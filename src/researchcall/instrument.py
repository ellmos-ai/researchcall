"""The instrument: what station 2 and 3 answer, turned into a questionnaire.

Until now the workbench collected instrument settings and then ran a fixture
questionnaire that had nothing to do with them. This module closes that gap. It
reads the answered form definitions and produces the questionnaire dictionary the
rest of the tool already knows how to handle — the same structure
``questionnaire.validate_questionnaire`` checks and ``questionnaire.build_task``
turns into the text an agent receives.

Three things it is careful about:

* **Quoted is spoken, unquoted is rephrased.** Measured against the real service
  (FINDINGS.md §4): a sentence in double quotes came back word for word, an
  intentional typo included. Everything outside the quotes was not only rephrased
  but extended. So quantitative items are quoted and qualitative ones are not —
  and the item says which it is.
* **Order is drawn per respondent, not per study.** A single shuffle at study
  level only removes the researcher's habit; position effects need a fresh order
  per call. Filters are respected: an item that depends on another never moves in
  front of it.
* **Nothing is invented.** Every value comes from a form definition. What the
  grammar below cannot express becomes a visible parse problem, not a silent
  default.
"""

from __future__ import annotations

import dataclasses
import random
import re
from typing import Any, Iterable, Sequence


#: Item formats, in the pipeline's German names and their English aliases.
FORMATS: dict[str, str] = {
    "dichotom": "dichotomous",
    "dichotomous": "dichotomous",
    "skala": "scale",
    "scale": "scale",
    "skala_umgepolt": "scale_reversed",
    "scale_reversed": "scale_reversed",
    "reversed": "scale_reversed",
    "auswahl": "choice",
    "choice": "choice",
    "offen": "open",
    "open": "open",
    "kreativ": "creative",
    "creative": "creative",
}

#: Formats whose answer is free text rather than a fixed category.
OPEN_FORMATS = {"open", "creative"}

#: Formats where every respondent must hear the identical sentence.
VERBATIM_BY_DEFAULT = {"dichotomous", "scale", "scale_reversed", "choice"}

DEFAULT_DICHOTOMOUS = ("yes", "no")

# CALL-E supports English and German (AGENTS.md). Generated sentences therefore
# exist in exactly those two, and in no third that nobody could check.
LOCALES = {"de": "de-DE", "en": "en-GB"}

SCALE_SENTENCE = {
    "de": "Bitte antworten Sie auf einer Skala von 1 bis {steps}, wobei 1 „{low}“ bedeutet und {steps} „{high}“.",
    "en": "Please answer on a scale from 1 to {steps}, where 1 means “{low}” and {steps} means “{high}”.",
}
RIGHT_TO_STOP = {
    "de": "Sie können das Gespräch jederzeit beenden, ohne einen Grund zu nennen.",
    "en": "You can end this call at any time without giving a reason.",
}
CONSENT_QUESTION = {
    "de": "Möchten Sie an der Befragung teilnehmen?",
    "en": "Would you like to take part in the survey?",
}
TIME_ESTIMATE = {
    "de": "Die Befragung dauert etwa {minutes} Minuten.",
    "en": "The survey takes about {minutes} minutes.",
}
NUMBER_ORIGIN_PREFIX = {"de": "Herkunft Ihrer Rufnummer: ", "en": "Where your number came from: "}
UNTITLED = {"de": "Unbenannte Erhebung", "en": "Untitled study"}

#: Seconds a spoken item costs, measured crudely: a sentence, a pause, an answer.
#: The estimate is announced on the phone, so it is deliberately not optimistic.
SECONDS_PER_ITEM = 25
SECONDS_PER_OPEN_ITEM = 55
SECONDS_FRAME = 75

_QUOTED = re.compile(r'^\s*[""„"\']?(?P<text>.*?)[""„"\']?\s*$')
_SCALE = re.compile(r"^(?P<steps>\d+)\s*:\s*(?P<low>.+?)\s*\.\.\s*(?P<high>.+)$")
_JUMP = re.compile(
    r"^\s*(?:if\s+|wenn\s+)?(?P<source>[\w.-]+)\s*(?:=|==|ist)\s*(?P<value>[^\s|]+)"
    r"\s*(?:->|=>|then\s+|dann\s+)?\s*(?:skip|überspringe|ueberspringe)\s+(?P<targets>.+)$",
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True)
class Item:
    """One question, as the instrument defines it."""

    id: str
    hypothesis: str
    format: str
    stem: str                       # what the researcher typed
    wording: str                    # what is spoken, scale sentence appended
    verbatim: bool
    categories: tuple[str, ...]
    scale: dict[str, Any] | None = None
    max_follow_ups: int = 0         # -1 means "until the conversation stops"
    analysis_rule: str = ""

    def as_question(self) -> dict[str, Any]:
        question: dict[str, Any] = {
            "id": self.id,
            "wording": self.wording,
            "categories": list(self.categories),
            "format": self.format,
            "verbatim": self.verbatim,
        }
        if self.hypothesis:
            question["hypothesis"] = self.hypothesis
        if self.scale:
            question["scale"] = dict(self.scale)
        if self.max_follow_ups:
            question["max_follow_ups"] = self.max_follow_ups
        if self.analysis_rule:
            question["analysis_rule"] = self.analysis_rule
        return question


@dataclasses.dataclass(frozen=True)
class Problem:
    """Something the grammar could not read, addressed to the person who wrote it."""

    line: int
    text: str
    message: str


def _as_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, (list, tuple)):
        return [str(line).strip() for line in value if str(line).strip()]
    return []


def _unquote(text: str) -> str:
    match = _QUOTED.match(text)
    return match.group("text").strip() if match else text.strip()


def parse_items(value: Any) -> tuple[list[Item], list[Problem]]:
    """Read the item table.

    One item per line::

        id | hypothesis | format | "wording" | option | option

    Options are ``key=value`` pairs or bare flags: ``scale=5:low..high``,
    ``categories=a,b,c``, ``free``, ``verbatim``, ``probe=2``, ``probe=unlimited``,
    ``rule=<how this answer is analysed>``.
    """
    items: list[Item] = []
    problems: list[Problem] = []
    seen: set[str] = set()

    for number, line in enumerate(_as_lines(value), start=1):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 4:
            problems.append(
                Problem(number, line, "needs at least id | hypothesis | format | wording")
            )
            continue

        identifier, hypothesis, raw_format = parts[0], parts[1], parts[2].lower()
        stem = _unquote(parts[3])
        options = [part for part in parts[4:] if part]

        if not identifier:
            problems.append(Problem(number, line, "the item needs an id"))
            continue
        if identifier in seen:
            problems.append(Problem(number, line, f"duplicate item id: {identifier}"))
            continue
        if not stem:
            problems.append(Problem(number, line, "the item needs a wording"))
            continue
        if raw_format not in FORMATS:
            problems.append(
                Problem(
                    number,
                    line,
                    "unknown format: " + raw_format + " — known: " + ", ".join(sorted(set(FORMATS.values()))),
                )
            )
            continue

        item_format = FORMATS[raw_format]
        verbatim = item_format in VERBATIM_BY_DEFAULT
        categories: tuple[str, ...] = ()
        scale: dict[str, Any] | None = None
        probes = 0
        rule = ""
        failed = False

        for option in options:
            key, _, raw = option.partition("=")
            key = key.strip().lower()
            raw = raw.strip()
            if key == "free":
                verbatim = False
            elif key == "verbatim":
                verbatim = True
            elif key == "categories":
                categories = tuple(
                    part.strip() for part in raw.split(",") if part.strip()
                )
            elif key == "scale":
                match = _SCALE.match(raw)
                if not match:
                    problems.append(
                        Problem(number, line, "scale needs the form scale=5:low..high")
                    )
                    failed = True
                    break
                steps = int(match.group("steps"))
                if not 2 <= steps <= 11:
                    problems.append(
                        Problem(number, line, "a spoken scale needs between 2 and 11 steps")
                    )
                    failed = True
                    break
                scale = {
                    "steps": steps,
                    "low": match.group("low").strip(),
                    "high": match.group("high").strip(),
                    "reversed": item_format == "scale_reversed",
                }
            elif key == "probe":
                if raw.lower() in {"unlimited", "unbegrenzt", "until_exhausted"}:
                    probes = -1
                elif raw.isdigit():
                    probes = int(raw)
                else:
                    problems.append(
                        Problem(number, line, "probe takes a number or 'unlimited'")
                    )
                    failed = True
                    break
            elif key == "rule":
                rule = raw
            else:
                problems.append(Problem(number, line, f"unknown option: {key}"))
                failed = True
                break
        if failed:
            continue

        if item_format in OPEN_FORMATS:
            if categories:
                problems.append(
                    Problem(number, line, "an open item is not coded into fixed categories")
                )
                continue
        elif item_format == "dichotomous":
            categories = categories or DEFAULT_DICHOTOMOUS
            if len(categories) != 2:
                problems.append(
                    Problem(number, line, "a dichotomous item has exactly two categories")
                )
                continue
        elif item_format in {"scale", "scale_reversed"}:
            if scale is None:
                problems.append(
                    Problem(number, line, "a scale item needs scale=<steps>:<low>..<high>")
                )
                continue
            categories = tuple(str(step) for step in range(1, scale["steps"] + 1))
        elif item_format == "choice":
            if len(categories) < 2:
                problems.append(
                    Problem(number, line, "a choice item needs categories=a,b,c")
                )
                continue

        if probes and item_format not in OPEN_FORMATS:
            problems.append(
                Problem(
                    number,
                    line,
                    "follow-up probes belong to open items; a standardised item must "
                    "sound the same for everyone",
                )
            )
            continue

        seen.add(identifier)
        items.append(
            Item(
                id=identifier,
                hypothesis=hypothesis,
                format=item_format,
                stem=stem,
                wording=stem,
                verbatim=verbatim,
                categories=categories,
                scale=scale,
                max_follow_ups=probes,
                analysis_rule=rule,
            )
        )
    return items, problems


def spoken_wording(item: Item, language: str) -> str:
    """The sentence the respondent hears — poles included, because they must be."""
    if not item.scale:
        return item.stem
    sentence = SCALE_SENTENCE.get(language, SCALE_SENTENCE["en"]).format(
        steps=item.scale["steps"], low=item.scale["low"], high=item.scale["high"]
    )
    return f"{item.stem} {sentence}"


def parse_jump_rules(value: Any, items: Sequence[Item]) -> tuple[dict[str, dict[str, Any]], list[Problem]]:
    """Turn ``if q1 = no skip q4, q5`` into a filter on q4 and q5.

    A skip rule is stored on the item that may be skipped, as the set of source
    answers that still lead to it. Expressing it there rather than on the source
    keeps one truth per item: an agent reading the task sees the condition next to
    the question it governs.
    """
    by_id = {item.id: item for item in items}
    conditions: dict[str, dict[str, Any]] = {}
    problems: list[Problem] = []

    for number, line in enumerate(_as_lines(value), start=1):
        match = _JUMP.match(line)
        if not match:
            problems.append(
                Problem(number, line, "needs the form: if q1 = no skip q4, q5")
            )
            continue
        source_id = match.group("source")
        value_text = _unquote(match.group("value"))
        targets = [part.strip() for part in re.split(r"[,\s]+", match.group("targets")) if part.strip()]

        source = by_id.get(source_id)
        if source is None:
            problems.append(Problem(number, line, f"unknown item: {source_id}"))
            continue
        if source.format in OPEN_FORMATS:
            problems.append(
                Problem(number, line, f"{source_id} is an open item and has no categories to branch on")
            )
            continue
        if value_text not in source.categories:
            problems.append(
                Problem(
                    number,
                    line,
                    f"{source_id} has no category {value_text!r} — it has: "
                    + ", ".join(source.categories),
                )
            )
            continue

        order = [item.id for item in items]
        remaining = [name for name in source.categories if name != value_text]
        for target in targets:
            if target not in by_id:
                problems.append(Problem(number, line, f"unknown item: {target}"))
                continue
            if order.index(target) <= order.index(source_id):
                problems.append(
                    Problem(
                        number,
                        line,
                        f"{target} is asked before {source_id} and cannot depend on it",
                    )
                )
                continue
            existing = conditions.get(target)
            if existing and existing["question"] != source_id:
                problems.append(
                    Problem(
                        number,
                        line,
                        f"{target} already depends on {existing['question']}; "
                        "one filter per item",
                    )
                )
                continue
            allowed = remaining if existing is None else [
                name for name in existing["equals"] if name in remaining
            ]
            if not allowed:
                problems.append(
                    Problem(number, line, f"the rules together never let {target} be asked")
                )
                continue
            conditions[target] = {"question": source_id, "equals": list(allowed)}
    return conditions, problems


def estimate_minutes(items: Sequence[Item]) -> int:
    """How long the interview takes, announced before consent.

    The number is spoken on the phone, so it rounds up: a promise that is broken
    damages the next survey as much as this one.
    """
    seconds = SECONDS_FRAME
    for item in items:
        seconds += SECONDS_PER_OPEN_ITEM if item.format in OPEN_FORMATS else SECONDS_PER_ITEM
        if item.max_follow_ups > 0:
            seconds += item.max_follow_ups * 30
        elif item.max_follow_ups < 0:
            seconds += 90
    return max(1, -(-seconds // 60))


def opening_blocks(values: dict[str, Any], items: Sequence[Item], language: str) -> list[dict[str, Any]]:
    """The conversation frame before the first question, in the order it is spoken."""
    blocks: list[dict[str, Any]] = []

    def add(kind: str, text: Any, verbatim: bool) -> None:
        for line in _as_lines(text):
            blocks.append({"kind": kind, "text": line, "verbatim": verbatim})

    add("greeting", values.get("ethics.greeting"), False)
    add("instruction", values.get("ethics.instruction"), True)
    if values.get("ethics.number_origin"):
        prefix = NUMBER_ORIGIN_PREFIX.get(language, NUMBER_ORIGIN_PREFIX["en"])
        add("number_origin", prefix + str(values["ethics.number_origin"]).strip(), True)
    if values.get("ethics.time_estimate", True):
        template = TIME_ESTIMATE.get(language, TIME_ESTIMATE["en"])
        add("time_estimate", template.format(minutes=estimate_minutes(items)), True)
    add("privacy", values.get("ethics.privacy_text"), True)
    return blocks


def consent_text(language: str) -> str:
    """The consent sentence, asked word for word.

    It carries the right to stop because that right is part of the frame: a
    setting nobody can switch off has to be *said*, not merely stored.
    """
    return (
        RIGHT_TO_STOP.get(language, RIGHT_TO_STOP["en"])
        + " "
        + CONSENT_QUESTION.get(language, CONSENT_QUESTION["en"])
    )


def build_questionnaire(
    values: dict[str, Any],
    language: str = "de",
) -> tuple[dict[str, Any], list[Problem]]:
    """The questionnaire the field phase runs, built from the answered stations."""
    language = language if language in LOCALES else "en"
    items, problems = parse_items(values.get("items"))
    conditions, rule_problems = parse_jump_rules(values.get("questionnaire.jump_rules"), items)
    problems = problems + rule_problems

    questions: list[dict[str, Any]] = []
    for item in items:
        question = dataclasses.replace(item, wording=spoken_wording(item, language)).as_question()
        condition = conditions.get(item.id)
        if condition:
            question["ask_if"] = condition
        questions.append(question)

    title = str(values.get("question") or "").strip() or UNTITLED.get(language, UNTITLED["en"])
    questionnaire: dict[str, Any] = {
        "title": title[:120],
        "question": title,
        "hypotheses": _as_lines(values.get("hypotheses")),
        "language": LOCALES[language],
        "consent_text": consent_text(language),
        "questions": questions,
        "order": str(values.get("questionnaire.order") or "fixed"),
        "opening": opening_blocks(values, items, language),
        "closing": [
            {"kind": "closing", "text": line, "verbatim": False}
            for line in _as_lines(values.get("ethics.closing"))
        ],
        "on_refusal": {
            "ask_reason": bool(values.get("ethics.on_refusal.ask_reason", True)),
            "offer_callback": bool(values.get("ethics.on_refusal.offer_callback", True)),
        },
        "coding": {
            "unlisted_answers": str(values.get("analysis.unlisted_answers") or "as_other"),
            "free_comments": str(values.get("analysis.free_comments") or "in_dataset"),
        },
        "estimated_minutes": estimate_minutes(items),
    }
    return questionnaire, problems


# --- order per respondent ------------------------------------------------------

def ordered_questions(
    questionnaire: dict[str, Any], sample_id: int
) -> list[dict[str, Any]]:
    """The item order for one respondent.

    ``fixed`` returns the questionnaire as written. ``randomised`` shuffles with a
    seed derived from the record, so the same record always hears the same order —
    a rerun of the dry run is reproducible — while two records almost never do.
    Filters survive the shuffle: an item that depends on another is pulled back
    behind it.
    """
    questions = list(questionnaire.get("questions", []))
    if str(questionnaire.get("order", "fixed")).lower() != "randomised":
        return questions

    shuffled = list(questions)
    random.Random(sample_id).shuffle(shuffled)
    return _repair_filters(shuffled)


def _repair_filters(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Move every dependent item behind the item it depends on, order otherwise kept."""
    placed: list[dict[str, Any]] = []
    waiting = list(questions)
    while waiting:
        progress = False
        remaining = []
        for question in waiting:
            condition = question.get("ask_if")
            source = condition.get("question") if isinstance(condition, dict) else None
            if source is None or any(done["id"] == source for done in placed):
                placed.append(question)
                progress = True
            else:
                remaining.append(question)
        if not progress:            # a cycle: keep the input order rather than loop
            placed.extend(remaining)
            break
        waiting = remaining
    return placed


def for_call(questionnaire: dict[str, Any], sample_id: int) -> dict[str, Any]:
    """The questionnaire as this one respondent hears it."""
    variant = dict(questionnaire)
    variant["questions"] = ordered_questions(questionnaire, sample_id)
    return variant


def item_index(questionnaire: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {question["id"]: question for question in questionnaire.get("questions", [])}


def is_open(question: dict[str, Any]) -> bool:
    return str(question.get("format", "")) in OPEN_FORMATS or not question.get("categories")


def describe(questionnaire: dict[str, Any], language: str = "de") -> list[str]:
    """The instrument as a readable list — the intermediate state to hand around."""
    lines = [f"# {questionnaire['title']}", ""]
    for block in questionnaire.get("opening", []):
        mark = '"' if block["verbatim"] else ""
        lines.append(f"- [{block['kind']}] {mark}{block['text']}{mark}")
    lines.append(f'- [consent] "{questionnaire["consent_text"]}"')
    lines.append("")
    for number, question in enumerate(questionnaire.get("questions", []), start=1):
        condition = question.get("ask_if")
        prefix = f"{number}. {question['id']}"
        if condition:
            prefix += f" (only if {condition['question']} = {'/'.join(condition['equals'])})"
        lines.append(f"{prefix}: {question['wording']}")
        if question.get("categories"):
            lines.append("   categories: " + ", ".join(question["categories"]))
        else:
            lines.append("   open answer, recorded as spoken")
    for block in questionnaire.get("closing", []):
        lines.append(f"- [closing] {block['text']}")
    return lines
