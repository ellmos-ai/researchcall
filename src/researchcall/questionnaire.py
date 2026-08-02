from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .safety import reject_high_stakes_content


CONSENT_VALUES = {"granted", "declined", "not_obtained"}

#: Formats whose answer is free text. They carry no categories and are never
#: coded during the call — interpreting a qualitative answer on the phone would
#: throw away the words the interpretation has to be checked against.
OPEN_FORMATS = {"open", "creative"}

#: Fields every structured result must carry.
REQUIRED_RESULT_FIELDS = {
    "consent",
    "withdrawal_requested",
    "asked_verbatim",
    "spoken_consent_wording",
    "spoken_wording",
    "answers",
    "raw_answers",
}

#: Fields a result may carry. They exist because the conversation frame can ask
#: for them (station 3) and are absent when it does not.
OPTIONAL_RESULT_FIELDS = {"refusal_reason", "callback_wanted"}

#: What an answer becomes when it fits none of the fixed categories and the
#: analysis rule says to keep it as "other". It is deliberately not a category of
#: the instrument: the instrument stays as it was written, and the report can
#: show how often the rule had to be applied.
UNLISTED_CODE = "__unlisted__"


def _task_label(value: str) -> str:
    return "`" + value.replace("`", "\\`") + "`"


def is_open_question(question: dict[str, Any]) -> bool:
    return str(question.get("format", "")) in OPEN_FORMATS or not question.get("categories")


def load_questionnaire_file(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Questionnaire must be a JSON object")
    validate_questionnaire(value)
    return value


def _condition_values(condition: dict[str, Any]) -> list[str]:
    equals = condition["equals"]
    return [str(equals)] if isinstance(equals, str) else [str(item) for item in equals]


def validate_questionnaire(questionnaire: dict[str, Any]) -> None:
    for field in ("title", "language", "consent_text", "questions"):
        if field not in questionnaire:
            raise ValueError(f"Questionnaire is missing required field: {field}")
    if not isinstance(questionnaire["questions"], list) or not questionnaire["questions"]:
        raise ValueError("Questionnaire questions must be a non-empty list")

    seen: dict[str, list[str]] = {}
    for question in questionnaire["questions"]:
        if not isinstance(question, dict):
            raise ValueError("Every question must be an object")
        question_id = question.get("id")
        wording = question.get("wording")
        categories = question.get("categories")
        if not isinstance(question_id, str) or not question_id:
            raise ValueError("Every question needs a non-empty id")
        if question_id in seen:
            raise ValueError(f"Duplicate question id: {question_id}")
        if not isinstance(wording, str) or not wording.strip():
            raise ValueError(f"Question {question_id} needs fixed wording")
        if is_open_question(question):
            if categories:
                raise ValueError(f"Open question {question_id} must not carry categories")
            categories = []
        else:
            if not isinstance(categories, list) or not categories:
                raise ValueError(f"Question {question_id} needs fixed answer categories")
            if len(set(categories)) != len(categories) or not all(
                isinstance(item, str) and item for item in categories
            ):
                raise ValueError(f"Question {question_id} has invalid answer categories")
        condition = question.get("ask_if")
        if condition is not None:
            if not isinstance(condition, dict) or set(condition) != {"question", "equals"}:
                raise ValueError(f"Question {question_id} has an invalid ask_if condition")
            if condition["question"] not in seen:
                raise ValueError(f"Question {question_id} filters on a later or unknown question")
            if not isinstance(condition["equals"], (str, list)) or condition["equals"] == []:
                raise ValueError(f"Question {question_id} has an empty ask_if condition")
            source_categories = seen[condition["question"]]
            unknown = [
                value for value in _condition_values(condition) if value not in source_categories
            ]
            if unknown:
                raise ValueError(
                    f"Question {question_id} filters on categories "
                    f"{', '.join(unknown)} that {condition['question']} does not have"
                )
        for follow_up in question.get("follow_ups", []):
            if not isinstance(follow_up, dict) or set(follow_up) != {"when", "wording"}:
                raise ValueError(f"Question {question_id} has an invalid follow-up")
            if follow_up["when"] not in categories:
                raise ValueError(f"Question {question_id} follow-up uses an unknown category")
            if not isinstance(follow_up["wording"], str) or not follow_up["wording"].strip():
                raise ValueError(f"Question {question_id} follow-up wording is empty")
        seen[question_id] = list(categories)
    reject_high_stakes_content(questionnaire)


def result_schema(questionnaire: dict[str, Any]) -> dict[str, Any]:
    answer_properties: dict[str, Any] = {}
    raw_answer_properties: dict[str, Any] = {}
    wording_properties: dict[str, Any] = {}
    question_ids: list[str] = []
    for question in questionnaire["questions"]:
        question_id = question["id"]
        question_ids.append(question_id)
        if is_open_question(question):
            # The words themselves are the datum. Coding happens in station 7,
            # against the raw text, by a rule that was fixed in advance.
            answer_properties[question_id] = {
                "type": "null",
                "description": "Open question: leave null, the answer belongs in raw_answers.",
            }
        else:
            answer_properties[question_id] = {
                "type": ["string", "null"],
                "enum": [*question["categories"], None],
            }
        raw_answer_properties[question_id] = {"type": ["string", "null"]}
        wording_properties[question_id] = {"type": ["string", "null"]}

    properties: dict[str, Any] = {
        "consent": {"type": "string", "enum": sorted(CONSENT_VALUES)},
        "withdrawal_requested": {"type": "boolean"},
        "asked_verbatim": {"type": "boolean"},
        "spoken_consent_wording": {"type": ["string", "null"]},
        "spoken_wording": {
            "type": "object",
            "additionalProperties": False,
            "required": question_ids,
            "properties": wording_properties,
        },
        "answers": {
            "type": "object",
            "additionalProperties": False,
            "required": question_ids,
            "properties": answer_properties,
        },
        "raw_answers": {
            "type": "object",
            "additionalProperties": False,
            "required": question_ids,
            "properties": raw_answer_properties,
        },
    }
    on_refusal = questionnaire.get("on_refusal") or {}
    if on_refusal.get("ask_reason"):
        properties["refusal_reason"] = {
            "type": ["string", "null"],
            "description": "Why the person declined, in their own words; null if not given.",
        }
    if on_refusal.get("offer_callback"):
        properties["callback_wanted"] = {
            "type": ["boolean", "null"],
            "description": "True only if the person said a call at another time is welcome.",
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(REQUIRED_RESULT_FIELDS),
        "properties": properties,
    }


def _condition_sentence(condition: dict[str, Any]) -> str:
    values = _condition_values(condition)
    if len(values) == 1:
        return f'equals category {_task_label(values[0])}'
    return "equals one of " + ", ".join(_task_label(value) for value in values)


def build_task(questionnaire: dict[str, Any]) -> str:
    """The whole call as one instruction — the only channel this API offers.

    Quoting is the load-bearing detail. Measured against the real service, a
    sentence in double quotes came back word for word; text outside the quotes was
    rephrased and extended. So everything that must be identical for every
    respondent is quoted, and only what may differ is left free.
    """
    lines = [
        "Conduct one standardized scientific telephone interview.",
        "STRICT STANDARDIZATION: Say every quoted sentence exactly as written. Do not paraphrase, summarize, embellish, or add spontaneous probes.",
        "Ask for consent first. If consent is not granted, thank the person and end the interview without asking survey questions.",
    ]

    opening = questionnaire.get("opening") or []
    if opening:
        lines.append("OPENING, in this order:")
        for block in opening:
            text = str(block.get("text", "")).strip()
            if not text:
                continue
            if block.get("verbatim", True):
                lines.append(f'- {block.get("kind", "opening")} (say exactly): "{text}"')
            else:
                lines.append(f'- {block.get("kind", "opening")} (your own words): {text}')

    lines.append(f'CONSENT (say exactly): "{questionnaire["consent_text"]}"')

    on_refusal = questionnaire.get("on_refusal") or {}
    if on_refusal.get("ask_reason"):
        lines.append(
            "If the person declines, ask once and without pressure what made them decline, "
            "and record their words in refusal_reason. Accept a non-answer."
        )
    if on_refusal.get("offer_callback"):
        lines.append(
            "If the person declines, ask whether a call at another time would be welcome "
            "and set callback_wanted accordingly. Do not negotiate."
        )

    lines.append("QUESTIONNAIRE:")
    for question in questionnaire["questions"]:
        prefix = question["id"]
        condition = question.get("ask_if")
        if condition:
            lines.append(
                f'- {prefix} FILTER: Ask only if {condition["question"]} {_condition_sentence(condition)}.'
            )
        if is_open_question(question):
            if question.get("verbatim"):
                lines.append(f'- {prefix} (say exactly): "{question["wording"]}"')
            else:
                lines.append(f'- {prefix} (open question, your own words): {question["wording"]}')
            lines.append(
                "  Record the answer as spoken in raw_answers; leave the entry in answers null. "
                "Do not categorize it yourself."
            )
            probes = int(question.get("max_follow_ups", 0) or 0)
            if probes > 0:
                lines.append(
                    f"  You may ask at most {probes} follow-up question(s) of your own here."
                )
            elif probes < 0:
                lines.append(
                    "  You may keep following up here until the answer is exhausted."
                )
            else:
                lines.append("  Do not follow up here.")
        else:
            lines.append(f'- {prefix} (say exactly): "{question["wording"]}"')
            lines.append(
                "  Allowed answer categories (interpretation labels; do not read aloud): "
                + ", ".join(_task_label(category) for category in question["categories"])
                + "."
            )
        for follow_up in question.get("follow_ups", []):
            lines.append(
                f'  If the interpreted answer is category {_task_label(str(follow_up["when"]))}, say exactly: "{follow_up["wording"]}"'
            )

    for block in questionnaire.get("closing") or []:
        text = str(block.get("text", "")).strip()
        if text:
            lines.append(f"CLOSING (your own words): {text}")

    lines.extend(
        [
            "Do not request names, addresses, background history, or any data not required by this questionnaire.",
            "If the person withdraws consent, stop immediately and set withdrawal_requested=true.",
            "For every question, return the actual words spoken in spoken_wording; use null when it was not asked.",
            "For every question, preserve the participant's raw words in raw_answers before interpreting them into answers; do not correct or paraphrase the raw words, and use null only when no answer was given.",
            "Set asked_verbatim=true only if every spoken consent/question sentence exactly matched the required wording.",
        ]
    )
    return "\n".join(lines)


def validate_structured_result(
    questionnaire: dict[str, Any], result: dict[str, Any]
) -> None:
    present = set(result)
    if not REQUIRED_RESULT_FIELDS <= present:
        raise ValueError("Structured result fields do not match the recipient schema")
    if present - REQUIRED_RESULT_FIELDS - OPTIONAL_RESULT_FIELDS:
        raise ValueError("Structured result fields do not match the recipient schema")
    if result["consent"] not in CONSENT_VALUES:
        raise ValueError("Structured result has an invalid consent value")
    if not isinstance(result["withdrawal_requested"], bool):
        raise ValueError("withdrawal_requested must be boolean")
    if not isinstance(result["asked_verbatim"], bool):
        raise ValueError("asked_verbatim must be boolean")
    if result["spoken_consent_wording"] is not None and not isinstance(
        result["spoken_consent_wording"], str
    ):
        raise ValueError("spoken_consent_wording must be a string or null")
    if not all(
        isinstance(result[field], dict)
        for field in ("spoken_wording", "answers", "raw_answers")
    ):
        raise ValueError("spoken_wording, answers, and raw_answers must be objects")
    if result.get("refusal_reason") is not None and not isinstance(
        result["refusal_reason"], str
    ):
        raise ValueError("refusal_reason must be a string or null")
    if result.get("callback_wanted") is not None and not isinstance(
        result["callback_wanted"], bool
    ):
        raise ValueError("callback_wanted must be a boolean or null")

    expected_ids = {question["id"] for question in questionnaire["questions"]}
    if any(
        set(result[field]) != expected_ids
        for field in ("spoken_wording", "answers", "raw_answers")
    ):
        raise ValueError("Structured result question ids do not match the questionnaire")
    for question in questionnaire["questions"]:
        question_id = question["id"]
        wording = result["spoken_wording"][question_id]
        answer = result["answers"][question_id]
        raw_answer = result["raw_answers"][question_id]
        if wording is not None and not isinstance(wording, str):
            raise ValueError(f"Spoken wording for {question_id} must be a string or null")
        if raw_answer is not None and not isinstance(raw_answer, str):
            raise ValueError(f"Raw answer for {question_id} must be a string or null")
        if is_open_question(question):
            if answer is not None:
                raise ValueError(
                    f"Open question {question_id} must not be categorized during the call"
                )
            continue
        if (
            answer is not None
            and answer != UNLISTED_CODE
            and answer not in question["categories"]
        ):
            raise ValueError(f"Answer for {question_id} is outside its fixed categories")
        if answer is not None and (not isinstance(raw_answer, str) or not raw_answer.strip()):
            raise ValueError(f"Categorized answer for {question_id} needs a raw answer")


def wording_matches(questionnaire: dict[str, Any], result: dict[str, Any]) -> bool:
    """Whether every sentence that had to be identical actually was.

    Items the instrument marked as free are excluded: for them a fresh phrasing is
    the intention, not a deviation. Judging them by the same yardstick would turn
    a deliberate methodological choice into a failure.
    """
    observed = result["consent"] != "not_obtained"
    if result["consent"] != "not_obtained":
        if result["spoken_consent_wording"] != questionnaire["consent_text"]:
            return False
    binding = {
        question["id"]: question["wording"]
        for question in questionnaire["questions"]
        if question.get("verbatim", True)
    }
    spoken = result["spoken_wording"]
    for question_id, actual in spoken.items():
        if actual is None or question_id not in binding:
            continue
        observed = True
        if actual != binding[question_id]:
            return False
    return observed
