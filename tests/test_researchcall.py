from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall import cli
from researchcall.calls import CallOutcome, FixtureCallClient, LiveCallClient
from researchcall.database import connect, create_study, get_study, initialize
from researchcall.field_trial import ENV_VAR as FIELD_TRIAL_ENV
from researchcall.dataphase import (
    anonymise_deliberately,
    call_detail,
    seal_dataset,
)
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


def nullable_unions(schema: Any, path: str = "$") -> list[str]:
    """Every place a schema says "or null" — in any of its spellings.

    The API rejects the whole request for one of these, so the check is made
    against the shape rather than against a list of known field names: a union
    reintroduced in a new field would otherwise pass unnoticed.
    """
    found: list[str] = []
    if isinstance(schema, dict):
        declared = schema.get("type")
        if isinstance(declared, list):
            found.append(f"{path}.type is a union: {declared}")
        elif declared == "null":
            found.append(f"{path}.type is null")
        if isinstance(schema.get("enum"), list) and None in schema["enum"]:
            found.append(f"{path}.enum contains null")
        for key, value in schema.items():
            found.extend(nullable_unions(value, f"{path}.{key}"))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            found.extend(nullable_unions(value, f"{path}[{index}]"))
    return found


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
        # The schema no longer accepts null (issue #120), so the task must not
        # keep asking for it: the call would survive create and fail on return.
        self.assertNotIn("null", task)
        self.assertIn("omit", task)
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
            "2. Ja, unzufrieden.",
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
                        {"timestamp": "17:37:50.769", "message": "Bot is speaking"}
                    ],
                },
                {
                    "status": "COMPLETED",
                    "transcript": None,
                    "activity": [
                        {"timestamp": "17:37:50.769", "message": "Bot is speaking"},
                        {"timestamp": "17:38:21.375", "message": "Call ended"},
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

    def call_with_transcript(
        self,
        transcript_lines: list[str] | None = None,
        keep_transcript: bool | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Run one call whose transcript is given, and return (detail, transcript).

        The retention decision travels with the study, so it is written into the
        stored questionnaire before the run — the same way the workbench records
        every other run rule.
        """
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        sample = self.connection.execute(
            "SELECT id, time_window FROM sample"
        ).fetchone()
        if keep_transcript is not None:
            self.connection.execute(
                "UPDATE study SET questionnaire_json = ? WHERE id = ?",
                (
                    json.dumps(
                        {
                            **self.questionnaire,
                            "run_rules": {"keep_transcript": keep_transcript},
                        },
                        ensure_ascii=False,
                    ),
                    self.study_id,
                ),
            )
            self.connection.commit()
        fixture_client = FixtureCallClient.from_file(OUTCOMES)
        fixture_outcome = fixture_client.call(
            {"sample_id": sample["id"]}, self.questionnaire, "unused"
        )
        if transcript_lines is None:
            transcript_lines = [
                f'[00:00] BOT: {self.questionnaire["consent_text"]}',
                "[00:04] USER: Ja.",
            ]
            for index, question in enumerate(self.questionnaire["questions"], start=1):
                transcript_lines.append(
                    f"[00:{index * 5:02d}] BOT: {question['wording']}"
                )
                raw_answer = fixture_outcome.structured_result["raw_answers"][
                    question["id"]
                ]
                transcript_lines.append(
                    f"[00:{index * 5 + 2:02d}] USER: {raw_answer}"
                )
        transcript = "\n".join(transcript_lines)
        live_outcome = CallOutcome(
            status="COMPLETED",
            run_id="rest-call-audit",
            structured_result=fixture_outcome.structured_result,
            detail={"transport": "live-api"},
            transcript=transcript,
        )
        with patch.object(fixture_client, "call", return_value=live_outcome):
            run_day(
                self.connection,
                get_study(self.connection, "study"),
                sample["time_window"],
                1,
                fixture_client,
            )
        detail_json = self.connection.execute(
            "SELECT detail_json FROM attempt WHERE sample_id = ?", (sample["id"],)
        ).fetchone()["detail_json"]
        return json.loads(detail_json), transcript

    def test_transcript_is_audited_and_kept_with_the_attempt(self) -> None:
        """User decision of 2026-08-11: transcripts are stored, not discarded.

        The review queue promises transcript and answer side by side, so the
        verbatim text has to survive the call. It reaches the review surface
        through the attempt detail, which is also what a withdrawal erases.
        """
        detail, transcript = self.call_with_transcript()

        self.assertEqual(detail["transcript_format"], "timestamped-speaker-lines")
        self.assertTrue(detail["transcript_wording_matches"])
        self.assertTrue(detail["transcript_persisted"])
        self.assertEqual(detail["transcript"], transcript)
        sample_id = int(
            self.connection.execute("SELECT id FROM sample").fetchone()["id"]
        )
        shown = call_detail(self.connection, self.study_id, sample_id)
        self.assertEqual(shown["attempts"][0]["transcript"], transcript)
        report = build_report(self.connection, get_study(self.connection, "study"))
        self.assertIn("Categorized answers with retained raw source text: 3", report)
        self.assertIn("Transcript records audited in memory: 1", report)

    def test_a_switched_off_retention_stores_nothing_but_still_audits(self) -> None:
        """`fieldwork.keep_transcript: false` is a real switch, not decoration."""
        detail, transcript = self.call_with_transcript(keep_transcript=False)

        self.assertNotIn("transcript", detail)
        self.assertFalse(detail["transcript_persisted"])
        self.assertEqual(detail["transcript_format"], "timestamped-speaker-lines")
        self.assertTrue(detail["transcript_wording_matches"])
        self.assertEqual(detail["gates_seen"], ["consent_question"])
        self.assertNotIn(transcript.splitlines()[1], json.dumps(detail))

    def test_a_stored_transcript_never_carries_an_unmasked_number(self) -> None:
        detail, _ = self.call_with_transcript(
            [
                "[00:00] BOT: Sie erreichen uns unter +15550123456.",
                "[00:05] USER: Meine Nummer ist +49 151 23456789, rufen Sie da an.",
                "[00:09] USER: Oder 015123456789.",
            ]
        )

        stored = json.dumps(detail, ensure_ascii=False)
        self.assertNotIn("+15550123456", stored)
        self.assertNotIn("+49 151 23456789", stored)
        self.assertNotIn("015123456789", stored)
        self.assertIn("[number removed]", detail["transcript"])
        # No dangling plus sign: the dialed number is removed as one piece,
        # whichever of its two written forms the transcript happens to carry.
        self.assertNotIn("+[number removed]", detail["transcript"])

    def test_redaction_leaves_ordinary_numbers_in_answers_alone(self) -> None:
        """The masking must not quietly rewrite the raw answers it protects.

        `keep_raw_answer` is locked in the form definitions: the raw wording is
        the only thing that makes a returned category auditable. A redaction that
        eats years, times or frequencies would destroy exactly that, silently.
        """
        spoken = (
            "[00:04] USER: Seit 2019, zwei bis drei Mal pro Woche, "
            "meist gegen 17:37 Uhr, Hausnummer 12, Linie 3."
        )
        detail, _ = self.call_with_transcript(
            [f'[00:00] BOT: {self.questionnaire["consent_text"]}', spoken]
        )

        self.assertIn(spoken, detail["transcript"])

    def test_withdrawal_erases_the_stored_transcript(self) -> None:
        detail, transcript = self.call_with_transcript()
        self.assertIn("transcript", detail)
        frame = self.connection.execute(
            "SELECT external_ref FROM frame LIMIT 1"
        ).fetchone()

        withdraw_external_ref(self.connection, self.study_id, frame["external_ref"])

        stored = " ".join(
            str(row["detail_json"])
            for row in self.connection.execute("SELECT detail_json FROM attempt")
        )
        self.assertNotIn(transcript, stored)
        self.assertNotIn("Ja.", stored)

    def test_deliberate_anonymisation_erases_the_stored_transcript(self) -> None:
        """Cutting the link removes the spoken words too — even after sealing."""
        _, transcript = self.call_with_transcript()
        frame = self.connection.execute(
            "SELECT external_ref FROM frame LIMIT 1"
        ).fetchone()
        seal_dataset(self.connection, self.study_id, "field phase finished")

        anonymise_deliberately(
            self.connection,
            self.study_id,
            frame["external_ref"],
            "participant asked for the link to be cut",
        )

        stored = " ".join(
            str(row["detail_json"])
            for row in self.connection.execute("SELECT detail_json FROM attempt")
        )
        self.assertNotIn(transcript, stored)

    # --- Field trial: many played people, one consenting number ---------------

    def dialing_client(self, transcript: str | None = None) -> Any:
        """A client that records the number it was handed, and answers COMPLETED."""
        questionnaire = self.questionnaire
        fixture = FixtureCallClient.from_file(OUTCOMES)

        class RecordingClient:
            dialed: list[str] = []

            def call(self, sample, asked, idempotency_key):
                RecordingClient.dialed.append(sample["phone_e164"])
                structured = fixture.call(
                    {"sample_id": 1}, questionnaire, idempotency_key
                ).structured_result
                return CallOutcome(
                    status="COMPLETED",
                    run_id=f"trial-{sample['sample_id']}",
                    structured_result=structured,
                    detail={"transport": "live-api"},
                    transcript=transcript,
                )

        RecordingClient.dialed = []
        return RecordingClient()

    def test_a_field_trial_dials_one_number_while_the_people_stay_apart(self) -> None:
        """Three drawn people, one consenting line — and still three records.

        The frame refuses the same number twice, on purpose, so a trial cannot
        be built by importing one number three times. The substitution therefore
        happens on the wire only: identities, samples and attempts stay separate.
        """
        self.import_rows(3)
        draw_sample(self.connection, self.study_id, 3, 5)
        client = self.dialing_client()
        with patch.dict("os.environ", {FIELD_TRIAL_ENV: "+4915100000000"}, clear=False):
            for window in DEFAULT_WINDOWS:
                run_day(
                    self.connection,
                    get_study(self.connection, "study"),
                    window,
                    3,
                    client,
                )

        self.assertEqual(client.dialed, ["+4915100000000"] * 3)
        frame_numbers = {
            row["phone_e164"]
            for row in self.connection.execute("SELECT phone_e164 FROM frame")
        }
        self.assertEqual(len(frame_numbers), 3)
        details = [
            json.loads(row["detail_json"])
            for row in self.connection.execute("SELECT detail_json FROM attempt")
        ]
        self.assertEqual(len(details), 3)
        for detail in details:
            self.assertTrue(detail["field_trial_routed"])
            self.assertEqual(detail["field_trial_number"], "+***00")
            self.assertNotIn("+4915100000000", json.dumps(detail))

    def test_an_unusable_field_trial_number_refuses_the_whole_run(self) -> None:
        """Fail-closed: the one case where guessing would dial a stranger."""
        self.import_rows(2)
        draw_sample(self.connection, self.study_id, 2, 5)
        client = self.dialing_client()
        with patch.dict("os.environ", {FIELD_TRIAL_ENV: "0151 nonsense"}, clear=False):
            with self.assertRaisesRegex(ValueError, FIELD_TRIAL_ENV):
                run_day(
                    self.connection,
                    get_study(self.connection, "study"),
                    DEFAULT_WINDOWS[0],
                    2,
                    client,
                )

        self.assertEqual(client.dialed, [])
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) AS n FROM attempt").fetchone()["n"],
            0,
        )

    def test_a_played_withdrawal_does_not_end_the_field_trial(self) -> None:
        """The played person withdraws, the human on the line does not.

        In a field trial one human plays every respondent. A withdrawal is part
        of the role, so it purges that record — and the run goes on. Stopping
        every further call would make the trial untestable at exactly the
        outcome it most needs to rehearse. The real human's way out is not this
        flag: it is Ctrl-C, the quota, or removing the variable.
        """
        self.import_rows(2)
        draw_sample(self.connection, self.study_id, 2, 5)
        fixture = FixtureCallClient.from_file(OUTCOMES)
        structured = fixture.call({"sample_id": 1}, self.questionnaire, "unused").structured_result
        withdrawing = json.loads(json.dumps(structured))
        withdrawing["withdrawal_requested"] = True
        outcomes = iter(
            [
                CallOutcome("COMPLETED", "trial-1", withdrawing, {"transport": "live-api"}),
                CallOutcome("COMPLETED", "trial-2", structured, {"transport": "live-api"}),
            ]
        )

        class SequenceClient:
            dialed: list[str] = []

            def call(self, sample, asked, idempotency_key):
                SequenceClient.dialed.append(sample["phone_e164"])
                return next(outcomes)

        client = SequenceClient()
        with patch.dict("os.environ", {FIELD_TRIAL_ENV: "+4915100000000"}, clear=False):
            for window in DEFAULT_WINDOWS:
                run_day(
                    self.connection,
                    get_study(self.connection, "study"),
                    window,
                    2,
                    client,
                )

        self.assertEqual(SequenceClient.dialed, ["+4915100000000"] * 2)
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) AS n FROM attempt").fetchone()["n"],
            2,
        )

    def test_a_field_trial_report_does_not_look_like_an_ordinary_study(self) -> None:
        self.import_rows(2)
        draw_sample(self.connection, self.study_id, 2, 5)
        client = self.dialing_client()
        with patch.dict("os.environ", {FIELD_TRIAL_ENV: "+4915100000000"}, clear=False):
            for window in DEFAULT_WINDOWS:
                run_day(
                    self.connection, get_study(self.connection, "study"), window, 2, client
                )

        report = build_report(self.connection, get_study(self.connection, "study"))
        self.assertIn("field trial", report.lower())
        self.assertIn("2", report)
        self.assertNotIn("+4915100000000", report)

    def test_the_trial_number_never_reaches_the_stored_transcript(self) -> None:
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 5)
        client = self.dialing_client(
            transcript=(
                "[00:00] BOT: Guten Tag.\n"
                "[00:05] USER: Rufen Sie mich unter +4915100000000 zurueck."
            )
        )
        with patch.dict("os.environ", {FIELD_TRIAL_ENV: "+4915100000000"}, clear=False):
            for window in DEFAULT_WINDOWS:
                run_day(
                    self.connection, get_study(self.connection, "study"), window, 1, client
                )

        stored = " ".join(
            str(row["detail_json"])
            for row in self.connection.execute("SELECT detail_json FROM attempt")
        )
        self.assertNotIn("4915100000000", stored)
        self.assertIn("[number removed]", stored)

    def test_the_task_names_the_language_every_spoken_sentence_must_use(self) -> None:
        """Measured in a sister project on 2026-08-11: quoted English stays English.

        The voice agent speaks a quoted sentence exactly as written, whatever
        the locale says. Everything quoted here comes from the researcher's own
        instrument, but the framing around it is English, so the task has to
        name the language the conversation is held in.
        """
        task = build_task(self.questionnaire)
        self.assertIn("GESPRÄCHSSPRACHE", task)
        self.assertIn("jeder laut gesprochene Satz muss deutsch sein", task)

        english = build_task(dict(self.questionnaire, language="en"))
        self.assertIn("CONVERSATION LANGUAGE", english)
        self.assertIn("every sentence spoken aloud must be English", english)

        # A language the tables do not carry still gets a directive, in English,
        # naming the language: saying nothing is what the measurement rules out.
        french = build_task(dict(self.questionnaire, language="fr"))
        self.assertIn("CONVERSATION LANGUAGE", french)
        self.assertIn("the language with the code fr", french)

    # --- Schema shapes the API accepts (upstream issue #120) ------------------

    def sent_schemas(self, questionnaire: dict[str, Any]) -> list[dict[str, Any]]:
        """Both schemas of one create request, as they go over the wire."""
        client = LiveCallClient(
            api_key="fixture-token",
            base_url="https://example.invalid",
            first_poll_seconds=0,
            poll_seconds=0,
            poll_timeout_seconds=1,
        )
        sent: list[dict[str, Any]] = []
        responses = iter([{"id": "rest-call-1"}, {"status": "COMPLETED"}])

        def fake_request(method, path, payload=None, idempotency_key=None):
            if payload is not None:
                sent.append(payload)
            return next(responses)

        with patch.object(client, "_request", side_effect=fake_request):
            client.call(
                {"sample_id": 1, "phone_e164": "+15550123456"},
                questionnaire,
                "stable-key",
            )
        payload = sent[0]
        return [payload["result_schema"], payload["recipient_result_schema"]]

    def test_no_schema_sent_to_the_api_declares_a_nullable_union(self) -> None:
        """Upstream issue #120: a union type is rejected before the call exists.

        `{"type": ["string", "null"]}` makes `POST /v1/calls` fail with
        `result_schema_invalid`, so every live interview would die at create
        time. Absence carries what null used to carry, and this guard keeps the
        union from coming back through any of its spellings.
        """
        open_item = dict(self.questionnaire)
        open_item["questions"] = [
            *self.questionnaire["questions"],
            {"id": "q4", "wording": "Was fehlt Ihnen im Nahverkehr?", "format": "open"},
        ]
        refusal = dict(
            self.questionnaire, on_refusal={"ask_reason": True, "offer_callback": True}
        )
        for name, questionnaire in (
            ("fixture", self.questionnaire),
            ("open item", open_item),
            ("refusal fields", refusal),
        ):
            with self.subTest(questionnaire=name):
                for schema in self.sent_schemas(questionnaire):
                    self.assertEqual(nullable_unions(schema), [])

    def test_a_result_that_omits_unanswered_entries_is_recorded_like_a_null_one(
        self,
    ) -> None:
        """The proof that absence costs nothing: same record, either way.

        An agent answering the new schema leaves unanswered entries out; the
        fixtures still send explicit nulls. Both must reach the database as the
        same response and the same audit detail, or the schema change would have
        quietly changed the data.
        """
        self.import_rows(2)
        draw_sample(self.connection, self.study_id, 2, 3)
        samples = self.connection.execute(
            "SELECT id, time_window FROM sample ORDER BY id"
        ).fetchall()
        client = FixtureCallClient.from_file(OUTCOMES)
        base = client.call({"sample_id": 1}, self.questionnaire, "unused").structured_result
        unanswered = self.questionnaire["questions"][-1]["id"]

        with_null = json.loads(json.dumps(base))
        for field in ("answers", "raw_answers", "spoken_wording"):
            with_null[field][unanswered] = None
        with_absence = json.loads(json.dumps(with_null))
        for field in ("answers", "raw_answers", "spoken_wording"):
            del with_absence[field][unanswered]

        for sample, structured in zip(samples, (with_null, with_absence)):
            outcome = CallOutcome(
                status="COMPLETED",
                run_id=f"rest-{sample['id']}",
                structured_result=structured,
                detail={"transport": "live-api"},
            )
            with patch.object(client, "call", return_value=outcome):
                run_day(
                    self.connection,
                    get_study(self.connection, "study"),
                    sample["time_window"],
                    1,
                    client,
                )

        stored = self.connection.execute(
            """
            SELECT structured_json, consent, asked_verbatim_reported, wording_matches
            FROM response ORDER BY sample_id
            """
        ).fetchall()
        self.assertEqual(len(stored), 2)
        self.assertEqual(
            json.loads(stored[0]["structured_json"]),
            json.loads(stored[1]["structured_json"]),
        )
        self.assertEqual(stored[0]["consent"], stored[1]["consent"])
        self.assertEqual(
            stored[0]["asked_verbatim_reported"], stored[1]["asked_verbatim_reported"]
        )
        self.assertEqual(stored[0]["wording_matches"], stored[1]["wording_matches"])
        details = [
            json.loads(row["detail_json"])
            for row in self.connection.execute(
                "SELECT detail_json FROM attempt ORDER BY sample_id"
            )
        ]
        self.assertEqual(details[0], details[1])
        # The stored form keeps explicit nulls: absence is the wire form only.
        self.assertIsNone(json.loads(stored[1]["structured_json"])["answers"][unanswered])

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
        self.assertTrue(detail["transcript_persisted"])

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
            validate_e164("01555 0123456")
        self.assertEqual(mask_phone("+15550123456"), "+***56")
        self.assertNotIn("1234", mask_phone("+15550123456"))

    def test_duplicate_phone_cannot_create_two_person_attempts(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate phone"):
            import_frame_rows(
                self.connection,
                self.study_id,
                [("person-a", "+15550123456"), ("person-b", "+15550123456")],
            )

    def test_the_command_line_says_out_loud_that_a_trial_is_routing(self) -> None:
        """An operator must never learn from the report that it was a rehearsal."""
        workspace = Path(self.tempdir.name) / "trial-demo"
        stdout = io.StringIO()
        with patch.dict(
            "os.environ", {FIELD_TRIAL_ENV: "+4915100000000"}, clear=False
        ), contextlib.redirect_stdout(stdout):
            code = cli.main(["demo", "--workspace", str(workspace), "--seed", "42"])

        output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("field_trial=on", output)
        self.assertIn("+***00", output)
        self.assertNotIn("+4915100000000", output)

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
