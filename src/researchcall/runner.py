from __future__ import annotations

import dataclasses
import json
import re
import sqlite3
from collections import Counter
from typing import Any, Protocol

from .calls import CalleAPIError, CallOutcome, TERMINAL_STATUSES
from .coding import apply_unlisted_policy
from .database import load_questionnaire, transaction, utc_now
from .field_trial import marks as field_trial_marks
from .field_trial import routed as field_trial_routed
from .field_trial import trial_phone
from .instrument import for_call
from .phrases import audit_transcript, bot_utterances, phrases_from_questionnaire
from .questionnaire import (
    normalize_structured_result,
    validate_structured_result,
    wording_matches,
)
from .review import open_review, reasons_for_attempt
from .safety import idempotency_key, redact_phone_numbers, validate_e164


TRANSCRIPT_LINE_RE = re.compile(
    r"^\[(?P<minute>\d{2}):(?P<second>\d{2})\] (?P<speaker>BOT|USER): (?P<text>.*)$"
)

#: Outcomes that say "nobody was reachable", not "somebody said no". Only these
#: are repeated: a refusal that is dialled again is harassment, not fieldwork.
AVAILABILITY_STATUSES = frozenset({"NO_ANSWER", "BUSY", "VOICEMAIL"})

#: How many failures in a row end the run even when errors are tolerated.
MAX_CONSECUTIVE_FAILURES = 3


@dataclasses.dataclass(frozen=True)
class ContactRules:
    """How often, and under which conditions, a record may be dialled again.

    The default is the one the specification started from: every person exactly
    once. Repeated contact raises the yield and biases the sample towards people
    who are often at home, so it stays a decision somebody makes on purpose — and
    the report states the number that was actually reached that way.
    """

    attempts_per_person: int = 0          # *additional* attempts, 0 = one call
    callback_after_refusal_max: int = 0   # only for people who invited a callback
    spread_attempts: bool = True
    windows: tuple[str, ...] = ()
    stop_on_error: bool = False

    @property
    def max_attempts(self) -> int:
        return 1 + max(0, int(self.attempts_per_person))

    def next_window(self, current: str) -> str:
        if not self.spread_attempts or len(self.windows) < 2:
            return current
        try:
            index = self.windows.index(current)
        except ValueError:
            return self.windows[0]
        return self.windows[(index + 1) % len(self.windows)]


DEFAULT_RULES = ContactRules()


class CallClient(Protocol):
    def call(
        self,
        sample: dict[str, Any],
        questionnaire: dict[str, Any],
        idempotency_key: str,
    ) -> CallOutcome: ...


def _keeps_transcript(questionnaire: dict[str, Any]) -> bool:
    """Whether this study keeps the spoken words, per ``fieldwork.keep_transcript``.

    The switch is answered in the workbench and travels with the study in
    ``run_rules``. It defaults to keeping: a study drawn before the decision
    existed, or run from the command line without the workbench, gets the same
    behaviour as the form definition's own default.
    """
    rules = questionnaire.get("run_rules") or {}
    return bool(rules.get("keep_transcript", True))


#: How much of a rejected result is worth keeping. Enough to see the shape and
#: a few values, far too little to become a second copy of the interview.
REJECTED_RESULT_CHARS = 2000


def _rejected_shape(
    result: dict[str, Any], keep_values: bool, known_number: str = ""
) -> Any:
    """A rejected result, reduced to what a person needs to judge it."""
    if not keep_values:
        return {
            "fields": sorted(str(key) for key in result),
            "types": {str(key): type(value).__name__ for key, value in sorted(result.items())},
            "values_withheld": "fieldwork.keep_transcript is off",
        }
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)[
        :REJECTED_RESULT_CHARS
    ]
    return redact_phone_numbers(rendered, known_number)


def _detail_of(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _eligible(row: sqlite3.Row, rules: ContactRules, run_started_at: str) -> bool:
    """Whether this record may be dialled now."""
    attempts = int(row["attempts"] or 0)
    if attempts == 0:
        return True
    if attempts >= rules.max_attempts and row["last_status"] != "DECLINED":
        return False

    detail = _detail_of(row["last_detail"])
    if row["last_status"] == "DECLINED":
        callbacks = int(row["callbacks"] or 0)
        if not detail.get("callback_wanted") or callbacks >= max(
            0, int(rules.callback_after_refusal_max)
        ):
            return False
    elif row["last_status"] not in AVAILABILITY_STATUSES:
        return False
    if rules.spread_attempts:
        return True
    # Without spreading, a repeat would fall into the same time of day as the
    # attempt that just failed — which measures nothing new. It waits for the
    # next run, which the host triggers.
    return str(row["last_started_at"] or "") < run_started_at


def _claim_next(
    connection: sqlite3.Connection,
    study: sqlite3.Row,
    time_window: str,
    rules: ContactRules = DEFAULT_RULES,
    run_started_at: str = "",
    rehearsal: bool = False,
) -> dict[str, Any] | None:
    # Everyone gets a first call before anyone gets a second one. Two queries
    # rather than one keep that order cheap: the common case never looks at the
    # attempt history at all.
    chosen = connection.execute(
        """
        SELECT s.id AS sample_id, s.time_window, f.id AS frame_id, f.phone_e164
        FROM sample s
        JOIN frame f ON f.id = s.frame_id
        LEFT JOIN attempt a ON a.sample_id = s.id AND a.rehearsal = 0
        WHERE s.study_id = ? AND s.time_window = ?
          AND s.excluded_at IS NULL AND f.withdrawn_at IS NULL AND a.id IS NULL
        ORDER BY s.id
        LIMIT 1
        """,
        (study["id"], time_window),
    ).fetchone()

    if chosen is None and (rules.max_attempts > 1 or rules.callback_after_refusal_max > 0):
        candidates = connection.execute(
            """
            SELECT s.id AS sample_id, s.time_window, f.id AS frame_id, f.phone_e164,
                   (SELECT COUNT(*) FROM attempt a WHERE a.sample_id = s.id
                      AND a.rehearsal = 0) AS attempts,
                   (SELECT COUNT(*) FROM attempt a WHERE a.sample_id = s.id
                      AND a.rehearsal = 0 AND a.call_status = 'DECLINED') AS callbacks,
                   (SELECT a.call_status FROM attempt a WHERE a.sample_id = s.id
                      AND a.rehearsal = 0 ORDER BY a.attempt_no DESC LIMIT 1) AS last_status,
                   (SELECT a.detail_json FROM attempt a WHERE a.sample_id = s.id
                      AND a.rehearsal = 0 ORDER BY a.attempt_no DESC LIMIT 1) AS last_detail,
                   (SELECT a.started_at FROM attempt a WHERE a.sample_id = s.id
                      AND a.rehearsal = 0 ORDER BY a.attempt_no DESC LIMIT 1) AS last_started_at
            FROM sample s
            JOIN frame f ON f.id = s.frame_id
            WHERE s.study_id = ? AND s.time_window = ?
              AND s.excluded_at IS NULL AND f.withdrawn_at IS NULL
            ORDER BY attempts ASC, s.id ASC
            """,
            (study["id"], time_window),
        ).fetchall()
        chosen = next(
            (row for row in candidates if _eligible(row, rules, run_started_at)), None
        )
    if chosen is None:
        return None

    with transaction(connection):
        attempts = int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM attempt WHERE sample_id = ?",
                (chosen["sample_id"],),
            ).fetchone()["n"]
        )
        attempt_no = attempts + 1
        phone = validate_e164(chosen["phone_e164"] or "")
        key = idempotency_key(study["study_key"], int(chosen["sample_id"]), attempt_no)
        started_at = utc_now()
        connection.execute(
            """
            INSERT INTO attempt(
                sample_id, attempt_no, time_window, started_at, call_status,
                idempotency_key, rehearsal
            )
            VALUES (?, ?, ?, ?, 'IN_PROGRESS', ?, ?)
            """,
            (
                chosen["sample_id"],
                attempt_no,
                time_window,
                started_at,
                key,
                int(rehearsal),
            ),
        )
        attempt_id = int(
            connection.execute(
                "SELECT id FROM attempt WHERE sample_id = ? AND attempt_no = ?",
                (chosen["sample_id"], attempt_no),
            ).fetchone()["id"]
        )
        return {
            "sample_id": int(chosen["sample_id"]),
            "attempt_id": attempt_id,
            "attempt_no": attempt_no,
            "frame_id": int(chosen["frame_id"]),
            "study_id": int(study["id"]),
            "time_window": time_window,
            "phone_e164": phone,
            "idempotency_key": key,
            "started_at": started_at,
            "rehearsal": rehearsal,
        }


def _purge_frame(
    connection: sqlite3.Connection,
    frame_id: int,
    reason: str = "WITHDRAWN",
) -> None:
    now = utc_now()
    sample_ids = [
        int(row["id"])
        for row in connection.execute(
            "SELECT id FROM sample WHERE frame_id = ?", (frame_id,)
        ).fetchall()
    ]
    # A withdrawal keeps the NUMBER in the dialed register, marked do-not-call:
    # the person asked to be left alone, and forgetting the number would make
    # a follow-up round dial it again. Only the edge to their answers falls.
    frame_row = connection.execute(
        "SELECT study_id, phone_e164 FROM frame WHERE id = ?", (frame_id,)
    ).fetchone()
    if frame_row is not None and frame_row["phone_e164"] and reason == "WITHDRAWN":
        from .dataphase import mark_do_not_call

        mark_do_not_call(
            connection, int(frame_row["study_id"]), str(frame_row["phone_e164"])
        )
    connection.execute(
        """
        UPDATE frame
        SET external_ref = ?, phone_e164 = NULL, withdrawn_at = ?
        WHERE id = ?
        """,
        (f"withdrawn:{frame_id}", now, frame_id),
    )
    connection.execute(
        """
        UPDATE sample
        SET excluded_at = ?, exclusion_reason = ?
        WHERE frame_id = ?
        """,
        (now, reason, frame_id),
    )
    for sample_id in sample_ids:
        connection.execute("DELETE FROM response WHERE sample_id = ?", (sample_id,))
        connection.execute(
            """
            UPDATE attempt
            SET run_id = NULL, detail_json = '{"purged":true}'
            WHERE sample_id = ?
            """,
            (sample_id,),
        )


def withdraw_external_ref(
    connection: sqlite3.Connection, study_id: int, external_ref: str
) -> None:
    with transaction(connection):
        row = connection.execute(
            "SELECT id FROM frame WHERE study_id = ? AND external_ref = ?",
            (study_id, external_ref),
        ).fetchone()
        if row is None:
            raise ValueError("No active frame row matches that external reference")
        _purge_frame(connection, int(row["id"]))


def _finish_attempt(
    connection: sqlite3.Connection,
    sample: dict[str, Any],
    questionnaire: dict[str, Any],
    outcome: CallOutcome,
) -> None:
    if outcome.status not in TERMINAL_STATUSES:
        raise ValueError(f"Unsupported terminal status: {outcome.status}")

    structured = outcome.structured_result
    response_error: str | None = None
    matches = False
    coding_notes: list[dict[str, str]] = []
    if structured is None and outcome.status == "COMPLETED":
        # A completed call owes a result. Saying nothing about that would let a
        # call with no data at all look exactly like a clean one.
        response_error = "The call completed but returned no recipient result"
    if structured is not None:
        # Absence is the wire form, null the stored one: the schema the API
        # accepts has no "or null", so an unanswered entry arrives missing.
        # Filling it in here, before anything reads the result, keeps the coding
        # rule, the report and the export looking at one shape.
        structured = normalize_structured_result(questionnaire, structured)
        structured, coding_notes = apply_unlisted_policy(questionnaire, structured)
        try:
            validate_structured_result(questionnaire, structured)
            matches = wording_matches(questionnaire, structured)
        except ValueError as error:
            response_error = str(error)

    detail = dict(outcome.detail)
    detail.update(field_trial_marks(sample.get("field_trial_number")))
    if coding_notes:
        detail["coded_by_rule"] = coding_notes
    if structured is not None and response_error is None:
        if structured.get("refusal_reason"):
            detail["refusal_reason_recorded"] = True
        if structured.get("callback_wanted") is not None:
            detail["callback_wanted"] = bool(structured["callback_wanted"])
    if outcome.transcript is not None:
        transcript_lines = [
            line for line in outcome.transcript.splitlines() if line.strip()
        ]
        parsed_lines = [TRANSCRIPT_LINE_RE.fullmatch(line) for line in transcript_lines]
        format_valid = bool(parsed_lines) and all(match is not None for match in parsed_lines)
        detail["transcript_available"] = True
        detail["transcript_format"] = (
            "timestamped-speaker-lines" if format_valid else "unrecognized"
        )
        # The verbatim transcript is kept with the attempt, which is what the
        # review queue reads: a person judging a call sees the spoken words
        # beside the coded answer instead of a verdict alone. It travels with
        # the rest of the record, so a withdrawal erases it along with the
        # answers. Numbers are removed first — a transcript is the one place a
        # dialable number can arrive as spoken text.
        keep = _keeps_transcript(questionnaire)
        detail["transcript_persisted"] = keep
        if keep:
            text = redact_phone_numbers(
                outcome.transcript, str(sample.get("phone_e164") or "")
            )
            # In a field trial the line that was actually dialled is a real
            # person's private number, so it is named explicitly rather than
            # left to the shape rule.
            detail["transcript"] = redact_phone_numbers(
                text, str(sample.get("field_trial_number") or "")
            )
        if format_valid and structured is not None and response_error is None:
            # Joined, not per utterance: the agent splits a required sentence
            # over several turns (measured 2026-08-11), and checking each turn
            # on its own would call a character-identical sentence a deviation.
            # It stays a literal substring test — nothing is loosened but the
            # line break.
            spoken = " ".join(bot_utterances(outcome.transcript))
            expected_wording: list[str] = []
            if structured["consent"] != "not_obtained":
                expected_wording.append(questionnaire["consent_text"])
            expected_wording.extend(
                question["wording"]
                for question in questionnaire["questions"]
                if question.get("verbatim", True)
                and structured["spoken_wording"][question["id"]] is not None
            )
            detail["transcript_wording_matches"] = all(
                expected in spoken for expected in expected_wording
            )
    if response_error:
        detail["structured_result_error"] = response_error
        if outcome.structured_result is not None:
            # The one place foreign, unvalidated data is written into the
            # record: without it a rejection cannot be diagnosed at all, which
            # is how the first live call ended as an unanswerable question. It
            # is capped, numbers are stripped, and the answers themselves are
            # only kept where the study keeps transcripts anyway — otherwise
            # this path would smuggle back what that switch refuses.
            detail["structured_result_rejected"] = _rejected_shape(
                outcome.structured_result,
                keep_values=_keeps_transcript(questionnaire),
                known_number=str(sample.get("phone_e164") or ""),
            )

    # Gate phrases: literal recognition over whatever the call left to read.
    # Only run when a transcript exists — a fixture pattern without one has
    # nothing to recognise in, and inventing a verdict from absence is exactly
    # what the review queue is there to prevent.
    if outcome.transcript is not None and structured is not None:
        gate_findings = audit_transcript(
            outcome.transcript, phrases_from_questionnaire(questionnaire)
        )
        detail.update(gate_findings)

    with transaction(connection):
        connection.execute(
            """
            UPDATE attempt
            SET ended_at = ?, call_status = ?, run_id = ?, detail_json = ?
            WHERE id = ?
            """,
            (
                utc_now(),
                outcome.status,
                outcome.run_id,
                json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
                sample["attempt_id"],
            ),
        )
        if structured is not None and response_error is None:
            if structured["withdrawal_requested"] and not sample.get("rehearsal"):
                # A fixture's withdrawal is a rehearsal of one, not a person's
                # request: purging here would destroy the record before the real
                # call it was rehearsing for ever happened. The same reasoning as
                # in the field trial — a played part is not a wish.
                _purge_frame(connection, sample["frame_id"])
            else:
                connection.execute(
                    """
                    INSERT INTO response(
                        sample_id, structured_json, consent,
                        asked_verbatim_reported, wording_matches, received_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(sample_id) DO UPDATE SET
                        structured_json = excluded.structured_json,
                        consent = excluded.consent,
                        asked_verbatim_reported = excluded.asked_verbatim_reported,
                        wording_matches = excluded.wording_matches,
                        received_at = excluded.received_at
                    """,
                    (
                        sample["sample_id"],
                        json.dumps(structured, ensure_ascii=False, separators=(",", ":")),
                        structured["consent"],
                        int(structured["asked_verbatim"]),
                        int(matches),
                        utc_now(),
                    ),
                )
        # The dialed register: the number was called, and that fact survives
        # everything -- including a later anonymisation of the person.
        if (
            sample.get("phone_e164")
            and sample.get("study_id")
            and not sample.get("rehearsal")
        ):
            from .dataphase import record_dialed

            record_dialed(
                connection,
                int(sample["study_id"]),
                str(sample["phone_e164"]),
                outcome.status,
            )
        # File a review case if any after-call check was not cleanly green.
        # Inside the same transaction on purpose: an attempt must never be
        # recorded without the flag its own checks raised.
        open_review(
            connection,
            int(sample["attempt_id"]),
            reasons_for_attempt(
                call_status=outcome.status,
                detail=detail,
                wording_matches=(
                    matches if structured is not None and response_error is None else None
                ),
                response_error=response_error,
            ),
        )


def _release_attempt(connection: sqlite3.Connection, attempt_id: int) -> None:
    """Undo a claim for a call that never happened.

    The row is written before the request so an interruption cannot make the
    same person eligible twice. When the service refuses before dialling — no
    balance, bad key, rate limit — that reasoning turns around: nobody was
    called, nothing was spent, and leaving the claim would spend the person on
    an attempt that never existed.
    """
    with transaction(connection):
        connection.execute("DELETE FROM attempt WHERE id = ?", (attempt_id,))


def _mark_local_failure(
    connection: sqlite3.Connection,
    attempt_id: int,
    status: str,
    error: BaseException,
) -> None:
    with transaction(connection):
        connection.execute(
            """
            UPDATE attempt
            SET ended_at = ?, call_status = ?, detail_json = ?
            WHERE id = ?
            """,
            (
                utc_now(),
                status,
                json.dumps(
                    {
                        "transport_error": type(error).__name__,
                        **(
                            error.as_detail()
                            if isinstance(error, CalleAPIError)
                            else {}
                        ),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                attempt_id,
            ),
        )


def _requeue(
    connection: sqlite3.Connection,
    sample: dict[str, Any],
    status: str,
    rules: ContactRules,
) -> str | None:
    """Move a record that may be dialled again into another time of day.

    Returns the new window, or None when the record stays where it is. The window
    a record was *drawn* into is never overwritten — ``sample.assigned_window``
    keeps it, so the report can still show the draw as it was made.
    """
    if status == "DECLINED":
        # "Call me another time" means another time. Leaving the record where it
        # is would dial the same time of day again, which is not what was agreed.
        if rules.callback_after_refusal_max <= 0:
            return None
    elif status not in AVAILABILITY_STATUSES or rules.max_attempts <= 1:
        return None
    target = rules.next_window(str(sample["time_window"]))
    if target == sample["time_window"]:
        return None
    with transaction(connection):
        connection.execute(
            "UPDATE sample SET time_window = ? WHERE id = ?",
            (target, sample["sample_id"]),
        )
    return target


def run_day(
    connection: sqlite3.Connection,
    study: sqlite3.Row,
    time_window: str,
    limit: int,
    client: CallClient,
    rules: ContactRules = DEFAULT_RULES,
    rehearsal: bool = False,
) -> Counter[str]:
    """One day's calls. ``rehearsal`` exercises everything without spending a person."""
    if limit <= 0:
        raise ValueError("Daily quota must be positive")
    # Read once, before a single record is claimed: a set-but-unusable trial
    # number must stop the run at the start, not halfway through it.
    field_trial_number = trial_phone()
    questionnaire = load_questionnaire(study)
    run_started_at = utc_now()
    totals: Counter[str] = Counter()
    consecutive_failures = 0
    for _ in range(limit):
        sample = _claim_next(
            connection, study, time_window, rules, run_started_at, rehearsal
        )
        if sample is None:
            break
        sample["field_trial_number"] = field_trial_number
        try:
            outcome = client.call(
                field_trial_routed(sample, field_trial_number),
                for_call(questionnaire, sample["sample_id"]),
                sample["idempotency_key"],
            )
            _finish_attempt(connection, sample, questionnaire, outcome)
        except CalleAPIError as error:
            if error.dialled:
                _mark_local_failure(connection, sample["attempt_id"], "FAILED", error)
            else:
                _release_attempt(connection, sample["attempt_id"])
            # Either way the run stops: a refusal repeats itself, and working
            # through the rest of the quota only turns one problem into many.
            raise
        except KeyboardInterrupt as error:
            _mark_local_failure(connection, sample["attempt_id"], "INTERRUPTED", error)
            raise
        except BaseException as error:
            _mark_local_failure(connection, sample["attempt_id"], "FAILED", error)
            if rules.stop_on_error or not isinstance(error, Exception):
                raise
            totals["FAILED"] += 1
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                # One broken record is a record. Three in a row is a broken setup,
                # and working through the rest of the quota would cost real calls
                # to find that out.
                raise
            continue
        consecutive_failures = 0
        totals[outcome.status] += 1
        _requeue(connection, sample, outcome.status, rules)
    return totals
