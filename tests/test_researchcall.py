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
from researchcall.calls import CallOutcome, FixtureCallClient, LiveCallClient
from researchcall.database import connect, create_study, get_study, initialize
from researchcall.questionnaire import (
    build_task,
    load_questionnaire_file,
    result_schema,
)
from researchcall.reporting import build_report
from researchcall.runner import (
    TRANSCRIPT_LINE_RE,
    ContactRules,
    run_day,
    withdraw_external_ref,
)
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
        self.assertIn(
            f'CONSENT (say exactly): "{self.questionnaire["consent_text"]}"', task
        )
        for question in self.questionnaire["questions"]:
            self.assertIn(f'(say exactly): "{question["wording"]}"', task)
        self.assertIn("Ask only if q1 equals category `yes`", task)
        self.assertIn(
            "Allowed answer categories (interpretation labels; do not read aloud): "
            "`yes`, `no`.",
            task,
        )
        self.assertNotIn('equals "yes"', task)
        self.assertIn("Do not paraphrase", task)
        self.assertIn("raw words", task)
        schema = result_schema(self.questionnaire)
        self.assertIn("asked_verbatim", schema["required"])
        self.assertIn("spoken_wording", schema["required"])
        self.assertIn("raw_answers", schema["required"])
        self.assertIn("withdrawal_requested", schema["required"])

    def test_fixture_keeps_raw_answer_separate_from_interpreted_category(self) -> None:
        client = FixtureCallClient.from_file(OUTCOMES)
        outcome = client.call({"sample_id": 6}, self.questionnaire, "unused")
        self.assertEqual(outcome.structured_result["answers"]["q2"], "dissatisfied")
        self.assertEqual(
            outcome.structured_result["raw_answers"]["q2"],
            "synthetische Kategorie zwei",
        )
        with self.assertRaisesRegex(ValueError, "raw_answers"):
            FixtureCallClient(
                [{"status": "COMPLETED", "answers": {"q1": "yes"}}]
            ).call({"sample_id": 1}, self.questionnaire, "unused")

    def test_live_rest_path_uses_activity_and_nested_result(self) -> None:
        fixture = FixtureCallClient.from_file(OUTCOMES).call(
            {"sample_id": 1}, self.questionnaire, "unused"
        )
        progress: list[dict[str, object]] = []
        requests: list[tuple[str, str, dict[str, object] | None, str | None]] = []
        client = LiveCallClient(
            api_key="fixture-token",
            base_url="https://example.invalid",
            first_poll_seconds=0,
            poll_seconds=0,
            poll_timeout_seconds=1,
            progress_callback=progress.append,
        )

        responses = iter(
            [
                {"id": "rest-call-1"},
                {
                    "status": "PREPARING",
                    "activity": [
                        {"timestamp": "00:00:05.000", "message": "Bot is speaking"}
                    ],
                },
                {
                    "status": "COMPLETED",
                    "transcript": None,
                    "activity": [
                        {"timestamp": "00:00:05.000", "message": "Bot is speaking"},
                        {"timestamp": "00:00:25.000", "message": "Call ended"},
                    ],
                    "result": {
                        "transcript": "[00:00] BOT: Testfrage\\n[00:02] USER: Testantwort",
                        "structuredResult": fixture.structured_result,
                    },
                },
            ]
        )

        def fake_request(
            method: str,
            path: str,
            payload: dict[str, object] | None = None,
            idempotency_key: str | None = None,
        ) -> dict[str, object]:
            requests.append((method, path, payload, idempotency_key))
            return next(responses)

        with patch.object(client, "_request", side_effect=fake_request):
            outcome = client.call(
                {"sample_id": 1, "phone_e164": "+15550123456"},
                self.questionnaire,
                "stable-key",
            )

        self.assertEqual(outcome.status, "COMPLETED")
        self.assertEqual(outcome.structured_result, fixture.structured_result)
        self.assertEqual(
            outcome.transcript,
            "[00:00] BOT: Testfrage\\n[00:02] USER: Testantwort",
        )
        self.assertEqual(progress[0]["activity_events"], 1)
        self.assertNotIn("status", progress[0])
        post_payload = requests[0][2]
        self.assertIn("recipient_result_schema", post_payload)
        self.assertIn(
            "raw_answers", post_payload["recipient_result_schema"]["required"]
        )
        self.assertEqual(requests[0][3], "stable-key")

    def test_live_client_reads_bearer_only_from_calle_api_key(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "CALLE_API_KEY": "fixture-token",
                "CALLE_BASE_URL": "https://example.invalid",
            },
            clear=True,
        ):
            client = LiveCallClient.from_environment()

        captured_requests = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            @staticmethod
            def read() -> bytes:
                return b"{}"

        def fake_urlopen(request, timeout):
            del timeout
            captured_requests.append(request)
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            client._request("GET", "/v1/calls/rest-call-1")

        self.assertEqual(
            captured_requests[0].get_header("Authorization"),
            "Bearer fixture-token",
        )
        with patch.dict("os.environ", {"CALLE_TOKEN": "ignored"}, clear=True):
            with self.assertRaisesRegex(ValueError, "CALLE_API_KEY"):
                LiveCallClient.from_environment()

    def test_transcript_is_audited_in_memory_but_not_persisted(self) -> None:
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        sample = self.connection.execute(
            "SELECT id, time_window FROM sample"
        ).fetchone()
        fixture_client = FixtureCallClient.from_file(OUTCOMES)
        fixture_outcome = fixture_client.call(
            {"sample_id": sample["id"]}, self.questionnaire, "unused"
        )
        transcript_lines = [
            f'[00:00] BOT: {self.questionnaire["consent_text"]}',
            '[00:04] USER: Ja.',
        ]
        for index, question in enumerate(self.questionnaire["questions"], start=1):
            transcript_lines.append(f"[00:{index * 5:02d}] BOT: {question['wording']}")
            raw_answer = fixture_outcome.structured_result["raw_answers"][question["id"]]
            transcript_lines.append(f"[00:{index * 5 + 2:02d}] USER: {raw_answer}")
        transcript = "\n".join(transcript_lines)
        live_outcome = CallOutcome(
            status="COMPLETED",
            run_id="rest-call-audit",
            structured_result=fixture_outcome.structured_result,
            detail={"transport": "live-api"},
            transcript=transcript,
        )

        with patch.object(fixture_client, "call", return_value=live_outcome):
            totals = run_day(
                self.connection,
                get_study(self.connection, "study"),
                sample["time_window"],
                1,
                fixture_client,
            )

        self.assertEqual(totals["COMPLETED"], 1)
        detail_json = self.connection.execute(
            "SELECT detail_json FROM attempt WHERE sample_id = ?", (sample["id"],)
        ).fetchone()["detail_json"]
        detail = json.loads(detail_json)
        self.assertEqual(detail["transcript_format"], "timestamped-speaker-lines")
        self.assertTrue(detail["transcript_wording_matches"])
        self.assertFalse(detail["transcript_persisted"])
        self.assertNotIn(transcript, detail_json)
        report = build_report(self.connection, get_study(self.connection, "study"))
        self.assertIn("Categorized answers with retained raw source text: 3", report)
        self.assertIn("Transcript records audited in memory: 1", report)

    # --- Live payload shapes measured against GET /v1/calls/{id} on 2026-08-11 ---

    def live_client(self, final_payload: dict[str, object]) -> CallOutcome:
        """One live call whose polling returns *final_payload* as terminal state."""
        client = LiveCallClient(
            api_key="fixture-token",
            base_url="https://example.invalid",
            first_poll_seconds=0,
            poll_seconds=0,
            poll_timeout_seconds=1,
        )
        responses = iter([{"id": "rest-call-1"}, final_payload])

        def fake_request(*args: object, **kwargs: object) -> dict[str, object]:
            return next(responses)

        with patch.object(client, "_request", side_effect=fake_request):
            return client.call(
                {"sample_id": 1, "phone_e164": "+15550123456"},
                self.questionnaire,
                "stable-key",
            )

    def interview_turns(self, structured: dict[str, object]) -> list[dict[str, object]]:
        """The turn list a completed interview leaves behind, as the API returns it."""
        turns: list[dict[str, object]] = [
            {
                "offset_seconds": 0,
                "speaker": "bot",
                "text": self.questionnaire["consent_text"],
            },
            {"offset_seconds": 4, "speaker": "user", "text": "Ja, gerne."},
        ]
        offset = 10
        for question in self.questionnaire["questions"]:
            turns.append(
                {"offset_seconds": offset, "speaker": "bot", "text": question["wording"]}
            )
            turns.append(
                {
                    "offset_seconds": offset + 3,
                    "speaker": "user",
                    "text": structured["raw_answers"][question["id"]],
                }
            )
            offset += 10
        return turns

    def completed_payload(
        self, structured: dict[str, object] | None, turns: list[dict[str, object]]
    ) -> dict[str, object]:
        recipient: dict[str, object] = {
            "status": "completed",
            "attempts": [{"status": "completed", "transcript_turns": turns}],
        }
        if structured is not None:
            recipient["structured_result"] = structured
        return {
            "status": "completed",
            "task_completed": True,
            "transcript": None,
            "recipients": [recipient],
        }

    def fixture_structured_result(self) -> dict[str, object]:
        return FixtureCallClient.from_file(OUTCOMES).call(
            {"sample_id": 1}, self.questionnaire, "unused"
        ).structured_result

    def test_transcript_turns_are_read_and_rendered_as_speaker_lines(self) -> None:
        structured = self.fixture_structured_result()
        outcome = self.live_client(
            self.completed_payload(structured, self.interview_turns(structured))
        )

        self.assertEqual(outcome.status, "COMPLETED")
        self.assertIsNotNone(outcome.transcript)
        lines = outcome.transcript.splitlines()
        self.assertEqual(
            lines[0], f'[00:00] BOT: {self.questionnaire["consent_text"]}'
        )
        self.assertEqual(lines[1], "[00:04] USER: Ja, gerne.")
        self.assertTrue(all(TRANSCRIPT_LINE_RE.fullmatch(line) for line in lines))
        self.assertEqual(
            outcome.detail["transcript_location"],
            "recipients[].attempts[].transcript_turns",
        )
        self.assertEqual(outcome.detail["recipient_attempts"], 1)

    def test_turn_transcript_actually_reaches_the_wording_and_gate_audits(self) -> None:
        """The point of reading turns: both after-call audits run again.

        Before the transport understood ``transcript_turns``, ``outcome.transcript``
        stayed ``None`` on a live call and the two guarded blocks in
        ``_finish_attempt`` silently did nothing. Asserting on the persisted
        attempt is the only way to see that they fire.
        """
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        sample = self.connection.execute(
            "SELECT id, time_window FROM sample"
        ).fetchone()
        structured = self.fixture_structured_result()
        outcome = self.live_client(
            self.completed_payload(structured, self.interview_turns(structured))
        )

        client = FixtureCallClient.from_file(OUTCOMES)
        with patch.object(client, "call", return_value=outcome):
            totals = run_day(
                self.connection,
                get_study(self.connection, "study"),
                sample["time_window"],
                1,
                client,
            )

        self.assertEqual(totals["COMPLETED"], 1)
        detail = json.loads(
            self.connection.execute(
                "SELECT detail_json FROM attempt WHERE sample_id = ?", (sample["id"],)
            ).fetchone()["detail_json"]
        )
        self.assertEqual(detail["transcript_format"], "timestamped-speaker-lines")
        self.assertTrue(detail["transcript_wording_matches"])
        self.assertEqual(detail["gates_seen"], ["consent_question"])
        self.assertEqual(detail["gates_missed"], [])
        self.assertFalse(detail["transcript_persisted"])

    def test_mailbox_pickup_is_not_counted_as_an_interview(self) -> None:
        payload = self.completed_payload(
            None,
            [
                {
                    "offset_seconds": 0,
                    "speaker": "bot",
                    "text": self.questionnaire["consent_text"],
                },
                {
                    "offset_seconds": 4,
                    "speaker": "user",
                    "text": (
                        "Die angerufene Person ist nicht erreichbar. bitte "
                        "hinterlassen sie eine nachricht nach dem signalton"
                    ),
                },
            ],
        )
        payload["evidence"] = [
            "Die Ansage der Mailbox bat darum, nach dem Signalton eine Nachricht zu hinterlassen."
        ]

        outcome = self.live_client(payload)

        self.assertEqual(outcome.status, "VOICEMAIL")
        self.assertEqual(outcome.detail["status_source"], "voicemail-heuristic")
        self.assertIn(
            "hinterlassen sie eine nachricht", outcome.detail["voicemail_markers"]
        )

    def test_a_person_who_is_hard_to_reach_stays_a_completed_interview(self) -> None:
        """The negative case the heuristic must never get wrong.

        A human saying they are badly reachable carries the weak marker but
        nothing a machine would say. In doubt the call stays COMPLETED.
        """
        outcome = self.live_client(
            self.completed_payload(
                None,
                [
                    {"offset_seconds": 0, "speaker": "bot", "text": "Guten Tag."},
                    {
                        "offset_seconds": 3,
                        "speaker": "user",
                        "text": "Hallo? Ja, ich bin gerade schlecht erreichbar, aber fragen Sie.",
                    },
                ],
            )
        )

        self.assertEqual(outcome.status, "COMPLETED")
        self.assertNotIn("voicemail_markers", outcome.detail)

    def test_a_consented_interview_is_never_reclassified_as_voicemail(self) -> None:
        """The expensive error: throwing away answers a person actually gave."""
        structured = self.fixture_structured_result()
        turns = self.interview_turns(structured)
        turns.append(
            {
                "offset_seconds": 60,
                "speaker": "user",
                "text": "Nein, ich habe gar keinen Anrufbeantworter, rufen Sie ruhig an.",
            }
        )

        outcome = self.live_client(self.completed_payload(structured, turns))

        self.assertEqual(outcome.status, "COMPLETED")
        self.assertNotIn("voicemail_markers", outcome.detail)

    def test_voicemail_leaves_no_response_row_and_is_reported_as_a_loss(self) -> None:
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        sample = self.connection.execute(
            "SELECT id, time_window FROM sample"
        ).fetchone()
        outcome = CallOutcome(
            status="VOICEMAIL",
            run_id="rest-call-voicemail",
            structured_result=None,
            detail={"transport": "live-api", "status_source": "voicemail-heuristic"},
            transcript="[00:04] USER: bitte hinterlassen sie eine nachricht nach dem signalton",
        )
        client = FixtureCallClient.from_file(OUTCOMES)
        with patch.object(client, "call", return_value=outcome):
            totals = run_day(
                self.connection,
                get_study(self.connection, "study"),
                sample["time_window"],
                1,
                client,
            )

        self.assertEqual(totals["VOICEMAIL"], 1)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) AS n FROM response").fetchone()["n"],
            0,
        )
        report = build_report(self.connection, get_study(self.connection, "study"))
        self.assertIn("- Completed interviews: 0", report)
        self.assertIn("VOICEMAIL", report)

    def test_declined_is_recovered_from_the_failure_message(self) -> None:
        outcome = self.live_client(
            {
                "status": "failed",
                "task_completed": False,
                "failure_code": "call_failed",
                "failure_message": "calling task status=DECLINED (Hangup by: user)",
                "recipients": [
                    {
                        "status": "failed",
                        "attempts": [{"status": "failed", "transcript_turns": []}],
                    }
                ],
            }
        )

        self.assertEqual(outcome.status, "DECLINED")
        self.assertEqual(outcome.detail["failure_code"], "call_failed")
        self.assertEqual(outcome.detail["status_source"], "failure_message")
        self.assertIsNone(outcome.transcript)
        # The foreign free-text message is parsed, never stored.
        self.assertNotIn("Hangup by", json.dumps(outcome.detail))

    def test_a_refusal_recovered_this_way_is_not_dialled_again(self) -> None:
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        sample = self.connection.execute(
            "SELECT id, time_window FROM sample"
        ).fetchone()
        outcome = CallOutcome(
            status="DECLINED",
            run_id="rest-call-declined",
            structured_result=None,
            detail={"transport": "live-api", "status_source": "failure_message"},
        )
        rules = ContactRules(attempts_per_person=2)
        client = FixtureCallClient.from_file(OUTCOMES)
        study = get_study(self.connection, "study")
        with patch.object(client, "call", return_value=outcome):
            first = run_day(
                self.connection, study, sample["time_window"], 3, client, rules
            )
            second = run_day(
                self.connection, study, sample["time_window"], 3, client, rules
            )

        self.assertEqual(first["DECLINED"], 1)
        self.assertEqual(sum(second.values()), 0)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) AS n FROM attempt").fetchone()["n"],
            1,
        )

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
