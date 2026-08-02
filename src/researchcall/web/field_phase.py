"""The dry-run field phase behind the workbench.

This does not re-implement fieldwork. It drives the existing pipeline —
``sampling.draw_sample``, ``runner.run_day``, ``reporting.build_report`` — one
record at a time so that a person watching has something to watch.

**The interface cannot place a real call.** No route here accepts a live flag and
no code path constructs the live client; the only transport it can reach is
``FixtureCallClient``. Placing an actual call stays with the command line and its
five-part gate, where the intent has to be typed out.
"""

from __future__ import annotations

import pathlib
import sqlite3
from collections import Counter
from importlib.resources import files
from typing import Any, Iterator

from .. import forms
from ..calls import FixtureCallClient
from ..database import connect, create_study, get_study, initialize
from ..questionnaire import load_questionnaire_file
from ..reporting import build_report
from ..runner import run_day
from ..sampling import DEFAULT_WINDOWS, draw_sample, import_frame_rows
from .workspace import Workspace


STUDY_KEY = "workbench"
DB_NAME = "fieldwork.db"
REPORT_NAME = "report.md"

# Frame rows generated for the dry run. The numbers are fictitious reserved-range
# values and never leave the local database; nothing here renders a number.
FRAME_FACTOR = 4
MIN_FRAME = 60


def _fixture(name: str) -> pathlib.Path:
    return pathlib.Path(str(files("researchcall").joinpath("fixtures", name)))


def database_path(workspace: Workspace) -> pathlib.Path:
    return workspace.path / DB_NAME


def report_path(workspace: Workspace) -> pathlib.Path:
    return workspace.path / REPORT_NAME


def _setting(workspace: Workspace, fields: list[forms.Field], path: str) -> Any:
    for field in fields:
        if field.path == path:
            return workspace.value(field)
    return None


def planned(workspace: Workspace, fields: list[forms.Field]) -> dict[str, Any]:
    """What the answered form definitions say this run should do."""
    size = _setting(workspace, fields, "sample.size")
    windows = _setting(workspace, fields, "sample.time_windows") or list(DEFAULT_WINDOWS)
    quota = _setting(workspace, fields, "contact_rules.daily_quota") or 50
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 0
    return {
        "size": max(0, size),
        "windows": [str(window) for window in windows if str(window).strip()],
        "quota": max(1, int(quota)),
    }


def exists(workspace: Workspace) -> bool:
    return database_path(workspace).exists()


def prepare(workspace: Workspace, fields: list[forms.Field], seed: int = 42) -> dict[str, int]:
    """Create the local study, a fictitious frame, and draw the sample."""
    plan = planned(workspace, fields)
    if plan["size"] <= 0:
        raise ValueError("sample.size must be set before the field phase")
    if not plan["windows"]:
        raise ValueError("sample.time_windows must name at least one window")

    workspace.path.mkdir(parents=True, exist_ok=True)
    path = database_path(workspace)
    if path.exists():
        path.unlink()

    initialize(path)
    questionnaire = load_questionnaire_file(_fixture("questionnaire.de.json"))
    connection = connect(path)
    try:
        study_id = create_study(connection, STUDY_KEY, questionnaire)
        connection.commit()
        frame_size = max(MIN_FRAME, plan["size"] * FRAME_FACTOR)
        rows = [
            (f"fictional-{index:04d}", f"+155500{index:05d}")
            for index in range(1, frame_size + 1)
        ]
        imported = import_frame_rows(connection, study_id, rows)
        drawn = draw_sample(
            connection, study_id, plan["size"], seed, tuple(plan["windows"])
        )
    finally:
        connection.close()
    return {"frame": imported, "drawn": drawn}


def open_database(workspace: Workspace) -> tuple[sqlite3.Connection, sqlite3.Row]:
    connection = connect(database_path(workspace))
    return connection, get_study(connection, STUDY_KEY)


def run(
    workspace: Workspace, fields: list[forms.Field]
) -> Iterator[dict[str, Any]]:
    """One record at a time, so progress is something other than a spinner.

    Yields a mapping per finished record and one final mapping with ``done``.
    """
    plan = planned(workspace, fields)
    client = FixtureCallClient.from_file(_fixture("outcomes.json"))
    connection, study = open_database(workspace)
    totals: Counter[str] = Counter()
    processed = 0
    try:
        for window in plan["windows"]:
            for _ in range(plan["quota"]):
                outcome = run_day(connection, study, window, 1, client)
                if not outcome:
                    break
                status = next(iter(outcome))
                totals[status] += 1
                processed += 1
                yield {
                    "index": processed,
                    "window": window,
                    "status": status,
                    "totals": dict(sorted(totals.items())),
                }
        yield {"done": True, "processed": processed, "totals": dict(sorted(totals.items()))}
    finally:
        connection.close()


def summary(workspace: Workspace) -> dict[str, Any]:
    """Counts for the report view, read from the same tables as the report."""
    if not exists(workspace):
        return {"ready": False}
    connection, study = open_database(workspace)
    try:
        rows = connection.execute(
            """
            SELECT s.time_window, s.excluded_at, a.call_status
            FROM sample s LEFT JOIN attempt a ON a.sample_id = s.id
            WHERE s.study_id = ?
            """,
            (study["id"],),
        ).fetchall()
        report = build_report(connection, study)
    finally:
        connection.close()

    included = [row for row in rows if row["excluded_at"] is None]
    statuses: Counter[str] = Counter(
        str(row["call_status"]) for row in included if row["call_status"]
    )
    by_window: dict[str, Counter[str]] = {}
    for row in included:
        window = str(row["time_window"])
        bucket = by_window.setdefault(window, Counter())
        bucket["drawn"] += 1
        if row["call_status"]:
            bucket[str(row["call_status"])] += 1
    return {
        "ready": True,
        "drawn": len(rows),
        "included": len(included),
        "withdrawn": len(rows) - len(included),
        "attempted": sum(statuses.values()),
        "completed": statuses.get("COMPLETED", 0),
        "statuses": dict(sorted(statuses.items())),
        "by_window": {name: dict(counts) for name, counts in sorted(by_window.items())},
        "report": report,
    }


def write_report(workspace: Workspace) -> pathlib.Path:
    connection, study = open_database(workspace)
    try:
        text = build_report(connection, study)
    finally:
        connection.close()
    target = report_path(workspace)
    target.write_text(text, encoding="utf-8")
    return target
