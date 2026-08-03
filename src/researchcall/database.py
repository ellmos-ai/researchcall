from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .huckepack_storage import open_connection


SCHEMA = """
CREATE TABLE IF NOT EXISTS study (
    id INTEGER PRIMARY KEY,
    study_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    questionnaire_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS frame (
    id INTEGER PRIMARY KEY,
    study_id INTEGER NOT NULL REFERENCES study(id) ON DELETE CASCADE,
    external_ref TEXT NOT NULL,
    phone_e164 TEXT,
    withdrawn_at TEXT,
    UNIQUE(study_id, external_ref)
);

CREATE TABLE IF NOT EXISTS sample (
    id INTEGER PRIMARY KEY,
    study_id INTEGER NOT NULL REFERENCES study(id) ON DELETE CASCADE,
    frame_id INTEGER NOT NULL REFERENCES frame(id) ON DELETE RESTRICT,
    time_window TEXT NOT NULL,
    assigned_window TEXT,
    drawn_at TEXT NOT NULL,
    excluded_at TEXT,
    exclusion_reason TEXT,
    UNIQUE(study_id, frame_id)
);

-- One row per attempt, not per person: a second attempt is a fact of its own,
-- with its own time and its own window. Collapsing it into the first would hide
-- exactly the bias that repeated contact introduces.
CREATE TABLE IF NOT EXISTS attempt (
    id INTEGER PRIMARY KEY,
    sample_id INTEGER NOT NULL REFERENCES sample(id) ON DELETE RESTRICT,
    attempt_no INTEGER NOT NULL DEFAULT 1,
    time_window TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    call_status TEXT NOT NULL,
    run_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    detail_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(sample_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS response (
    sample_id INTEGER PRIMARY KEY REFERENCES sample(id) ON DELETE CASCADE,
    structured_json TEXT NOT NULL,
    consent TEXT NOT NULL,
    asked_verbatim_reported INTEGER NOT NULL,
    wording_matches INTEGER NOT NULL,
    received_at TEXT NOT NULL
);

-- What the transport has actually proven it can do. 'untested' is a state of
-- its own, not a missing row: a capability nobody has probed must not read
-- like one that failed.
CREATE TABLE IF NOT EXISTS capability (
    name TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'untested',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    checked_at TEXT
);

-- One row per attempt whose after-call checks were not cleanly green. The
-- decision sits BESIDE the attempt, like a category beside its raw text: the
-- recorded disposition is never overwritten.
CREATE TABLE IF NOT EXISTS review (
    id INTEGER PRIMARY KEY,
    attempt_id INTEGER NOT NULL UNIQUE REFERENCES attempt(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    decision TEXT,
    note TEXT,
    decided_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sample_open
    ON sample(study_id, time_window, excluded_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_frame_unique_phone
    ON frame(study_id, phone_e164)
    WHERE phone_e164 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_attempt_status
    ON attempt(call_status);
CREATE INDEX IF NOT EXISTS idx_review_open
    ON review(decision) WHERE decision IS NULL;
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database this installation is supposed to use.

    Which one that is depends on the server mode: the file below, or the copy
    the browser sent for this session. See ``huckepack_storage``.
    """
    connection = open_connection(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def migrate(connection: sqlite3.Connection) -> list[str]:
    """Bring a database written by an earlier version up to the current shape.

    ``CREATE TABLE IF NOT EXISTS`` leaves an existing table exactly as it was, so
    a state file from before repeated attempts existed would silently keep its
    one-attempt-per-person constraint and fail at the worst moment — when a study
    is already running. The changes are additive and keep every recorded row.
    """
    applied: list[str] = []
    sample_columns = _columns(connection, "sample")
    if sample_columns and "assigned_window" not in sample_columns:
        connection.execute("ALTER TABLE sample ADD COLUMN assigned_window TEXT")
        connection.execute("UPDATE sample SET assigned_window = time_window")
        applied.append("sample.assigned_window")

    attempt_columns = _columns(connection, "attempt")
    if attempt_columns and "attempt_no" not in attempt_columns:
        connection.executescript(
            """
            ALTER TABLE attempt RENAME TO attempt_before_retries;
            CREATE TABLE attempt (
                id INTEGER PRIMARY KEY,
                sample_id INTEGER NOT NULL REFERENCES sample(id) ON DELETE RESTRICT,
                attempt_no INTEGER NOT NULL DEFAULT 1,
                time_window TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                call_status TEXT NOT NULL,
                run_id TEXT,
                idempotency_key TEXT NOT NULL UNIQUE,
                detail_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(sample_id, attempt_no)
            );
            INSERT INTO attempt(
                id, sample_id, attempt_no, time_window, started_at, ended_at,
                call_status, run_id, idempotency_key, detail_json
            )
            SELECT a.id, a.sample_id, 1, s.time_window, a.started_at, a.ended_at,
                   a.call_status, a.run_id, a.idempotency_key, a.detail_json
            FROM attempt_before_retries a JOIN sample s ON s.id = a.sample_id;
            DROP TABLE attempt_before_retries;
            """
        )
        applied.append("attempt.attempt_no")
    elif attempt_columns and "time_window" not in attempt_columns:
        connection.execute("ALTER TABLE attempt ADD COLUMN time_window TEXT")
        connection.execute(
            """
            UPDATE attempt SET time_window = (
                SELECT s.time_window FROM sample s WHERE s.id = attempt.sample_id
            )
            """
        )
        applied.append("attempt.time_window")

    existing_tables = {
        str(row["name"])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "study" in existing_tables and "capability" not in existing_tables:
        connection.execute(
            """
            CREATE TABLE capability (
                name TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'untested',
                evidence_json TEXT NOT NULL DEFAULT '{}',
                checked_at TEXT
            )
            """
        )
        applied.append("capability")
    if "study" in existing_tables and "review" not in existing_tables:
        connection.executescript(
            """
            CREATE TABLE review (
                id INTEGER PRIMARY KEY,
                attempt_id INTEGER NOT NULL UNIQUE REFERENCES attempt(id) ON DELETE CASCADE,
                reason TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                decision TEXT,
                note TEXT,
                decided_at TEXT
            );
            CREATE INDEX idx_review_open ON review(decision) WHERE decision IS NULL;
            """
        )
        applied.append("review")
    return applied


def initialize(path: str | Path) -> None:
    connection = connect(path)
    try:
        applied = migrate(connection)
        connection.executescript(SCHEMA)
        if applied:
            connection.commit()
        connection.commit()
    finally:
        connection.close()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def create_study(
    connection: sqlite3.Connection,
    study_key: str,
    questionnaire: dict[str, Any],
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO study(study_key, title, questionnaire_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            study_key,
            questionnaire["title"],
            json.dumps(questionnaire, ensure_ascii=False, separators=(",", ":")),
            utc_now(),
        ),
    )
    return int(cursor.lastrowid)


def get_study(connection: sqlite3.Connection, study_key: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM study WHERE study_key = ?", (study_key,)
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown study: {study_key}")
    return row


def load_questionnaire(study: sqlite3.Row) -> dict[str, Any]:
    value = json.loads(study["questionnaire_json"])
    if not isinstance(value, dict):
        raise ValueError("Stored questionnaire is not a JSON object")
    return value
