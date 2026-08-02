from __future__ import annotations

import csv
import random
import sqlite3
from pathlib import Path
from typing import Iterable

from .database import transaction, utc_now
from .safety import validate_e164


DEFAULT_WINDOWS = ("morning", "afternoon", "evening")


def read_csv_frame(
    path: str | Path, id_column: str, phone_column: str
) -> list[tuple[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Frame CSV needs a header row")
        missing = {id_column, phone_column} - set(reader.fieldnames)
        if missing:
            raise ValueError("Frame CSV is missing columns: " + ", ".join(sorted(missing)))
        return [(str(row[id_column]).strip(), str(row[phone_column]).strip()) for row in reader]


def read_sqlite_frame(
    path: str | Path,
    table: str,
    id_column: str,
    phone_column: str,
) -> list[tuple[str, str]]:
    if not table.replace("_", "").isalnum():
        raise ValueError("SQLite table name contains unsupported characters")
    for column in (id_column, phone_column):
        if not column.replace("_", "").isalnum():
            raise ValueError("SQLite column name contains unsupported characters")
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            f'SELECT "{id_column}", "{phone_column}" FROM "{table}"'
        ).fetchall()
    finally:
        connection.close()
    return [(str(row[0]).strip(), str(row[1]).strip()) for row in rows]


def import_frame_rows(
    connection: sqlite3.Connection,
    study_id: int,
    rows: Iterable[tuple[str, str]],
) -> int:
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    seen_phones: set[str] = set()
    for external_ref, phone in rows:
        if not external_ref:
            raise ValueError("Every frame row needs an external reference")
        if external_ref in seen:
            raise ValueError(f"Duplicate external reference in input: {external_ref}")
        seen.add(external_ref)
        normalized_phone = validate_e164(phone)
        if normalized_phone in seen_phones:
            raise ValueError("Duplicate phone number in frame input")
        seen_phones.add(normalized_phone)
        normalized.append((external_ref, normalized_phone))
    if not normalized:
        raise ValueError("Frame source contains no rows")

    with transaction(connection):
        connection.executemany(
            "INSERT INTO frame(study_id, external_ref, phone_e164) VALUES (?, ?, ?)",
            [(study_id, external_ref, phone) for external_ref, phone in normalized],
        )
    return len(normalized)


def eligible_count(connection: sqlite3.Connection, study_id: int) -> int:
    """How many frame rows could still be drawn — the size of a census."""
    row = connection.execute(
        """
        SELECT COUNT(*) AS n
        FROM frame f
        LEFT JOIN sample s ON s.study_id = f.study_id AND s.frame_id = f.id
        WHERE f.study_id = ? AND f.withdrawn_at IS NULL AND s.id IS NULL
        """,
        (study_id,),
    ).fetchone()
    return int(row["n"])


def draw_sample(
    connection: sqlite3.Connection,
    study_id: int,
    count: int,
    seed: int,
    windows: tuple[str, ...] = DEFAULT_WINDOWS,
    assign_randomly: bool = True,
) -> int:
    """Draw ``count`` records and give each one a time of day.

    The time window is part of the draw, not of the dialling: assigning it by lot
    turns the time of day into a controlled variable instead of a silent
    preselection of whoever happens to be at home when the run starts. Assigning
    in equal blocks instead (``assign_randomly=False``) gives exactly balanced
    windows and is the better choice for a small sample, where chance alone can
    leave one window nearly empty.
    """
    if count <= 0:
        raise ValueError("Sample count must be positive")
    if not windows or any(not window.strip() for window in windows):
        raise ValueError("At least one non-empty time window is required")
    if len(set(windows)) != len(windows):
        raise ValueError("Time windows must be unique")

    candidates = connection.execute(
        """
        SELECT f.id
        FROM frame f
        LEFT JOIN sample s ON s.study_id = f.study_id AND s.frame_id = f.id
        WHERE f.study_id = ? AND f.withdrawn_at IS NULL AND s.id IS NULL
        ORDER BY f.id
        """,
        (study_id,),
    ).fetchall()
    if count > len(candidates):
        raise ValueError(
            f"Requested {count} sample rows but only {len(candidates)} are eligible"
        )

    rng = random.Random(seed)
    selected = rng.sample([int(row["id"]) for row in candidates], count)
    drawn_at = utc_now()
    if assign_randomly:
        assigned = [(frame_id, rng.choice(windows)) for frame_id in selected]
    else:
        assigned = [
            (frame_id, windows[index % len(windows)])
            for index, frame_id in enumerate(selected)
        ]
    with transaction(connection):
        connection.executemany(
            """
            INSERT INTO sample(study_id, frame_id, time_window, assigned_window, drawn_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (study_id, frame_id, window, window, drawn_at)
                for frame_id, window in assigned
            ],
        )
    return len(assigned)
