"""Gate phrases: the sentences that MUST fall, checked by recognition.

A live check of ethics gates is only honest under one condition, and the
operator stated it precisely: the exact sentences have to be defined in
advance, and recognition means finding them — not judging whether the agent
"basically" covered the ground. Free semantic judgement would be an
interpretation without a checkable source, which is the one thing this project
refuses everywhere.

The empirical basis exists (EVIDENCE-001): the agent speaks its instructed
wording faithfully down to a typo, and the ``activity`` feed carries the
spoken lines (``Bot is speaking ...``) while the call runs. So a monitor can
compare those lines against the required phrases as literal text.

What a miss means is deliberately narrow: *this phrase was not seen in the
monitored lines.* It does not mean the agent skipped it — the feed could be
incomplete. That is exactly why a miss files a review case for a person
instead of failing the call on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .questionnaire import (
    ai_disclosure_sentence,
    privacy_sentence,
    stop_right_sentence,
)


@dataclass(frozen=True)
class GatePhrase:
    """One sentence that must fall, verbatim, at least once."""

    key: str        # e.g. "greeting", "consent_question", "abort_offer"
    text: str       # the exact sentence handed to the voice agent

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("A gate phrase needs a key")
        if len(self.text.strip()) < 15:
            raise ValueError(
                f"Gate phrase '{self.key}' is too short to be recognisable; a "
                f"fragment would match half the conversation"
            )


#: One rendered transcript line: ``[mm:ss] SPEAKER: text``.
SPOKEN_LINE_RE = re.compile(r"^\[\d{2}:\d{2}\] (?P<speaker>[A-Z]+): (?P<text>.*)$")


def bot_utterances(transcript: str) -> list[str]:
    """What the agent actually said, without the transcript's own scaffolding.

    Measured on the first live call (2026-08-11): the agent speaks one required
    sentence across three turns. Concatenated it was character-identical to the
    required phrase — a line break, not a paraphrase. Reading whole transcript
    lines therefore missed the gate, because each line carries its own
    ``[00:06] BOT: `` prefix and that text sat between the parts of the
    sentence.

    Only the agent's own turns are returned. A gate is a sentence the agent owes
    the person; hearing it back from the other side does not discharge it. A
    line that does not parse is passed through unchanged rather than dropped:
    losing text would weaken a check whose whole point is literal recognition.
    """
    spoken: list[str] = []
    for line in transcript.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = SPOKEN_LINE_RE.fullmatch(stripped)
        if match is None:
            spoken.append(stripped)
        elif match.group("speaker") == "BOT":
            spoken.append(match.group("text"))
    return spoken


def _normalise(text: str) -> str:
    """Whitespace-tolerant, case-tolerant, punctuation kept.

    Punctuation stays significant on purpose: "May I ask you three questions?"
    and "May I ask you three questions" are the same sentence; dropping all
    punctuation, however, would let unrelated fragments run together.
    """
    return re.sub(r"\s+", " ", text).strip().lower()


def phrases_from_questionnaire(questionnaire: dict[str, Any]) -> list[GatePhrase]:
    """The gate phrases a study defines, plus the one every study carries.

    The consent text is always a gate: no question before it is not
    configurable, so its sentence is not either.
    """
    phrases = [
        GatePhrase(key="consent_question", text=questionnaire["consent_text"]),
        # Both are spoken in every call and neither is configurable, so both are
        # checked the same way the consent sentence is: a call that did not
        # disclose the machine, or did not offer the way out, lands in review.
        GatePhrase(key="ai_disclosure", text=ai_disclosure_sentence(questionnaire)),
        GatePhrase(
            key="stop_right",
            text=stop_right_sentence(questionnaire.get("language", "")),
        ),
        # What happens with the answers is an information duty like the other
        # two, so it is checked like them. The duration is not a gate: a missing
        # duration is a discourtesy, not a breach, and every added gate buys
        # more false alarms for less.
        GatePhrase(key="data_statement", text=privacy_sentence(questionnaire)),
    ]
    for entry in questionnaire.get("gate_phrases", []):
        phrases.append(GatePhrase(key=str(entry["key"]), text=str(entry["text"])))
    seen: set[str] = set()
    for phrase in phrases:
        if phrase.key in seen:
            raise ValueError(f"Duplicate gate phrase key: {phrase.key}")
        seen.add(phrase.key)
    return phrases


@dataclass
class PhraseMonitor:
    """Reads along and ticks off phrases as their sentences appear.

    Feed it whatever the transport shows — activity lines during a live call,
    or the transcript afterwards. The two uses share one matcher, so the live
    verdict and the post-hoc audit cannot drift apart.
    """

    phrases: list[GatePhrase]
    _seen: set[str] = field(default_factory=set)
    _buffer: str = ""

    def observe(self, line: str) -> list[str]:
        """Take one monitored line; return the keys newly satisfied by it.

        Lines are also appended to a rolling buffer, because a transport may
        split one sentence across two activity events. The buffer is capped so
        an hour of talk does not grow an unbounded string.
        """
        self._buffer = _normalise(self._buffer + " " + line)[-4000:]
        normalised_line = _normalise(line)
        newly: list[str] = []
        for phrase in self.phrases:
            if phrase.key in self._seen:
                continue
            needle = _normalise(phrase.text)
            if needle in normalised_line or needle in self._buffer:
                self._seen.add(phrase.key)
                newly.append(phrase.key)
        return newly

    def observe_all(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.observe(line)

    @property
    def seen(self) -> list[str]:
        return sorted(self._seen)

    @property
    def missed(self) -> list[str]:
        return sorted(p.key for p in self.phrases if p.key not in self._seen)

    def findings(self) -> dict[str, Any]:
        """What goes into the attempt record. A miss is a fact about the feed."""
        return {
            "gates_seen": self.seen,
            "gates_missed": self.missed,
            "gate_check_basis": (
                "literal recognition of predefined sentences in what the agent "
                "said, with its turns joined"
            ),
        }


#: The floor, in the order it is spoken. The order is what makes the check
#: possible without judging the conversation: anything before a sentence that
#: WAS spoken must have been spoken too.
FLOOR_SEQUENCE = ("disclosure", "scope", "data", "stop", "deletion")


def floor_sentences(questionnaire: dict[str, Any]) -> dict[str, str]:
    """Every sentence the floor owes this call, keyed by its place in the order."""
    from .questionnaire import (
        ai_disclosure_sentence,
        deletion_sentence,
        privacy_sentence,
        scope_sentence,
        stop_right_sentence,
        withdrawal_route_sentence,
    )

    return {
        "disclosure": ai_disclosure_sentence(questionnaire),
        "scope": scope_sentence(questionnaire),
        "data": privacy_sentence(questionnaire),
        "stop": stop_right_sentence(questionnaire.get("language", "")),
        "deletion": deletion_sentence(questionnaire),
        "withdrawal": withdrawal_route_sentence(questionnaire),
    }


def audit_floor(
    transcript: str, questionnaire: dict[str, Any], completed: bool = False
) -> dict[str, Any]:
    """Which owed sentences were skipped — and which the call never reached.

    Three of the floor's sentences are not gate phrases: scope, deletion and the
    withdrawal route. Until now nothing checked them at all, because the wording
    audit builds its expectations from consent and questions only. A promise
    nobody verifies is the same class of claim that went wrong once already.

    Making them gates would have been the lazy fix and a wrong one: a call that
    breaks off during the opening never owed the later sentences, and flagging
    it would bury the review queue in hang-ups. So the debt is derived from how
    far the conversation actually got, by a rule that judges nothing:

    * a sentence is **missing** when a LATER one was spoken — the order is
      fixed, so a hole in the middle is a skip;
    * a sentence after the last one spoken is **not reached**, which is a fact
      about the call, not a fault of the agent;
    * the withdrawal route is owed exactly when the interview ran to the end,
      which the outcome says and the order cannot.

    It reads the same rendered speech as the gate audit, through the same
    helper, so the two cannot drift apart.
    """
    spoken = _normalise(" ".join(bot_utterances(transcript)))
    sentences = floor_sentences(questionnaire)
    seen = {
        key: _normalise(text) in spoken
        for key, text in sentences.items()
        if text
    }
    order = [key for key in FLOOR_SEQUENCE if key in seen]
    last_spoken = max(
        (index for index, key in enumerate(order) if seen[key]), default=-1
    )
    missing = [key for key in order[:last_spoken] if not seen[key]]
    not_reached = [key for key in order[last_spoken + 1 :]]

    if "withdrawal" in seen:
        if completed and not seen["withdrawal"]:
            missing.append("withdrawal")
        elif not seen["withdrawal"]:
            not_reached.append("withdrawal")

    return {
        "floor_spoken": sorted(key for key, was_spoken in seen.items() if was_spoken),
        "floor_missing": missing,
        "floor_not_reached": not_reached,
        "floor_check_basis": (
            "a floor sentence counts as owed once a later one was spoken; the "
            "withdrawal route once the interview ran to the end"
        ),
    }


def audit_transcript(transcript: str, phrases: list[GatePhrase]) -> dict[str, Any]:
    """The post-hoc twin of the live monitor, over the final transcript.

    The monitor keeps a rolling buffer precisely so a sentence may arrive in
    pieces; it is fed the agent's utterances rather than the transcript's lines
    so that the pieces sit next to each other. An interjection from the other
    side does not separate them: those turns are not fed at all.
    """
    monitor = PhraseMonitor(phrases=phrases)
    monitor.observe_all(bot_utterances(transcript) or [transcript])
    return monitor.findings()
