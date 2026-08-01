from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall import cli
from researchcall.calls import FixtureCallClient
from researchcall.database import connect, create_study, get_study, initialize
from researchcall.questionnaire import (
    build_task,
    load_questionnaire_file,
    result_schema,
)
from researchcall.reporting import build_report
from researchcall.runner import run_day, withdraw_external_ref
from researchcall.safety import mask_phone, validate_e164
from researchcall.sampling import (
    DEFAULT_WINDOWS,
    draw_sample,
    import_frame_rows,
    read_sqlite_frame,
)


QUESTIONNAIRE = ROOT / "src" / "researchcall" / "fixtures" / "questionnaire.de.json"
OUTCOMES = ROOT / "src" / "researchcall" / "fixtures" / "outcomes.json"
TEST_TEMP_ROOT = ROOT / "out" / "tests"


class ResearchCallTestCase(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tempdir = tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT)
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "state.db"
        initialize(self.db_path)
        self.questionnaire = load_questionnaire_file(QUESTIONNAIRE)
        self.connection = connect(self.db_path)
        self.addCleanup(self.connection.close)
        self.study_id = create_study(self.connection, "study", self.questionnaire)
        self.connection.commit()

    def import_rows(self, count: int = 30) -> None:
        rows = [
            (f"person-{index:03d}", f"+155501{index:05d}")
            for index in range(1, count + 1)
        ]
        import_frame_rows(self.connection, self.study_id, rows)

    def run_all_windows(self, limit: int = 100) -> dict[str, int]:
        study = get_study(self.connection, "study")
        client = FixtureCallClient.from_file(OUTCOMES)
        totals: dict[str, int] = {}
        for window in DEFAULT_WINDOWS:
            for status, count in run_day(
                self.connection, study, window, limit, client
            ).items():
                totals[status] = totals.get(status, 0) + count
        return totals

    def test_fixed_wording_filter_and_audit_schema_are_in_task(self) -> None:
        task = build_task(self.questionnaire)
        self.assertIn(self.questionnaire["consent_text"], task)
        self.assertIn(self.questionnaire["questions"][1]["wording"], task)
        self.assertIn("Ask only if q1 equals \"yes\"", task)
        self.assertIn("Do not paraphrase", task)
        schema = result_schema(self.questionnaire)
        self.assertIn("asked_verbatim", schema["required"])
        self.assertIn("spoken_wording", schema["required"])
        self.assertIn("withdrawal_requested", schema["required"])

    def test_random_draw_assigns_windows_and_every_sample_is_attempted_once(self) -> None:
        self.import_rows()
        self.assertEqual(draw_sample(self.connection, self.study_id, 18, 17), 18)
        samples = self.connection.execute(
            "SELECT frame_id, time_window FROM sample ORDER BY id"
        ).fetchall()
        self.assertEqual(len({row["frame_id"] for row in samples}), 18)
        self.assertTrue({row["time_window"] for row in samples} <= set(DEFAULT_WINDOWS))

        totals = self.run_all_windows()
        self.assertEqual(sum(totals.values()), 18)
        self.assertGreater(len(totals), 3)
        self.assertEqual(sum(self.run_all_windows().values()), 0)
        attempts = self.connection.execute(
            "SELECT sample_id, started_at, ended_at, call_status FROM attempt"
        ).fetchall()
        self.assertEqual(len(attempts), 18)
        self.assertEqual(len({row["sample_id"] for row in attempts}), 18)
        self.assertTrue(all(row["started_at"] and row["ended_at"] for row in attempts))

    def test_report_preserves_loss_structure_and_never_contains_phone_numbers(self) -> None:
        self.import_rows()
        draw_sample(self.connection, self.study_id, 18, 17)
        self.run_all_windows()
        report = build_report(self.connection, get_study(self.connection, "study"))
        for status in ("NO_ANSWER", "DECLINED", "BUSY", "VOICEMAIL"):
            self.assertIn(status, report)
        self.assertIn("Only fixture evidence is present", report)
        self.assertNotIn("+155501", report)

    def test_withdrawal_erases_identifiers_and_excludes_record(self) -> None:
        self.import_rows(2)
        draw_sample(self.connection, self.study_id, 2, 5)
        frame = self.connection.execute(
            """
            SELECT f.id, f.external_ref
            FROM frame f JOIN sample s ON s.frame_id = f.id
            ORDER BY s.id LIMIT 1
            """
        ).fetchone()
        withdraw_external_ref(self.connection, self.study_id, frame["external_ref"])
        stored = self.connection.execute(
            "SELECT external_ref, phone_e164, withdrawn_at FROM frame WHERE id = ?",
            (frame["id"],),
        ).fetchone()
        self.assertTrue(stored["external_ref"].startswith("withdrawn:"))
        self.assertIsNone(stored["phone_e164"])
        self.assertIsNotNone(stored["withdrawn_at"])
        sample = self.connection.execute(
            "SELECT excluded_at, exclusion_reason FROM sample WHERE frame_id = ?",
            (frame["id"],),
        ).fetchone()
        self.assertIsNotNone(sample["excluded_at"])
        self.assertEqual(sample["exclusion_reason"], "WITHDRAWN")

    def test_sqlite_frame_source_is_opened_read_only(self) -> None:
        source = Path(self.tempdir.name) / "frame.sqlite"
        source_connection = sqlite3.connect(source)
        source_connection.execute("CREATE TABLE people(ref TEXT, phone TEXT)")
        source_connection.execute(
            "INSERT INTO people VALUES ('source-1', '+15550199999')"
        )
        source_connection.commit()
        source_connection.close()
        rows = read_sqlite_frame(source, "people", "ref", "phone")
        self.assertEqual(rows, [("source-1", "+15550199999")])

    def test_live_mode_fails_before_client_creation_without_exact_intent(self) -> None:
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 1)
        self.connection.close()
        with patch(
            "researchcall.cli.LiveCallClient.from_environment",
            side_effect=AssertionError("live client must not be created"),
        ):
            code = cli.main(
                [
                    "--db",
                    str(self.db_path),
                    "run-day",
                    "--study",
                    "study",
                    "--window",
                    "morning",
                    "--limit",
                    "1",
                    "--live",
                ]
            )
        self.assertEqual(code, 2)

    def test_phone_validation_and_masking(self) -> None:
        self.assertEqual(validate_e164("+15550123456"), "+15550123456")
        with self.assertRaises(ValueError):
            validate_e164("07700 900000")
        self.assertEqual(mask_phone("+15550123456"), "+***56")
        self.assertNotIn("1234", mask_phone("+15550123456"))

    def test_duplicate_phone_cannot_create_two_person_attempts(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate phone"):
            import_frame_rows(
                self.connection,
                self.study_id,
                [("person-a", "+15550123456"), ("person-b", "+15550123456")],
            )

    def test_demo_runs_end_to_end_without_network(self) -> None:
        workspace = Path(self.tempdir.name) / "demo"
        stdout = io.StringIO()
        with patch(
            "urllib.request.urlopen", side_effect=AssertionError("network access forbidden")
        ), contextlib.redirect_stdout(stdout):
            code = cli.main(["demo", "--workspace", str(workspace), "--seed", "42"])
        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("mode=dry-run transport=fixture network=disabled", output)
        self.assertIn("frame_imported=200 sample_drawn=50 attempts=50", output)
        self.assertTrue((workspace / "report.md").exists())
        state = sqlite3.connect(workspace / "researchcall-demo.db")
        try:
            self.assertEqual(state.execute("SELECT COUNT(*) FROM frame").fetchone()[0], 200)
            self.assertEqual(state.execute("SELECT COUNT(*) FROM sample").fetchone()[0], 50)
            self.assertEqual(state.execute("SELECT COUNT(*) FROM attempt").fetchone()[0], 50)
        finally:
            state.close()


if __name__ == "__main__":
    unittest.main()
