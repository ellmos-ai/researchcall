from __future__ import annotations

import json
import sqlite3
from collections import Counter
from typing import Any, Protocol

from .calls import CallOutcome, TERMINAL_STATUSES
from .database import load_questionnaire, transaction, utc_now
from .questionnaire import validate_structured_result, wording_matches
from .safety import idempotency_key, validate_e164


class CallClient(Protocol):
    def call(
        self,
        sample: dict[str, Any],
        questionnaire: dict[str, Any],
        idempotency_key: str,
    ) -> CallOutcome: ...


def _claim_next(
    connection: sqlite3.Connection,
    study: sqlite3.Row,
    time_window: str,
) -> dict[str, Any] | None:
    with transaction(connection):
        row = connection.execute(
            """
            SELECT s.id AS sample_id, s.time_window, f.id AS frame_id, f.phone_e164
            FROM sample s
            JOIN frame f ON f.id = s.frame_id
            LEFT JOIN attempt a ON a.sample_id = s.id
            WHERE s.study_id = ? AND s.time_window = ?
              AND s.excluded_at IS NULL AND f.withdrawn_at IS NULL AND a.id IS NULL
            ORDER BY s.id
            LIMIT 1
            """,
            (study["id"], time_window),
        ).fetchone()
        if row is None:
            return None
        phone = validate_e164(row["phone_e164"] or "")
        key = idempotency_key(study["study_key"], int(row["sample_id"]))
        started_at = utc_now()
        connection.execute(
            """
            INSERT INTO attempt(sample_id, started_at, call_status, idempotency_key)
            VALUES (?, ?, 'IN_PROGRESS', ?)
            """,
            (row["sample_id"], started_at, key),
        )
        return {
            "sample_id": int(row["sample_id"]),
            "frame_id": int(row["frame_id"]),
            "time_window": row["time_window"],
            "phone_e164": phone,
            "idempotency_key": key,
            "started_at": started_at,
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
    if structured is not None:
        try:
            validate_structured_result(questionnaire, structured)
            matches = wording_matches(questionnaire, structured)
        except ValueError as error:
            response_error = str(error)

    detail = dict(outcome.detail)
    if response_error:
        detail["structured_result_error"] = response_error
    with transaction(connection):
        connection.execute(
            """
            UPDATE attempt
            SET ended_at = ?, call_status = ?, run_id = ?, detail_json = ?
            WHERE sample_id = ?
            """,
            (
                utc_now(),
                outcome.status,
                outcome.run_id,
                json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
                sample["sample_id"],
            ),
        )
        if structured is not None and response_error is None:
            if structured["withdrawal_requested"]:
                _purge_frame(connection, sample["frame_id"])
            else:
                connection.execute(
                    """
                    INSERT INTO response(
                        sample_id, structured_json, consent,
                        asked_verbatim_reported, wording_matches, received_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
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


def _mark_local_failure(
    connection: sqlite3.Connection,
    sample_id: int,
    status: str,
    error: BaseException,
) -> None:
    with transaction(connection):
        connection.execute(
            """
            UPDATE attempt
            SET ended_at = ?, call_status = ?, detail_json = ?
            WHERE sample_id = ?
            """,
            (
                utc_now(),
                status,
                json.dumps(
                    {"transport_error": type(error).__name__}, separators=(",", ":")
                ),
                sample_id,
            ),
        )


def run_day(
    connection: sqlite3.Connection,
    study: sqlite3.Row,
    time_window: str,
    limit: int,
    client: CallClient,
) -> Counter[str]:
    if limit <= 0:
        raise ValueError("Daily quota must be positive")
    questionnaire = load_questionnaire(study)
    totals: Counter[str] = Counter()
    for _ in range(limit):
        sample = _claim_next(connection, study, time_window)
        if sample is None:
            break
        try:
            outcome = client.call(sample, questionnaire, sample["idempotency_key"])
            _finish_attempt(connection, sample, questionnaire, outcome)
        except KeyboardInterrupt as error:
            _mark_local_failure(connection, sample["sample_id"], "INTERRUPTED", error)
            raise
        except BaseException as error:
            _mark_local_failure(connection, sample["sample_id"], "FAILED", error)
            raise
        totals[outcome.status] += 1
    return totals

