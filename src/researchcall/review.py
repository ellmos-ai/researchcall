"""The conflict queue: calls whose after-call checks were not cleanly green.

Automated checks can only say "this needs a person", never "this is fine
anyway". A call whose wording drifted, whose structured answer failed
validation, or whose consent line is unclear must not slide into the dataset by
default — and must not be silently dropped either. Both would be decisions, and
they belong to someone who looked.

So every such attempt lands here, as an open row. A person opens the case,
sees transcript, gate findings and structured answer side by side, and decides:
``gate_passed`` (the conversation was fine, the flag was overcautious),
``dropout`` (the case leaves the completed count) or ``excluded`` (the case
leaves the denominators, like an ineligible). The decision is written WITH a
note, and the attempt's own record is never overwritten — the ruling sits
beside the evidence, the way a category sits beside its raw text.

The transcript is really there to read: since the user decision of 2026-08-11 it
is stored with the attempt, and ``fieldwork.keep_transcript`` decides it per
study. Switched off, the case still opens — the reviewer then judges the flags
without the spoken words, which is a weaker position and a deliberate one.

Aggregation refuses to run while cases are open. A report over undecided
conflicts would present exactly the numbers the review exists to protect.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .database import transaction, utc_now


class ReviewReason(str, Enum):
    WORDING_MISMATCH = "wording_mismatch"
    SCHEMA_ERROR = "schema_error"
    UNCLEAR_CONSENT = "unclear_consent"
    GATE_MISSED = "gate_missed"
    #: A sentence the floor owes was skipped — not a gate, but not optional
    #: either. Kept apart from GATE_MISSED so a reviewer sees at a glance
    #: whether an ethics phrase or a scope/deletion promise went missing.
    FLOOR_MISSED = "floor_missed"
    MANUAL_FLAG = "manual_flag"


class ReviewDecision(str, Enum):
    GATE_PASSED = "gate_passed"
    DROPOUT = "dropout"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class ReviewCase:
    id: int
    attempt_id: int
    reason: str
    opened_at: str
    decision: str | None
    note: str | None
    decided_at: str | None


def reasons_for_attempt(
    call_status: str,
    detail: dict[str, Any],
    wording_matches: bool | None,
    response_error: str | None,
) -> list[ReviewReason]:
    """Which findings of the after-call checks demand a human look.

    The list is derived from recorded facts only. Nothing here interprets the
    conversation — it interprets the checks.
    """
    reasons: list[ReviewReason] = []
    if response_error is not None:
        reasons.append(ReviewReason.SCHEMA_ERROR)
    if wording_matches is False:
        reasons.append(ReviewReason.WORDING_MISMATCH)
    if detail.get("consent_unclear"):
        reasons.append(ReviewReason.UNCLEAR_CONSENT)
    if detail.get("gates_missed"):
        reasons.append(ReviewReason.GATE_MISSED)
    if detail.get("floor_missing"):
        reasons.append(ReviewReason.FLOOR_MISSED)
    return reasons


def open_review(
    connection: sqlite3.Connection, attempt_id: int, reasons: list[ReviewReason]
) -> None:
    """File one case per attempt, carrying every reason at once.

    Re-filing the same attempt keeps the first opening time — a case does not
    become younger by being flagged again — but the reasons are merged, so a
    later finding is not lost.
    """
    if not reasons:
        return
    joined = ",".join(sorted({reason.value for reason in reasons}))
    existing = connection.execute(
        "SELECT id, reason FROM review WHERE attempt_id = ?", (attempt_id,)
    ).fetchone()
    if existing is None:
        connection.execute(
            "INSERT INTO review(attempt_id, reason, opened_at) VALUES (?, ?, ?)",
            (attempt_id, joined, utc_now()),
        )
        return
    merged = ",".join(sorted(set(str(existing["reason"]).split(",")) | set(joined.split(","))))
    connection.execute(
        "UPDATE review SET reason = ? WHERE id = ?", (merged, int(existing["id"]))
    )


def open_cases(connection: sqlite3.Connection, study_id: int) -> list[dict[str, Any]]:
    """Every undecided case of this study, with what a reviewer needs to look."""
    rows = connection.execute(
        """
        SELECT r.id, r.attempt_id, r.reason, r.opened_at,
               a.call_status, a.attempt_no, a.detail_json,
               s.id AS sample_id
        FROM review r
        JOIN attempt a ON a.id = r.attempt_id
        JOIN sample s ON s.id = a.sample_id
        WHERE s.study_id = ? AND r.decision IS NULL
        ORDER BY r.opened_at, r.id
        """,
        (study_id,),
    ).fetchall()
    cases = []
    for row in rows:
        detail = json.loads(str(row["detail_json"]))
        cases.append(
            {
                "review_id": int(row["id"]),
                "attempt_id": int(row["attempt_id"]),
                "sample_id": int(row["sample_id"]),
                "attempt_no": int(row["attempt_no"]),
                "reasons": str(row["reason"]).split(","),
                "opened_at": str(row["opened_at"]),
                "call_status": str(row["call_status"]),
                "transcript": detail.get("transcript"),
                "gates_missed": detail.get("gates_missed", []),
                "gates_seen": detail.get("gates_seen", []),
            }
        )
    return cases


def open_case_count(connection: sqlite3.Connection, study_id: int) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS open_count
        FROM review r
        JOIN attempt a ON a.id = r.attempt_id
        JOIN sample s ON s.id = a.sample_id
        WHERE s.study_id = ? AND r.decision IS NULL
        """,
        (study_id,),
    ).fetchone()
    return int(row["open_count"])


def decide(
    connection: sqlite3.Connection,
    review_id: int,
    decision: ReviewDecision,
    note: str,
    decided_by: str = "manual",
) -> None:
    """Close a case. The note is mandatory: a ruling without grounds is a shrug.

    ``dropout`` and ``excluded`` also mark the sample, so the reporting
    denominators see the ruling — but the attempt row itself stays exactly as
    the call left it. ``decided_by`` records whether a person looked or a rule
    ran; the report tells the two apart.
    """
    if not note.strip():
        raise ValueError("A review decision requires a note explaining it")
    with transaction(connection):
        row = connection.execute(
            """
            SELECT r.id, r.decision, a.sample_id
            FROM review r JOIN attempt a ON a.id = r.attempt_id
            WHERE r.id = ?
            """,
            (review_id,),
        ).fetchone()
        if row is None:
            raise ValueError("No review case with that id")
        if row["decision"] is not None:
            raise ValueError("This case is already decided; decisions are not rewritten")
        connection.execute(
            "UPDATE review SET decision = ?, note = ?, decided_at = ?, decided_by = ? "
            "WHERE id = ?",
            (decision.value, note.strip(), utc_now(), decided_by, review_id),
        )
        if decision in (ReviewDecision.DROPOUT, ReviewDecision.EXCLUDED):
            connection.execute(
                """
                UPDATE sample SET excluded_at = ?, exclusion_reason = ?
                WHERE id = ? AND excluded_at IS NULL
                """,
                (utc_now(), f"review:{decision.value}", int(row["sample_id"])),
            )


RULE_DECISIONS = (ReviewDecision.DROPOUT, ReviewDecision.EXCLUDED)


def decide_all_by_rule(
    connection: sqlite3.Connection,
    study_id: int,
    decision: ReviewDecision,
    note: str,
) -> int:
    """Apply one default rule to every open case of a study.

    Only the conservative rulings exist as rules. A rule that passes every
    conflict would make the queue decorative — 'gate_passed' stays a decision
    somebody takes while looking at one case. Each closure is recorded with
    ``decided_by='rule'`` so the report can say how many conflicts a person
    actually looked at.
    """
    if decision not in RULE_DECISIONS:
        raise ValueError(
            "A default rule can only drop out or exclude; passing a gate is a "
            "decision a person takes while looking at the case"
        )
    if not note.strip():
        raise ValueError("A rule run requires a note explaining why it applies")
    closed = 0
    for case in open_cases(connection, study_id):
        decide(connection, int(case["review_id"]), decision, note, decided_by="rule")
        closed += 1
    return closed


def flag_manually(
    connection: sqlite3.Connection, attempt_id: int, note: str
) -> None:
    """Turn a green call into a conflict, on grounds.

    The automatic checks can only see what they measure. A person reading the
    transcript may see more — and their objection enters the same queue as
    every automatic one, with the grounds stored and shown again on reopening.
    """
    if not note.strip():
        raise ValueError("Flagging a call as a conflict requires grounds")
    with transaction(connection):
        existing = connection.execute(
            "SELECT id, decision, note FROM review WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
        if existing is not None and existing["decision"] is not None:
            raise ValueError(
                "This attempt already carries a decided case; decisions are not reopened"
            )
        open_review(connection, attempt_id, [ReviewReason.MANUAL_FLAG])
        row = connection.execute(
            "SELECT id, note FROM review WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
        merged = (str(row["note"]) + "\n" if row["note"] else "") + note.strip()
        connection.execute(
            "UPDATE review SET note = ? WHERE id = ?", (merged, int(row["id"]))
        )


def guard_aggregation(connection: sqlite3.Connection, study_id: int) -> None:
    """Refuse to aggregate over undecided conflicts."""
    count = open_case_count(connection, study_id)
    if count:
        raise ValueError(
            f"{count} review case(s) are still open; the aggregate would contain "
            f"exactly the numbers the review exists to protect. Decide them first."
        )
