"""The dry-run field phase behind the workbench.

This does not re-implement fieldwork. It drives the existing pipeline —
``instrument.build_questionnaire``, ``sampling.draw_sample``, ``runner.run_day``,
``reporting.build_report`` — one record at a time so that a person watching has
something to watch.

What changed with this round: the questionnaire is no longer a fixture. It is
built from the answers given in station 1 to 4, so the run asks the questions the
researcher wrote, in the order the instrument prescribes, inside the conversation
frame station 3 defines. Only the *transport* stays a fixture.

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

from .. import forms, instrument
from ..calls import FixtureCallClient
from ..database import connect, create_study, get_study, initialize
from ..reporting import build_report, collect
from ..runner import ContactRules, run_day
from ..sampling import DEFAULT_WINDOWS, draw_sample, eligible_count, import_frame_rows
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


def values_of(workspace: Workspace, fields: list[forms.Field]) -> dict[str, Any]:
    """Every answered setting as a flat mapping — defaults included."""
    return {field.path: workspace.value(field) for field in fields}


def rules_of(workspace: Workspace, fields: list[forms.Field]) -> ContactRules:
    values = values_of(workspace, fields)
    windows = [
        str(window)
        for window in (values.get("sample.time_windows") or DEFAULT_WINDOWS)
        if str(window).strip()
    ]

    def number(path: str, fallback: int) -> int:
        try:
            return int(values.get(path))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return fallback

    return ContactRules(
        attempts_per_person=max(0, number("contact_rules.attempts_per_person", 0)),
        callback_after_refusal_max=max(0, number("contact_rules.callback_after_refusal_max", 0))
        if values.get("ethics.on_refusal.offer_callback", True)
        else 0,
        spread_attempts=bool(values.get("contact_rules.spread_attempts", True)),
        windows=tuple(windows or DEFAULT_WINDOWS),
        stop_on_error=bool(values.get("fieldwork.stop_on_error", False)),
    )


def build(
    workspace: Workspace, fields: list[forms.Field], language: str = "de"
) -> tuple[dict[str, Any], list[instrument.Problem]]:
    """The questionnaire this workspace describes, plus what could not be read."""
    values = values_of(workspace, fields)
    questionnaire, problems = instrument.build_questionnaire(values, language)
    rules = rules_of(workspace, fields)
    # Recorded with the study so the report can hold the intention against the
    # outcome: how many repeats were allowed, and how many actually happened.
    questionnaire["run_rules"] = {
        "attempts_per_person": rules.attempts_per_person,
        "callback_after_refusal_max": rules.callback_after_refusal_max,
        "spread_attempts": rules.spread_attempts,
    }
    return questionnaire, problems


def planned(
    workspace: Workspace, fields: list[forms.Field], language: str = "de"
) -> dict[str, Any]:
    """What the answered form definitions say this run should do."""
    values = values_of(workspace, fields)
    questionnaire, problems = build(workspace, fields, language)
    rules = rules_of(workspace, fields)

    try:
        size = int(values.get("sample.size"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        size = 0
    try:
        quota = max(1, int(values.get("contact_rules.daily_quota")))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        quota = 50

    return {
        "size": max(0, size),
        "windows": list(rules.windows),
        "quota": quota,
        "method": str(values.get("sample.method") or "random"),
        "assign_randomly": bool(values.get("sample.assign_windows_randomly", True)),
        "attempts": rules.max_attempts,
        "callbacks": rules.callback_after_refusal_max,
        "spread": rules.spread_attempts,
        "resumable": bool(values.get("fieldwork.resumable", True)),
        "stop_on_error": rules.stop_on_error,
        "questions": len(questionnaire["questions"]),
        "open_questions": sum(
            1 for question in questionnaire["questions"] if instrument.is_open(question)
        ),
        "minutes": questionnaire["estimated_minutes"],
        "order": questionnaire["order"],
        "problems": problems,
        "questionnaire": questionnaire,
    }


def exists(workspace: Workspace) -> bool:
    return database_path(workspace).exists()


def prepare(
    workspace: Workspace,
    fields: list[forms.Field],
    seed: int = 42,
    language: str = "de",
) -> dict[str, int]:
    """Create the local study, a fictitious frame, and draw the sample."""
    plan = planned(workspace, fields, language)
    if plan["problems"]:
        first = plan["problems"][0]
        raise ValueError(
            f"The instrument cannot be read (line {first.line}): {first.message}"
        )
    if plan["questions"] == 0:
        raise ValueError("Station 2 carries no items, so there is nothing to ask")
    if plan["size"] <= 0 and plan["method"] != "census":
        raise ValueError("sample.size must be set before the field phase")
    if not plan["windows"]:
        raise ValueError("sample.time_windows must name at least one window")
    if plan["method"] == "stratified":
        # Refusing is the honest answer. Drawing at random and calling it
        # stratified would put a method into the report that never ran.
        raise ValueError(
            "A stratified draw needs stratifying attributes in the sampling frame, "
            "and the dry-run frame carries none. Choose random or census, or bring a "
            "frame that has them."
        )

    workspace.path.mkdir(parents=True, exist_ok=True)
    path = database_path(workspace)
    if path.exists():
        if plan["resumable"]:
            # Resumable means exactly that: an existing run is continued rather
            # than thrown away, which is also the only way a stopped run does not
            # cost its records twice.
            connection = connect(path)
            try:
                study = get_study(connection, STUDY_KEY)
                data = collect(connection, study)
                return {
                    "frame": 0,
                    "drawn": len(data["samples"]),
                    "resumed": 1,
                }
            except (ValueError, sqlite3.Error):
                pass
            finally:
                connection.close()
        path.unlink()

    initialize(path)
    questionnaire = plan["questionnaire"]
    connection = connect(path)
    try:
        study_id = create_study(connection, STUDY_KEY, questionnaire)
        connection.commit()
        frame_size = max(MIN_FRAME, max(plan["size"], 1) * FRAME_FACTOR)
        rows = [
            (f"fictional-{index:04d}", f"+155500{index:05d}")
            for index in range(1, frame_size + 1)
        ]
        imported = import_frame_rows(connection, study_id, rows)
        count = (
            eligible_count(connection, study_id)
            if plan["method"] == "census"
            else plan["size"]
        )
        drawn = draw_sample(
            connection,
            study_id,
            count,
            seed,
            tuple(plan["windows"]),
            plan["assign_randomly"],
        )
    finally:
        connection.close()
    return {"frame": imported, "drawn": drawn, "resumed": 0}


def open_database(workspace: Workspace) -> tuple[sqlite3.Connection, sqlite3.Row]:
    connection = connect(database_path(workspace))
    return connection, get_study(connection, STUDY_KEY)


def run(
    workspace: Workspace, fields: list[forms.Field]
) -> Iterator[dict[str, Any]]:
    """One record at a time, so progress is something other than a spinner.

    Yields a mapping per finished record and one final mapping with ``done``.
    Repeated contact needs more than one pass: a record that nobody answered is
    moved into another time of day and comes back when that window is worked.
    """
    plan = planned(workspace, fields)
    rules = rules_of(workspace, fields)
    client = FixtureCallClient.from_file(_fixture("outcomes.json"))
    connection, study = open_database(workspace)
    totals: Counter[str] = Counter()
    processed = 0
    passes = max(1, rules.max_attempts, 1 + rules.callback_after_refusal_max)
    try:
        for round_number in range(1, passes + 1):
            worked = 0
            for window in plan["windows"]:
                for _ in range(plan["quota"]):
                    outcome = run_day(connection, study, window, 1, client, rules)
                    if not outcome:
                        break
                    status = next(iter(outcome))
                    totals[status] += 1
                    processed += 1
                    worked += 1
                    yield {
                        "index": processed,
                        "window": window,
                        "round": round_number,
                        "status": status,
                        "totals": dict(sorted(totals.items())),
                    }
            if not worked:
                break
        yield {
            "done": True,
            "processed": processed,
            "totals": dict(sorted(totals.items())),
        }
    finally:
        connection.close()


def summary(workspace: Workspace) -> dict[str, Any]:
    """Counts for the report view, read from the same tables as the report."""
    if not exists(workspace):
        return {"ready": False}
    connection, study = open_database(workspace)
    try:
        data = collect(connection, study)
        report = build_report(connection, study)
    finally:
        connection.close()

    included = data["included_ids"]
    final_status: dict[int, str] = data["final_status"]
    statuses: Counter[str] = Counter(final_status.values())
    by_window: dict[str, Counter[str]] = {}
    for sample_id in included:
        window = data["assigned"][sample_id]
        bucket = by_window.setdefault(window, Counter())
        bucket["drawn"] += 1
        status = final_status.get(sample_id)
        if status:
            bucket[status] += 1
    repeated = sum(1 for rows in data["by_sample"].values() if len(rows) > 1)
    return {
        "ready": True,
        "drawn": len(data["samples"]),
        "included": len(included),
        "withdrawn": len(data["samples"]) - len(included),
        "attempted": len(final_status),
        "attempts": len(data["attempts"]),
        "repeated": repeated,
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
