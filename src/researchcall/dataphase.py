"""The data phase: the dialed register, the seal, and documented corrections.

Three ideas, one file, because they answer the same question -- what may still
change once data exists, and what must never quietly change.

**The dialed register.** Every number that was ever dialled stays on record as
its own row, without any edge to the answers. Anonymisation cuts the
person-number link; it must not erase the fact that the number was called.
Follow-up planning needs the reconciliation -- original list, dialled,
unsuccessful, successful -- and a withdrawal needs the opposite guarantee:
that the number is remembered as do-not-call precisely because the person
asked to be left alone.

**The seal.** One deliberate cut, with grounds. Before it, the dataset is
being collected; after it, every change is an event in the change log, old
and new value side by side. Corrections stay possible -- refitting the data
quietly is what stops being possible.

**Corrections.** A miscoded answer may be fixed, with mandatory grounds. The
raw answer is never touched: it is what was said, and what was said does not
change because somebody coded it wrong.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .database import transaction, utc_now


# -- the dialed register ---------------------------------------------------


def record_dialed(
    connection: sqlite3.Connection, study_id: int, phone_e164: str, status: str
) -> None:
    """One row per number, updated on every attempt. Runs inside the caller's
    transaction, like the review filing: an attempt must not exist without its
    trace in the register."""
    now = utc_now()
    connection.execute(
        """
        INSERT INTO dialed(study_id, phone_e164, first_dialed_at, last_dialed_at, last_status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(study_id, phone_e164) DO UPDATE SET
            last_dialed_at = excluded.last_dialed_at,
            last_status = excluded.last_status
        """,
        (study_id, phone_e164, now, now, status),
    )


def mark_do_not_call(
    connection: sqlite3.Connection, study_id: int, phone_e164: str
) -> None:
    """A withdrawal keeps the number -- as the promise not to dial it again."""
    now = utc_now()
    connection.execute(
        """
        INSERT INTO dialed(study_id, phone_e164, first_dialed_at, last_dialed_at,
                           last_status, do_not_call)
        VALUES (?, ?, ?, ?, 'WITHDRAWN', 1)
        ON CONFLICT(study_id, phone_e164) DO UPDATE SET
            do_not_call = 1,
            last_status = 'WITHDRAWN',
            last_dialed_at = excluded.last_dialed_at
        """,
        (study_id, phone_e164, now, now),
    )


def dialed_register(connection: sqlite3.Connection, study_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT phone_e164, first_dialed_at, last_dialed_at, last_status, do_not_call
        FROM dialed WHERE study_id = ? ORDER BY first_dialed_at, phone_e164
        """,
        (study_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def reconciliation(connection: sqlite3.Connection, study_id: int) -> dict[str, int]:
    """Original list vs. dialled vs. outcome -- the counts a follow-up starts from."""
    frame_total = int(
        connection.execute(
            "SELECT COUNT(*) AS n FROM frame WHERE study_id = ?", (study_id,)
        ).fetchone()["n"]
    )
    register = dialed_register(connection, study_id)
    successful = sum(1 for row in register if row["last_status"] == "COMPLETED")
    do_not_call = sum(1 for row in register if row["do_not_call"])
    return {
        "frame_total": frame_total,
        "dialed": len(register),
        "not_yet_dialed": max(0, frame_total - len(register)),
        "successful": successful,
        "unsuccessful": len(register) - successful,
        "do_not_call": do_not_call,
    }


# -- the seal and the change log -------------------------------------------


def is_sealed(connection: sqlite3.Connection, study_id: int) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM seal WHERE study_id = ?", (study_id,)
        ).fetchone()
        is not None
    )


def seal_dataset(connection: sqlite3.Connection, study_id: int, note: str) -> None:
    if not note.strip():
        raise ValueError("Sealing requires a note: why is the dataset complete now?")
    if is_sealed(connection, study_id):
        raise ValueError("This dataset is already sealed; a seal is not renewed")
    with transaction(connection):
        connection.execute(
            "INSERT INTO seal(study_id, sealed_at, note) VALUES (?, ?, ?)",
            (study_id, utc_now(), note.strip()),
        )


def log_change(
    connection: sqlite3.Connection,
    study_id: int,
    target: str,
    field: str,
    old_value: Any,
    new_value: Any,
    reason: str,
    via: str = "web",
) -> None:
    """Runs inside the caller's transaction: change and log are one event."""
    connection.execute(
        """
        INSERT INTO change_log(study_id, at, target, field, old_value, new_value, reason, via)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            study_id,
            utc_now(),
            target,
            field,
            json.dumps(old_value, ensure_ascii=False),
            json.dumps(new_value, ensure_ascii=False),
            reason,
            via,
        ),
    )


def change_history(
    connection: sqlite3.Connection, study_id: int, target: str | None = None
) -> list[dict[str, Any]]:
    query = (
        "SELECT at, target, field, old_value, new_value, reason, via "
        "FROM change_log WHERE study_id = ?"
    )
    params: list[Any] = [study_id]
    if target is not None:
        query += " AND target = ?"
        params.append(target)
    query += " ORDER BY at, id"
    return [dict(row) for row in connection.execute(query, params).fetchall()]


# -- deliberate anonymisation ----------------------------------------------


def anonymise_deliberately(
    connection: sqlite3.Connection,
    study_id: int,
    external_ref: str,
    reason: str,
) -> None:
    """Cut the person-number edge, on purpose and on record.

    The number itself survives in the dialed register. What disappears is the
    link between it and this person's answers. The reason is mandatory because
    the step is irreversible and a follow-up study may still have needed the
    link -- whoever cuts it should have said why.
    """
    from .runner import _purge_frame  # late import to avoid a cycle

    if not reason.strip():
        raise ValueError(
            "Anonymisation requires a reason. A follow-up study may still need "
            "this link; whoever cuts it says why."
        )
    with transaction(connection):
        row = connection.execute(
            "SELECT id, phone_e164 FROM frame WHERE study_id = ? AND external_ref = ?",
            (study_id, external_ref),
        ).fetchone()
        if row is None:
            raise ValueError("No active frame row matches that external reference")
        phone = row["phone_e164"]
        if phone:
            # The register keeps the number; only the edge falls.
            record_dialed(connection, study_id, str(phone), "ANONYMISED")
        _purge_frame(connection, int(row["id"]), reason="ANONYMISED")
        log_change(
            connection,
            study_id,
            target=f"frame:{external_ref}",
            field="phone_link",
            old_value="linked",
            new_value="cut",
            reason=reason.strip(),
        )


# -- documented answer corrections -----------------------------------------


def correct_answer(
    connection: sqlite3.Connection,
    study_id: int,
    sample_id: int,
    question_id: str,
    new_category: str | None,
    reason: str,
) -> None:
    """Fix a coded category; never the raw words it was coded from.

    Works before and after the seal -- the difference is not permission but
    visibility, and visibility is provided here in both cases.
    """
    if not reason.strip():
        raise ValueError("A correction requires a reason")
    with transaction(connection):
        row = connection.execute(
            "SELECT structured_json FROM response WHERE sample_id = ?", (sample_id,)
        ).fetchone()
        if row is None:
            raise ValueError("No response is recorded for this sample")
        structured = json.loads(str(row["structured_json"]))
        answers = structured.get("answers", {})
        if question_id not in answers:
            raise ValueError(f"No answer is recorded for question '{question_id}'")
        old_value = answers[question_id]
        if old_value == new_category:
            raise ValueError("The correction changes nothing")
        answers[question_id] = new_category
        corrections = structured.setdefault("corrections", [])
        corrections.append(
            {"question": question_id, "from": old_value, "to": new_category, "at": utc_now()}
        )
        connection.execute(
            "UPDATE response SET structured_json = ? WHERE sample_id = ?",
            (json.dumps(structured, ensure_ascii=False, separators=(",", ":")), sample_id),
        )
        log_change(
            connection,
            study_id,
            target=f"response:{sample_id}",
            field=f"answers.{question_id}",
            old_value=old_value,
            new_value=new_category,
            reason=reason.strip(),
        )


# -- the call list ---------------------------------------------------------

CALL_STATUS_FILTERS = ("all", "not_attempted", "successful", "unsuccessful", "conflict")


def call_list(
    connection: sqlite3.Connection, study_id: int, status: str = "all"
) -> list[dict[str, Any]]:
    """Every drawn person with their latest attempt and their review state.

    'conflict' is a status of its own, derived from open review cases -- it is
    not a call outcome, it is the state of the paperwork about the call.
    """
    if status not in CALL_STATUS_FILTERS:
        raise ValueError(f"Unknown status filter: {status}")
    rows = connection.execute(
        """
        SELECT s.id AS sample_id, s.excluded_at, s.exclusion_reason,
               f.external_ref, f.phone_e164, f.withdrawn_at,
               a.id AS attempt_id, a.attempt_no, a.call_status, a.started_at,
               a.detail_json,
               r.id AS review_id, r.decision AS review_decision,
               r.reason AS review_reason, r.note AS review_note,
               r.decided_by AS review_decided_by
        FROM sample s
        JOIN frame f ON f.id = s.frame_id
        LEFT JOIN attempt a ON a.sample_id = s.id
            AND a.attempt_no = (
                SELECT MAX(attempt_no) FROM attempt WHERE sample_id = s.id
            )
        LEFT JOIN review r ON r.attempt_id = a.id
        WHERE s.study_id = ?
        ORDER BY s.id
        """,
        (study_id,),
    ).fetchall()

    entries = []
    for row in rows:
        call_status = row["call_status"]
        has_open_conflict = row["review_id"] is not None and row["review_decision"] is None
        if call_status is None:
            derived = "not_attempted"
        elif has_open_conflict:
            derived = "conflict"
        elif call_status == "COMPLETED":
            derived = "successful"
        else:
            derived = "unsuccessful"
        if status != "all" and derived != status:
            continue
        entries.append(
            {
                "sample_id": int(row["sample_id"]),
                "external_ref": str(row["external_ref"]),
                "withdrawn": row["withdrawn_at"] is not None,
                "attempt_no": row["attempt_no"],
                "call_status": call_status,
                "derived_status": derived,
                "started_at": row["started_at"],
                "review_id": row["review_id"],
                "review_decision": row["review_decision"],
                "review_reason": row["review_reason"],
                "review_note": row["review_note"],
                "review_decided_by": row["review_decided_by"],
                "excluded": row["excluded_at"] is not None,
            }
        )
    return entries


def call_detail(
    connection: sqlite3.Connection, study_id: int, sample_id: int
) -> dict[str, Any]:
    """Everything the mask shows: attempts, transcript, gates, checks, review."""
    sample = connection.execute(
        """
        SELECT s.id AS sample_id, s.excluded_at, s.exclusion_reason,
               f.external_ref, f.withdrawn_at
        FROM sample s JOIN frame f ON f.id = s.frame_id
        WHERE s.study_id = ? AND s.id = ?
        """,
        (study_id, sample_id),
    ).fetchone()
    if sample is None:
        raise ValueError("No sample with that id in this study")
    attempts = []
    for row in connection.execute(
        """
        SELECT a.id, a.attempt_no, a.call_status, a.started_at, a.ended_at,
               a.detail_json,
               r.id AS review_id, r.reason AS review_reason,
               r.decision AS review_decision, r.note AS review_note,
               r.decided_by AS review_decided_by
        FROM attempt a LEFT JOIN review r ON r.attempt_id = a.id
        WHERE a.sample_id = ? ORDER BY a.attempt_no
        """,
        (sample_id,),
    ).fetchall():
        detail = json.loads(str(row["detail_json"]))
        attempts.append(
            {
                "attempt_id": int(row["id"]),
                "attempt_no": int(row["attempt_no"]),
                "call_status": str(row["call_status"]),
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "transcript": detail.get("transcript"),
                "gates_seen": detail.get("gates_seen", []),
                "gates_missed": detail.get("gates_missed", []),
                "wording_matches": detail.get("transcript_wording_matches"),
                "schema_error": detail.get("structured_result_error"),
                "dispatch_mode": detail.get("dispatch_mode"),
                "review_id": row["review_id"],
                "review_reason": row["review_reason"],
                "review_decision": row["review_decision"],
                "review_note": row["review_note"],
                "review_decided_by": row["review_decided_by"],
            }
        )
    response = connection.execute(
        "SELECT structured_json, consent, wording_matches FROM response WHERE sample_id = ?",
        (sample_id,),
    ).fetchone()
    structured = json.loads(str(response["structured_json"])) if response else None
    return {
        "sample_id": int(sample["sample_id"]),
        "external_ref": str(sample["external_ref"]),
        "withdrawn": sample["withdrawn_at"] is not None,
        "excluded": sample["excluded_at"] is not None,
        "exclusion_reason": sample["exclusion_reason"],
        "attempts": attempts,
        "consent": response["consent"] if response else None,
        "answers": (structured or {}).get("answers"),
        "raw_answers": (structured or {}).get("raw_answers"),
        "corrections": (structured or {}).get("corrections", []),
        "changes": change_history(connection, study_id, target=f"response:{sample_id}"),
    }


def suggest_decision(reasons: list[str]) -> tuple[str, str]:
    """A proposal, clearly labelled as one. The person decides.

    Heuristic, and deliberately conservative: only a wording drift with every
    gate phrase seen suggests 'gate_passed'; everything structural suggests
    'dropout'. The suggestion never touches the database.
    """
    reason_set = set(reasons)
    if reason_set == {"wording_mismatch"}:
        return (
            "gate_passed",
            "only the wording drifted; if the transcript shows the meaning held, "
            "the call stands",
        )
    if "schema_error" in reason_set or "unclear_consent" in reason_set:
        return (
            "dropout",
            "a structurally unreadable or consent-unclear interview should not "
            "enter the completed count",
        )
    if "gate_missed" in reason_set:
        return (
            "dropout",
            "a required phrase was not seen; unless the transcript shows it "
            "fell, the interview is not clean",
        )
    return ("dropout", "no rule fits this combination; look closely")
