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
) -> None:
    """Close a case. The note is mandatory: a ruling without grounds is a shrug.

    ``dropout`` and ``excluded`` also mark the sample, so the reporting
    denominators see the ruling — but the attempt row itself stays exactly as
    the call left it.
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
            "UPDATE review SET decision = ?, note = ?, decided_at = ? WHERE id = ?",
            (decision.value, note.strip(), utc_now(), review_id),
        )
        if decision in (ReviewDecision.DROPOUT, ReviewDecision.EXCLUDED):
            connection.execute(
                """
                UPDATE sample SET excluded_at = ?, exclusion_reason = ?
                WHERE id = ? AND excluded_at IS NULL
                """,
                (utc_now(), f"review:{decision.value}", int(row["sample_id"])),
            )


def guard_aggregation(connection: sqlite3.Connection, study_id: int) -> None:
    """Refuse to aggregate over undecided conflicts."""
    count = open_case_count(connection, study_id)
    if count:
        raise ValueError(
            f"{count} review case(s) are still open; the aggregate would contain "
            f"exactly the numbers the review exists to protect. Decide them first."
        )
