from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


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
    drawn_at TEXT NOT NULL,
    excluded_at TEXT,
    exclusion_reason TEXT,
    UNIQUE(study_id, frame_id)
);

CREATE TABLE IF NOT EXISTS attempt (
    id INTEGER PRIMARY KEY,
    sample_id INTEGER NOT NULL UNIQUE REFERENCES sample(id) ON DELETE RESTRICT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    call_status TEXT NOT NULL,
    run_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    detail_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS response (
    sample_id INTEGER PRIMARY KEY REFERENCES sample(id) ON DELETE CASCADE,
    structured_json TEXT NOT NULL,
    consent TEXT NOT NULL,
    asked_verbatim_reported INTEGER NOT NULL,
    wording_matches INTEGER NOT NULL,
    received_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sample_open
    ON sample(study_id, time_window, excluded_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_frame_unique_phone
    ON frame(study_id, phone_e164)
    WHERE phone_e164 IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_attempt_status
    ON attempt(call_status);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize(path: str | Path) -> None:
    connection = connect(path)
    try:
        connection.executescript(SCHEMA)
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
