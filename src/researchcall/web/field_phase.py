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
from ..database import connect, create_study, get_study, initialize, load_questionnaire
from ..reporting import build_report, collect
from ..review import ReviewDecision, decide as decide_review, open_cases
from ..runner import ContactRules, run_day, withdraw_external_ref
from ..sampling import (
    DEFAULT_WINDOWS,
    draw_sample,
    eligible_count,
    import_frame_rows,
    read_frame_file,
)
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
    return workspace.artifact_directory() / DB_NAME


# -- an uploaded frame instead of the fictitious one -----------------------

FRAME_UPLOAD_STEM = "frame-upload"
FRAME_UPLOAD_SUFFIXES = (".csv", ".xlsx")
FRAME_ID_COLUMN = "external_ref"
FRAME_PHONE_COLUMN = "phone"
FRAME_UPLOAD_LIMIT = 5 * 1024 * 1024


def frame_upload_path(workspace: Workspace) -> pathlib.Path | None:
    """The uploaded frame file of this workspace, if one exists."""
    directory = workspace.artifact_directory()
    for suffix in FRAME_UPLOAD_SUFFIXES:
        candidate = directory / f"{FRAME_UPLOAD_STEM}{suffix}"
        if candidate.exists():
            return candidate
    return None


def store_frame_upload(
    workspace: Workspace, filename: str, content: bytes
) -> tuple[pathlib.Path, int]:
    """Keep the uploaded file as the evidence it is, and validate it now.

    Parsing happens at upload time, not at prepare time: the person who chose
    the file is still looking at the screen and can fix a wrong column name.
    Failing later, mid-prepare, would blame the wrong step. The raw file stays
    in the workspace so the frame's origin remains inspectable.
    """
    suffix = pathlib.Path(filename or "").suffix.lower()
    if suffix not in FRAME_UPLOAD_SUFFIXES:
        raise ValueError("The frame must be a .csv or .xlsx file")
    if len(content) > FRAME_UPLOAD_LIMIT:
        raise ValueError("The frame file exceeds 5 MB; that is not a frame, that is a dump")
    if not content:
        raise ValueError("The uploaded file is empty")
    directory = workspace.artifact_directory()
    directory.mkdir(parents=True, exist_ok=True)
    for old_suffix in FRAME_UPLOAD_SUFFIXES:     # only ever one upload at a time
        stale = directory / f"{FRAME_UPLOAD_STEM}{old_suffix}"
        if stale.exists():
            stale.unlink()
    path = directory / f"{FRAME_UPLOAD_STEM}{suffix}"
    path.write_bytes(content)
    try:
        rows = read_frame_file(path, FRAME_ID_COLUMN, FRAME_PHONE_COLUMN)
    except ValueError:
        path.unlink()      # a file that cannot be read must not linger as if accepted
        raise
    if not rows:
        path.unlink()
        raise ValueError("The frame file contains a header but no rows")
    return path, len(rows)


def uploaded_frame_rows(workspace: Workspace) -> list[tuple[str, str]] | None:
    path = frame_upload_path(workspace)
    if path is None:
        return None
    return read_frame_file(path, FRAME_ID_COLUMN, FRAME_PHONE_COLUMN)


def report_path(workspace: Workspace) -> pathlib.Path:
    return workspace.artifact_directory() / REPORT_NAME


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
        "stop_on_error": rules.stop_on_error,
        # Rides with the study so the run knows it: the answer given in station 6
        # decides whether the spoken words are kept beside the coded answer.
        "keep_transcript": bool(values.get("fieldwork.keep_transcript", True)),
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


def _persisted_questionnaire(plan: dict[str, Any]) -> dict[str, Any]:
    """The instrument plus the draw decisions that cannot change on resume."""
    questionnaire = dict(plan["questionnaire"])
    questionnaire["fieldwork_plan"] = {
        "size": plan["size"],
        "windows": list(plan["windows"]),
        "method": plan["method"],
        "assign_randomly": plan["assign_randomly"],
    }
    return questionnaire


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

    path = database_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    questionnaire = _persisted_questionnaire(plan)
    if path.exists():
        # A browser click must never delete collected data. An existing run is
        # either resumed unchanged or refused with a precise reason.
        if not plan["resumable"]:
            raise ValueError(
                "A field phase already exists. This interface never deletes it; "
                "start the changed study in a new workspace directory."
            )
        connection = connect(path)
        try:
            study = get_study(connection, STUDY_KEY)
            if load_questionnaire(study) != questionnaire:
                raise ValueError(
                    "The saved field phase uses a different instrument or sampling "
                    "plan. Start the changed study in a new workspace directory."
                )
            data = collect(connection, study)
            return {
                "frame": 0,
                "drawn": len(data["samples"]),
                "resumed": 1,
            }
        except sqlite3.Error as error:
            raise ValueError(
                "The existing field phase cannot be resumed and was left untouched."
            ) from error
        finally:
            connection.close()

    initialize(path)
    connection = connect(path)
    try:
        study_id = create_study(connection, STUDY_KEY, questionnaire)
        connection.commit()
        rows = uploaded_frame_rows(workspace)
        if rows is None:
            # No upload: the dry run gets its fictitious frame, as before.
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
        report_path(workspace).write_text(
            build_report(connection, study), encoding="utf-8"
        )
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
        "report_written": report_path(workspace).exists(),
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


# -- per-person anonymisation, from the interface --------------------------

def withdraw(workspace: Workspace, external_ref: str) -> None:
    """Honour one person's withdrawal: the number goes, the row stays.

    The mechanics live in the runner (`_purge_frame`); this is only the door
    the interface knocks on. It raises with a precise sentence when the
    reference does not exist, because a withdrawal that silently did nothing
    would be worse than an error.
    """
    if not exists(workspace):
        raise ValueError("There is no field phase yet, so there is nobody to withdraw")
    connection, study = open_database(workspace)
    try:
        withdraw_external_ref(connection, int(study["id"]), external_ref.strip())
    finally:
        connection.close()


# -- the conflict queue, from the interface --------------------------------

def review_cases(workspace: Workspace) -> list[dict]:
    if not exists(workspace):
        return []
    connection, study = open_database(workspace)
    try:
        return open_cases(connection, int(study["id"]))
    finally:
        connection.close()


def decide_case(workspace: Workspace, review_id: int, decision: str, note: str) -> None:
    connection, _ = open_database(workspace)
    try:
        decide_review(connection, review_id, ReviewDecision(decision), note)
    finally:
        connection.close()


# -- the data phase, from the interface ------------------------------------

def calls(workspace: Workspace, status: str = "all") -> list[dict]:
    from ..dataphase import call_list

    if not exists(workspace):
        return []
    connection, study = open_database(workspace)
    try:
        return call_list(connection, int(study["id"]), status)
    finally:
        connection.close()


def call(workspace: Workspace, sample_id: int) -> dict:
    from ..dataphase import call_detail

    connection, study = open_database(workspace)
    try:
        return call_detail(connection, int(study["id"]), sample_id)
    finally:
        connection.close()


def flag_attempt(workspace: Workspace, attempt_id: int, note: str) -> None:
    from ..review import flag_manually

    connection, _ = open_database(workspace)
    try:
        flag_manually(connection, attempt_id, note)
    finally:
        connection.close()


def decide_open_by_rule(workspace: Workspace, decision: str, note: str) -> int:
    from ..review import ReviewDecision, decide_all_by_rule

    connection, study = open_database(workspace)
    try:
        return decide_all_by_rule(
            connection, int(study["id"]), ReviewDecision(decision), note
        )
    finally:
        connection.close()


def anonymise(workspace: Workspace, external_ref: str, reason: str) -> None:
    from ..dataphase import anonymise_deliberately

    if not exists(workspace):
        raise ValueError("There is no field phase yet, so there is nobody to withdraw")
    connection, study = open_database(workspace)
    try:
        anonymise_deliberately(connection, int(study["id"]), external_ref, reason)
    finally:
        connection.close()


def register(workspace: Workspace) -> tuple[list[dict], dict]:
    from ..dataphase import dialed_register, reconciliation

    if not exists(workspace):
        return [], {}
    connection, study = open_database(workspace)
    try:
        study_id = int(study["id"])
        return dialed_register(connection, study_id), reconciliation(connection, study_id)
    finally:
        connection.close()


def seal_status(workspace: Workspace) -> bool:
    from ..dataphase import is_sealed

    if not exists(workspace):
        return False
    connection, study = open_database(workspace)
    try:
        return is_sealed(connection, int(study["id"]))
    finally:
        connection.close()


def seal(workspace: Workspace, note: str) -> None:
    from ..dataphase import seal_dataset

    connection, study = open_database(workspace)
    try:
        seal_dataset(connection, int(study["id"]), note)
    finally:
        connection.close()


def correct(
    workspace: Workspace, sample_id: int, question_id: str, new_category: str, reason: str
) -> None:
    from ..dataphase import correct_answer

    connection, study = open_database(workspace)
    try:
        correct_answer(
            connection,
            int(study["id"]),
            sample_id,
            question_id,
            new_category if new_category != "" else None,
            reason,
        )
    finally:
        connection.close()


def changes(workspace: Workspace) -> list[dict]:
    from ..dataphase import change_history

    if not exists(workspace):
        return []
    connection, study = open_database(workspace)
    try:
        return change_history(connection, int(study["id"]))
    finally:
        connection.close()


def run_t_test(workspace: Workspace, numeric_question: str, group_question: str) -> dict:
    """Welch t-test of one numeric item across the two groups of another item.

    Answers are category strings; an item only counts as numeric when every
    answered value parses as a number. Anything else is refused with the
    sentence that explains it -- silently coercing categories to numbers is
    how nonsense gets significance stars.
    """
    from ..stats import welch_t_test

    connection, study = open_database(workspace)
    try:
        rows = connection.execute(
            """
            SELECT r.structured_json FROM response r
            JOIN sample s ON s.id = r.sample_id
            WHERE s.study_id = ? AND s.excluded_at IS NULL
            """,
            (int(study["id"]),),
        ).fetchall()
    finally:
        connection.close()

    import json as _json

    groups: dict[str, list[float]] = {}
    for row in rows:
        structured = _json.loads(str(row["structured_json"]))
        answers = structured.get("answers", {})
        group = answers.get(group_question)
        value = answers.get(numeric_question)
        if group is None or value is None:
            continue
        try:
            number = float(str(value))
        except ValueError:
            raise ValueError(
                f"'{numeric_question}' has the answer '{value}', which is not a "
                f"number; a t-test over coerced categories would be nonsense"
            )
        groups.setdefault(str(group), []).append(number)

    if len(groups) != 2:
        raise ValueError(
            f"'{group_question}' has {len(groups)} answered group(s); a t-test "
            f"compares exactly two"
        )
    (label_a, values_a), (label_b, values_b) = sorted(groups.items())
    result = welch_t_test(values_a, values_b, label_a, label_b)
    return result.to_dict()
