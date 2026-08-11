from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .questionnaire import build_task, result_schema


TERMINAL_STATUSES = {
    "COMPLETED",
    "FAILED",
    "NO_ANSWER",
    "DECLINED",
    "CANCELED",
    "CANCELLED",
    "VOICEMAIL",
    "BUSY",
    "EXPIRED",
}

OBSERVED_SETUP_SECONDS = 40
ProgressCallback = Callable[[dict[str, Any]], None]

#: Stand-in refusal reasons. Short, plausible, and never presented as real: every
#: one of them is marked as fixture text where it is shown or exported.
FIXTURE_REFUSALS = (
    "(fixture) no time right now",
    "(fixture) does not take part in surveys",
    "(fixture) does not trust automated calls",
    "(fixture) topic not relevant to me",
)


#: Sentences an answering machine says and a person does not. One of them, in
#: the callee's own words, is enough to read the call as a mailbox pickup.
VOICEMAIL_MARKERS = (
    "nachricht nach dem signalton",
    "nachricht nach dem ton",
    "hinterlassen sie eine nachricht",
    "hinterlassen sie mir eine nachricht",
    "nach dem signalton",
    "nach dem piepton",
    "mailbox",
    "sprachbox",
    "anrufbeantworter",
    "voicemail",
    "leave a message",
    "after the tone",
    "after the beep",
    "answering machine",
    "record your message",
)

#: Wording a machine announcement uses that a person also uses about themselves
#: ("I'm hard to reach right now"). Alone it decides nothing: it needs a second
#: signal, either another marker or the agent's own evidence note.
WEAK_VOICEMAIL_MARKERS = (
    "nicht erreichbar",
    "zurzeit nicht erreichbar",
    "not available",
    "currently unavailable",
)

#: CALL-E reports a refused call as a generic failure and keeps the real ending
#: in a free-text field: "calling task status=DECLINED (Hangup by: user)".
FAILURE_STATUS_RE = re.compile(r"status=([A-Z_]+)")


def _passes_filter(question: dict[str, Any], answers: dict[str, Any]) -> bool:
    """Whether a filtered item would be asked, given the answers so far."""
    condition = question.get("ask_if")
    if not isinstance(condition, dict):
        return True
    given = answers.get(condition.get("question"))
    if given is None:
        return False
    equals = condition.get("equals")
    allowed = [equals] if isinstance(equals, str) else list(equals or ())
    return given in allowed


def _fits(question: dict[str, Any], value: Any) -> bool:
    """Whether a recorded fixture answer belongs to *this* item.

    Item ids repeat across studies — ``q1`` is ``q1`` everywhere. Without this
    check the demo fixture's ``satisfied`` would land in a five-point scale built
    in the workbench, and the run would spend its time reporting a coding problem
    that only the fixture had. A pattern that wants an out-of-category answer on
    purpose says so with ``allow_unlisted``.
    """
    if value is None:
        return True
    categories = question.get("categories") or []
    if not categories:      # an open item is never categorized during the call
        return False
    return value in categories


def _stand_in(
    question: dict[str, Any], sample_id: int, asked: bool
) -> tuple[Any, str | None]:
    """A deterministic answer for an item the fixture file does not know."""
    if not asked:
        return None, None
    categories = question.get("categories") or []
    if not categories:
        return None, f"(fixture) free answer for {question['id']}"
    index = (sample_id * 7 + sum(ord(char) for char in str(question["id"]))) % len(categories)
    category = categories[index]
    return category, f"(fixture) {category}"


def _refusal_reason(sample_id: int) -> str:
    return FIXTURE_REFUSALS[sample_id % len(FIXTURE_REFUSALS)]


def _turn_speaker(turn: dict[str, Any]) -> str:
    """``BOT`` for the agent, ``USER`` for whoever answered.

    The measured payload labels turns ``bot`` and ``user``. Everything that is
    not the agent is folded into ``USER`` on purpose: the after-call audits read
    the rendered lines through ``runner.TRANSCRIPT_LINE_RE``, which accepts these
    two speakers only, so an unexpected third label would not just look odd — it
    would switch the wording and gate checks off for the whole call.
    """
    return "BOT" if str(turn.get("speaker") or "").strip().lower() == "bot" else "USER"


def _turn_text(turn: dict[str, Any]) -> str:
    return str(turn.get("text") or "").strip()


def _transcript_from_turns(turns: list[dict[str, Any]]) -> str:
    """Render recorded turns as the ``[mm:ss] SPEAKER: Text`` lines the audits read."""
    lines = []
    for turn in turns:
        try:
            seconds = max(0, int(float(turn.get("offset_seconds") or 0)))
        except (TypeError, ValueError):
            seconds = 0
        lines.append(
            f"[{seconds // 60:02d}:{seconds % 60:02d}] "
            f"{_turn_speaker(turn)}: {_turn_text(turn)}"
        )
    return "\n".join(lines)


def _voicemail_markers(
    turns: list[dict[str, Any]], evidence: list[str]
) -> list[str] | None:
    """Whether the callee side of this call was a machine, by literal recognition.

    A documented heuristic, not a verdict: it reads only what the callee said,
    looks for sentences a mailbox announcement uses, and returns the markers it
    found so the attempt record carries its own grounds. Weak wording that a
    person also uses about themselves needs corroboration — from a second marker
    or from the agent's evidence note. Anything less certain stays completed,
    because inflating the nonresponse column is the cheaper mistake.
    """
    spoken = " ".join(
        _turn_text(turn).lower() for turn in turns if _turn_speaker(turn) != "BOT"
    )
    if not spoken.strip():
        return None
    strong = [marker for marker in VOICEMAIL_MARKERS if marker in spoken]
    if strong:
        return strong
    weak = [marker for marker in WEAK_VOICEMAIL_MARKERS if marker in spoken]
    if not weak:
        return None
    noted = " ".join(str(item).lower() for item in evidence)
    corroborated = len(weak) > 1 or any(
        marker in noted for marker in VOICEMAIL_MARKERS
    )
    return weak if corroborated else None


@dataclass(frozen=True)
class CallOutcome:
    status: str
    run_id: str | None
    structured_result: dict[str, Any] | None
    detail: dict[str, Any]
    transcript: str | None = None


class FixtureCallClient:
    """Offline client. It never imports an SDK and never opens a network connection."""

    def __init__(self, patterns: list[dict[str, Any]]) -> None:
        if not patterns:
            raise ValueError("Fixture outcome list must not be empty")
        self.patterns = patterns

    @classmethod
    def from_file(cls, path: str | Path) -> "FixtureCallClient":
        patterns = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(patterns, list) or not all(isinstance(item, dict) for item in patterns):
            raise ValueError("Fixture outcomes must be a JSON array of objects")
        return cls(patterns)

    def call(
        self,
        sample: dict[str, Any],
        questionnaire: dict[str, Any],
        idempotency_key: str,
    ) -> CallOutcome:
        del idempotency_key
        pattern = self.patterns[(int(sample["sample_id"]) - 1) % len(self.patterns)]
        status = str(pattern.get("status", "FAILED")).upper()
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Fixture uses unsupported terminal status: {status}")

        structured: dict[str, Any] | None = None
        if pattern.get("structured", status == "COMPLETED"):
            answers_in = pattern.get("answers", {})
            if not isinstance(answers_in, dict):
                raise ValueError("Fixture answers must be an object")
            raw_answers_in = pattern.get("raw_answers")
            if not isinstance(raw_answers_in, dict):
                raise ValueError("Fixture raw_answers must be an object")
            asked_verbatim = bool(pattern.get("asked_verbatim", True))
            consent = str(pattern.get("consent", "granted"))
            answered = consent == "granted"

            allow_unlisted = bool(pattern.get("allow_unlisted", False))
            answers: dict[str, Any] = {}
            raw_answers: dict[str, str | None] = {}
            for question in questionnaire["questions"]:
                question_id = question["id"]
                if (question_id in answers_in or question_id in raw_answers_in) and (
                    allow_unlisted
                    or _fits(question, answers_in.get(question_id))
                ):
                    answers[question_id] = answers_in.get(question_id)
                    raw_answers[question_id] = raw_answers_in.get(question_id)
                    continue
                # The fixture has no line for this item — it belongs to an
                # instrument somebody built in the workbench. Rather than return
                # nothing, stand in for an answer, deterministically and visibly
                # marked as invented, so a dry run of a fresh questionnaire is
                # still worth watching.
                value, raw = _stand_in(
                    question, int(sample["sample_id"]), answered and _passes_filter(question, answers)
                )
                answers[question_id] = value
                raw_answers[question_id] = raw

            spoken: dict[str, str | None] = {}
            changed = False
            for question in questionnaire["questions"]:
                question_id = question["id"]
                if answers[question_id] is None and raw_answers.get(question_id) is None:
                    spoken[question_id] = None
                elif not question.get("verbatim", True):
                    # A free item is meant to be rephrased; saying it word for
                    # word would be the deviation, not the other way round.
                    spoken[question_id] = "Fixture rephrasing: " + question["wording"]
                elif asked_verbatim or changed:
                    spoken[question_id] = question["wording"]
                else:
                    spoken[question_id] = "Fixture paraphrase: " + question["wording"]
                    changed = True
            consent_wording: str | None
            if consent == "not_obtained":
                consent_wording = None
            elif asked_verbatim:
                consent_wording = questionnaire["consent_text"]
            else:
                consent_wording = "Fixture paraphrase: " + questionnaire["consent_text"]
            structured = {
                "consent": consent,
                "withdrawal_requested": bool(pattern.get("withdrawal_requested", False)),
                "asked_verbatim": asked_verbatim,
                "spoken_consent_wording": consent_wording,
                "spoken_wording": spoken,
                "answers": answers,
                "raw_answers": raw_answers,
            }
            on_refusal = questionnaire.get("on_refusal") or {}
            if consent == "declined":
                if on_refusal.get("ask_reason"):
                    structured["refusal_reason"] = pattern.get(
                        "refusal_reason", _refusal_reason(int(sample["sample_id"]))
                    )
                if on_refusal.get("offer_callback"):
                    structured["callback_wanted"] = bool(
                        pattern.get("callback_wanted", int(sample["sample_id"]) % 3 == 0)
                    )
        return CallOutcome(
            status=status,
            run_id=f"fixture-{sample['sample_id']}",
            structured_result=structured,
            detail={"transport": "fixture", "pattern": (int(sample["sample_id"]) - 1) % len(self.patterns)},
        )

    def call_batch(
        self,
        samples: list[dict[str, Any]],
        questionnaire: dict[str, Any],
        idempotency_key: str,
    ) -> list[CallOutcome]:
        """The batch path of the offline transport.

        It exists so the dispatch machinery can be exercised end to end without
        a network. The live client deliberately has no counterpart yet: batch
        dispatch over the wire is documented but unproven here, and a method
        that pretends otherwise would let ``resolve_dispatch`` select a path
        nobody has seen work. Each outcome is marked with the shared batch key
        so the record shows these calls travelled in one request.
        """
        outcomes = []
        for index, sample in enumerate(samples):
            outcome = self.call(sample, questionnaire, f"{idempotency_key}:{index}")
            detail = dict(outcome.detail)
            detail["batch_key"] = idempotency_key
            detail["batch_position"] = index
            outcomes.append(
                CallOutcome(
                    status=outcome.status,
                    run_id=outcome.run_id,
                    structured_result=outcome.structured_result,
                    detail=detail,
                    transcript=outcome.transcript,
                )
            )
        return outcomes


class LiveCallClient:
    """Minimal, deliberately serial CALL-E Developer API adapter.

    This path is present for later operator validation. It is never selected unless the
    CLI receives all explicit live-call gates.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        first_poll_seconds: float = 60.0,
        poll_seconds: float = 10.0,
        poll_timeout_seconds: float = 900.0,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("CALLE_API_KEY is required for live mode")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.first_poll_seconds = first_poll_seconds
        self.poll_seconds = poll_seconds
        self.poll_timeout_seconds = poll_timeout_seconds
        self.progress_callback = progress_callback

    @classmethod
    def from_environment(
        cls, progress_callback: ProgressCallback | None = None
    ) -> "LiveCallClient":
        """The one place a live client is built — and whose key it spends.

        In ``huckepack-only-host`` the visitor's own key outranks the host's
        environment, and its absence raises instead of falling back: charging
        the host for a visitor's call is the failure nobody would notice.
        """
        from .huckepack_key import credential_override

        override = credential_override()
        return cls(
            api_key=override or os.environ.get("CALLE_API_KEY", ""),
            base_url=os.environ.get("CALLE_BASE_URL", "https://api.heycall-e.com"),
            progress_callback=progress_callback,
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                value = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"CALL-E API returned HTTP {error.code}") from error
        if not isinstance(value, dict):
            raise RuntimeError("CALL-E API returned a non-object response")
        return value

    @staticmethod
    def _status(value: dict[str, Any]) -> str | None:
        containers = [value]
        if isinstance(value.get("result"), dict):
            containers.append(value["result"])
        for container in containers:
            status = container.get("status") or container.get("call_status")
            if isinstance(status, str):
                return status.upper()
        return None

    @staticmethod
    def _activity(value: dict[str, Any]) -> list[Any]:
        if isinstance(value.get("activity"), list):
            return value["activity"]
        result = value.get("result")
        if isinstance(result, dict) and isinstance(result.get("activity"), list):
            return result["activity"]
        return []

    @classmethod
    def _activity_progress(cls, value: dict[str, Any]) -> dict[str, Any] | None:
        activity = cls._activity(value)
        if not activity:
            return None
        latest = activity[-1]
        timestamp = None
        if isinstance(latest, dict):
            for key in ("timestamp", "created_at", "time"):
                if isinstance(latest.get(key), str):
                    timestamp = latest[key]
                    break
        return {
            "activity_events": len(activity),
            "latest_activity_at": timestamp,
        }

    @staticmethod
    def _containers(value: dict[str, Any]) -> list[dict[str, Any]]:
        """The response object and its nested ``result``, in that order."""
        containers = [value]
        if isinstance(value.get("result"), dict):
            containers.append(value["result"])
        return containers

    @classmethod
    def _recipient_attempts(cls, value: dict[str, Any]) -> list[dict[str, Any]]:
        """The attempts CALL-E reports for the first recipient.

        One created call may contain several dial attempts — the service redials
        on its own. They are read as a list rather than assumed to be one, and
        their number is recorded, so a run that used only the last of them says
        so instead of quietly dropping the others.
        """
        for container in cls._containers(value):
            recipients = container.get("recipients")
            if (
                isinstance(recipients, list)
                and recipients
                and isinstance(recipients[0], dict)
            ):
                attempts = recipients[0].get("attempts")
                if isinstance(attempts, list):
                    return [item for item in attempts if isinstance(item, dict)]
        return []

    @staticmethod
    def _turns(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The turns of the last attempt that recorded any — the one that ended the call."""
        for attempt in reversed(attempts):
            turns = attempt.get("transcript_turns")
            if isinstance(turns, list):
                usable = [
                    turn
                    for turn in turns
                    if isinstance(turn, dict) and _turn_text(turn)
                ]
                if usable:
                    return usable
        return []

    @classmethod
    def _evidence(cls, value: dict[str, Any]) -> list[str]:
        for container in cls._containers(value):
            evidence = container.get("evidence")
            if isinstance(evidence, list):
                return [str(item) for item in evidence]
        return []

    @staticmethod
    def _transcript(
        value: dict[str, Any], turns: list[dict[str, Any]]
    ) -> tuple[str | None, str | None]:
        """The transcript and where it came from.

        Measured on 2026-08-11: a completed call carries its transcript as a
        ``transcript_turns`` list under the recipient's attempt, and the
        top-level ``result.transcript`` string can be absent entirely. Reading
        only the string left ``outcome.transcript`` empty, and an empty
        transcript switches off both after-call audits without saying so. The
        string remains the fallback because the earlier measurement returned it.
        """
        if turns:
            return (
                _transcript_from_turns(turns),
                "recipients[].attempts[].transcript_turns",
            )
        result = value.get("result")
        if isinstance(result, dict) and isinstance(result.get("transcript"), str):
            return result["transcript"], "result.transcript"
        return None, None

    @classmethod
    def _failure_status(cls, value: dict[str, Any]) -> str | None:
        """The terminal status hidden in the failure message, if it names one.

        A refusal arrives as ``status=FAILED`` with the real ending in free text.
        Reporting it as a generic failure would collapse an active refusal into
        the technical-error column — and a refusal that is dialled again is
        harassment, so the difference decides behaviour, not just presentation.
        The message itself is parsed and discarded: it is foreign free text, and
        nothing foreign is written into the attempt record.
        """
        for container in cls._containers(value):
            message = container.get("failure_message")
            if not isinstance(message, str):
                continue
            match = FAILURE_STATUS_RE.search(message)
            if match and match.group(1) in TERMINAL_STATUSES:
                return match.group(1)
        return None

    @classmethod
    def _failure_code(cls, value: dict[str, Any]) -> str | None:
        for container in cls._containers(value):
            code = container.get("failure_code")
            if isinstance(code, str) and code:
                return code
        return None

    @staticmethod
    def _structured_result(value: dict[str, Any]) -> dict[str, Any] | None:
        containers = [value]
        if isinstance(value.get("result"), dict):
            containers.insert(0, value["result"])
        for container in containers:
            for key in ("structured_result", "structuredResult"):
                if isinstance(container.get(key), dict):
                    return container[key]
            recipients = container.get("recipients")
            if (
                isinstance(recipients, list)
                and recipients
                and isinstance(recipients[0], dict)
            ):
                recipient = recipients[0]
                for key in ("structured_result", "structuredResult"):
                    if isinstance(recipient.get(key), dict):
                        return recipient[key]
        return None

    def call(
        self,
        sample: dict[str, Any],
        questionnaire: dict[str, Any],
        idempotency_key: str,
    ) -> CallOutcome:
        payload = {
            "task": build_task(questionnaire),
            "recipients": [
                {
                    "phones": [sample["phone_e164"]],
                    "region": "DE",
                    "locale": questionnaire["language"],
                }
            ],
            "result_schema": {
                "type": "object",
                "properties": {"completed_count": {"type": "integer"}},
            },
            "recipient_result_schema": result_schema(questionnaire),
            "metadata": {"researchcall_sample_id": str(sample["sample_id"])},
        }
        created = self._request(
            "POST", "/v1/calls", payload=payload, idempotency_key=idempotency_key
        )
        run_id = created.get("id") or created.get("call_id") or created.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise RuntimeError("CALL-E create response did not include a call id")

        deadline = time.monotonic() + self.poll_timeout_seconds
        time.sleep(self.first_poll_seconds)
        latest = created
        activity_fingerprint: str | None = None
        while True:
            latest = self._request("GET", f"/v1/calls/{run_id}")
            activity = self._activity(latest)
            new_fingerprint = json.dumps(
                activity, ensure_ascii=False, sort_keys=True, default=str
            )
            progress = self._activity_progress(latest)
            if (
                progress is not None
                and new_fingerprint != activity_fingerprint
                and self.progress_callback is not None
            ):
                self.progress_callback(progress)
            activity_fingerprint = new_fingerprint
            status = self._status(latest)
            if status in TERMINAL_STATUSES:
                attempts = self._recipient_attempts(latest)
                turns = self._turns(attempts)
                transcript, transcript_location = self._transcript(latest, turns)
                structured = self._structured_result(latest)
                detail: dict[str, Any] = {
                    "transport": "live-api",
                    "progress_source": "activity",
                    "transcript_location": transcript_location,
                }
                if attempts:
                    detail["recipient_attempts"] = len(attempts)
                if progress is not None:
                    detail.update(progress)

                code = self._failure_code(latest)
                if code:
                    detail["failure_code"] = code
                if status == "FAILED":
                    refined = self._failure_status(latest)
                    if refined is not None and refined != "FAILED":
                        detail["status_source"] = "failure_message"
                        detail["status_reported"] = status
                        status = refined
                elif status == "COMPLETED" and not (
                    isinstance(structured, dict)
                    and structured.get("consent") == "granted"
                ):
                    # A mailbox that let the agent talk comes back as a completed
                    # task. Counted as an interview it would raise the completion
                    # yield with a call nobody answered. A result that reports
                    # granted consent is never touched: no machine consents, and
                    # discarding a real interview is the more expensive error.
                    markers = _voicemail_markers(turns, self._evidence(latest))
                    if markers:
                        detail["status_source"] = "voicemail-heuristic"
                        detail["status_reported"] = status
                        detail["voicemail_markers"] = markers
                        status = "VOICEMAIL"

                return CallOutcome(
                    status=status,
                    run_id=run_id,
                    structured_result=structured,
                    detail=detail,
                    transcript=transcript,
                )
            if time.monotonic() >= deadline:
                raise TimeoutError("CALL-E status polling exceeded the configured timeout")
            time.sleep(self.poll_seconds)
