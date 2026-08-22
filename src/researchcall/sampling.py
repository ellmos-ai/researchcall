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


def read_xlsx_frame(
    path: str | Path, id_column: str, phone_column: str
) -> list[tuple[str, str]]:
    """Read the first worksheet of an .xlsx file, header row first.

    Researchers get their frames from sampling vendors or their own tools, and
    those tools speak Excel. The reader is standard-library only (an .xlsx file
    is a zip of XML), because a parsing dependency for two columns of text
    would be the tail wagging the dog. Deliberately narrow: first sheet, shared
    or inline strings, no formulas evaluated — a frame is a list, not a model.
    """
    import re as _re
    import zipfile
    from xml.etree import ElementTree

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(Path(path)) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", ns):
                shared.append("".join(node.text or "" for node in item.iter() if node.text))
        sheet_names = sorted(
            name
            for name in archive.namelist()
            if _re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
        )
        if not sheet_names:
            raise ValueError("The .xlsx file contains no worksheet")
        root = ElementTree.fromstring(archive.read(sheet_names[0]))

    def cell_text(cell: ElementTree.Element) -> str:
        kind = cell.get("t", "")
        if kind == "s":
            value = cell.find("m:v", ns)
            index = int(value.text) if value is not None and value.text else -1
            return shared[index] if 0 <= index < len(shared) else ""
        if kind == "inlineStr":
            return "".join(
                node.text or "" for node in cell.iter() if node.text
            ).strip()
        value = cell.find("m:v", ns)
        return (value.text or "") if value is not None else ""

    def column_of(reference: str) -> int:
        letters = "".join(char for char in reference if char.isalpha())
        index = 0
        for char in letters:
            index = index * 26 + (ord(char.upper()) - ord("A") + 1)
        return index - 1

    table: list[list[str]] = []
    for row in root.findall(".//m:row", ns):
        cells: dict[int, str] = {}
        for cell in row.findall("m:c", ns):
            cells[column_of(cell.get("r", "A1"))] = cell_text(cell).strip()
        width = max(cells) + 1 if cells else 0
        table.append([cells.get(i, "") for i in range(width)])

    if not table or not any(table[0]):
        raise ValueError("Frame .xlsx needs a header row")
    header = [value.strip() for value in table[0]]
    missing = {id_column, phone_column} - set(header)
    if missing:
        raise ValueError("Frame .xlsx is missing columns: " + ", ".join(sorted(missing)))
    id_index = header.index(id_column)
    phone_index = header.index(phone_column)
    rows = []
    for line in table[1:]:
        if not any(value.strip() for value in line):
            continue        # a trailing empty row is not a participant
        ref = line[id_index] if id_index < len(line) else ""
        phone = line[phone_index] if phone_index < len(line) else ""
        rows.append((ref.strip(), phone.strip()))
    return rows


def read_frame_file(
    path: str | Path, id_column: str, phone_column: str
) -> list[tuple[str, str]]:
    """CSV or .xlsx, decided by the file itself, not by its name alone."""
    file_path = Path(path)
    if file_path.suffix.lower() == ".xlsx":
        return read_xlsx_frame(file_path, id_column, phone_column)
    return read_csv_frame(file_path, id_column, phone_column)


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


#: The join every frame query needing the do-not-call guard shares, so the two
#: places that decide who may still be drawn cannot silently drift apart.
#:
#: Measured live 2026-08-22 (Endabnahme, befund RC7): the guard checked only
#: whether THIS frame row had been withdrawn (``frame.withdrawn_at``), never
#: whether the NUMBER itself was already marked ``do_not_call`` in the
#: ``dialed`` register. A number that withdrew and was later re-imported —
#: a second field day, a corrected frame file — arrived as a fresh frame row
#: with ``withdrawn_at IS NULL`` and was dialable again. ``dialed`` carries at
#: most one row per ``(study_id, phone_e164)`` (``UNIQUE`` constraint,
#: :func:`researchcall.dataphase.mark_do_not_call`), so the guard is a NUMBER
#: check by construction — no aggregation across rows is needed, only the
#: join.
_DO_NOT_CALL_JOIN = """
    LEFT JOIN dialed d ON d.study_id = f.study_id AND d.phone_e164 = f.phone_e164
"""
_DO_NOT_CALL_CLAUSE = "AND (d.do_not_call IS NULL OR d.do_not_call = 0)"


def eligible_count(connection: sqlite3.Connection, study_id: int) -> int:
    """How many frame rows could still be drawn — the size of a census."""
    row = connection.execute(
        f"""
        SELECT COUNT(*) AS n
        FROM frame f
        LEFT JOIN sample s ON s.study_id = f.study_id AND s.frame_id = f.id
        {_DO_NOT_CALL_JOIN}
        WHERE f.study_id = ? AND f.withdrawn_at IS NULL AND s.id IS NULL
        {_DO_NOT_CALL_CLAUSE}
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
        f"""
        SELECT f.id
        FROM frame f
        LEFT JOIN sample s ON s.study_id = f.study_id AND s.frame_id = f.id
        {_DO_NOT_CALL_JOIN}
        WHERE f.study_id = ? AND f.withdrawn_at IS NULL AND s.id IS NULL
        {_DO_NOT_CALL_CLAUSE}
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
