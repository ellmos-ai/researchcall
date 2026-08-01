from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from importlib.resources import files
from pathlib import Path
from typing import Sequence

from .calls import OBSERVED_SETUP_SECONDS, FixtureCallClient, LiveCallClient
from .database import connect, create_study, get_study, initialize
from .questionnaire import load_questionnaire_file, validate_questionnaire
from .reporting import build_report
from .runner import run_day, withdraw_external_ref
from .sampling import (
    DEFAULT_WINDOWS,
    draw_sample,
    import_frame_rows,
    read_csv_frame,
    read_sqlite_frame,
)


def _fixture_path(name: str) -> Path:
    return Path(str(files("researchcall").joinpath("fixtures", name)))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="researchcall",
        description="Dry-run-first standardized scientific telephone survey tooling.",
    )
    parser.add_argument("--db", type=Path, default=Path("researchcall.db"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize the local SQLite state database.")

    create = subparsers.add_parser("create-study")
    create.add_argument("--study", required=True)
    create.add_argument("--questionnaire", required=True, type=Path)

    frame = subparsers.add_parser("import-frame")
    frame.add_argument("--study", required=True)
    frame.add_argument("--source", required=True, type=Path)
    frame.add_argument("--table")
    frame.add_argument("--id-column", default="external_ref")
    frame.add_argument("--phone-column", default="phone_e164")

    draw = subparsers.add_parser("draw")
    draw.add_argument("--study", required=True)
    draw.add_argument("--count", required=True, type=int)
    draw.add_argument("--seed", required=True, type=int)
    draw.add_argument("--windows", default=",".join(DEFAULT_WINDOWS))

    daily = subparsers.add_parser("run-day")
    daily.add_argument("--study", required=True)
    daily.add_argument("--window", required=True)
    daily.add_argument("--limit", required=True, type=int)
    daily.add_argument("--fixture", type=Path, default=_fixture_path("outcomes.json"))
    daily.add_argument("--live", action="store_true")
    daily.add_argument(
        "--confirm-live",
        help='Live intent gate. Must exactly equal "CALL N", where N is --limit.',
    )
    daily.add_argument(
        "--consent-attested",
        action="store_true",
        help="Attest that selected recipients may lawfully and ethically be called.",
    )

    report = subparsers.add_parser("report")
    report.add_argument("--study", required=True)
    report.add_argument("--output", type=Path)

    withdraw = subparsers.add_parser("withdraw")
    withdraw.add_argument("--study", required=True)
    withdraw.add_argument("--external-ref", required=True)

    demo = subparsers.add_parser("demo")
    demo.add_argument("--workspace", type=Path, default=Path("out/demo"))
    demo.add_argument("--seed", type=int, default=20260914)
    return parser


def _require_initialized(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise ValueError(f"State database does not exist: {path}")
    return connect(path)


def _print_live_progress(progress: dict[str, object]) -> None:
    print(
        "live_progress=activity "
        f"activity_events={progress['activity_events']}"
    )


def _run_demo(workspace: Path, seed: int) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    db_path = workspace / "researchcall-demo.db"
    report_path = workspace / "report.md"
    if db_path.exists():
        raise ValueError(f"Demo state already exists: {db_path}")
    initialize(db_path)
    questionnaire = load_questionnaire_file(_fixture_path("questionnaire.de.json"))
    connection = connect(db_path)
    try:
        study_id = create_study(connection, "demo", questionnaire)
        connection.commit()
        rows = [
            (f"fictional-{index:03d}", f"+155500{index:05d}")
            for index in range(1, 201)
        ]
        imported = import_frame_rows(connection, study_id, rows)
        drawn = draw_sample(connection, study_id, 50, seed, DEFAULT_WINDOWS)
        study = get_study(connection, "demo")
        client = FixtureCallClient.from_file(_fixture_path("outcomes.json"))
        totals: dict[str, int] = {}
        for window in DEFAULT_WINDOWS:
            for status, count in run_day(connection, study, window, 50, client).items():
                totals[status] = totals.get(status, 0) + count
        report = build_report(connection, study)
    finally:
        connection.close()
    report_path.write_text(report, encoding="utf-8")
    print("mode=dry-run transport=fixture network=disabled")
    print(f"frame_imported={imported} sample_drawn={drawn} attempts={sum(totals.values())}")
    print("terminal_statuses=" + json.dumps(dict(sorted(totals.items())), separators=(",", ":")))
    print(f"report={report_path}")


def run(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "init":
        initialize(args.db)
        print(f"initialized={args.db}")
        return 0
    if args.command == "demo":
        _run_demo(args.workspace, args.seed)
        return 0

    connection = _require_initialized(args.db)
    try:
        if args.command == "create-study":
            questionnaire = load_questionnaire_file(args.questionnaire)
            create_study(connection, args.study, questionnaire)
            connection.commit()
            print(f"study_created={args.study}")
        elif args.command == "import-frame":
            study = get_study(connection, args.study)
            if args.source.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                if not args.table:
                    raise ValueError("--table is required for a SQLite frame source")
                rows = read_sqlite_frame(
                    args.source, args.table, args.id_column, args.phone_column
                )
            else:
                rows = read_csv_frame(args.source, args.id_column, args.phone_column)
            count = import_frame_rows(connection, int(study["id"]), rows)
            print(f"frame_imported={count}")
        elif args.command == "draw":
            study = get_study(connection, args.study)
            windows = tuple(item.strip() for item in args.windows.split(",") if item.strip())
            count = draw_sample(
                connection, int(study["id"]), args.count, args.seed, windows
            )
            print(f"sample_drawn={count} windows={','.join(windows)}")
        elif args.command == "run-day":
            study = get_study(connection, args.study)
            validate_questionnaire(json.loads(study["questionnaire_json"]))
            if args.live:
                expected = f"CALL {args.limit}"
                if args.confirm_live != expected:
                    raise ValueError(
                        f'Live mode requires --confirm-live "{expected}" for this bounded quota'
                    )
                if not args.consent_attested:
                    raise ValueError("Live mode requires --consent-attested")
                print(
                    f"live_plan=max_calls={args.limit} dispatch=serial "
                    f"observed_setup_seconds_per_call=about-{OBSERVED_SETUP_SECONDS} "
                    "concurrency=unverified"
                )
                client = LiveCallClient.from_environment(
                    progress_callback=_print_live_progress
                )
                mode = "live"
            else:
                client = FixtureCallClient.from_file(args.fixture)
                mode = "dry-run"
            totals = run_day(connection, study, args.window, args.limit, client)
            print(f"mode={mode} window={args.window} attempts={sum(totals.values())}")
            print("terminal_statuses=" + json.dumps(dict(sorted(totals.items())), separators=(",", ":")))
        elif args.command == "report":
            study = get_study(connection, args.study)
            report_text = build_report(connection, study)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(report_text, encoding="utf-8")
                print(f"report={args.output}")
            else:
                print(report_text)
        elif args.command == "withdraw":
            study = get_study(connection, args.study)
            withdraw_external_ref(connection, int(study["id"]), args.external_ref)
            print("withdrawal=anonymized-and-excluded")
        else:
            raise AssertionError("Unhandled command")
    finally:
        connection.close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except KeyboardInterrupt:
        print("interrupted=attempt-state-preserved", file=sys.stderr)
        return 130
    except (ValueError, sqlite3.Error, OSError, json.JSONDecodeError) as error:
        print(f"error={error}", file=sys.stderr)
        return 2
