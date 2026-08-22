from __future__ import annotations

import contextlib
import io
import json
import re
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall import cli
from researchcall.calls import (
    CalleAPIError,
    CallOutcome,
    FixtureCallClient,
    LiveCallClient,
)
from researchcall.calls import _transcript_from_turns as transcript_from_turns
from researchcall.database import connect, create_study, get_study, initialize, migrate, utc_now
from researchcall.field_trial import ENV_VAR as FIELD_TRIAL_ENV
from researchcall.phrases import (
    audit_floor,
    audit_transcript,
    phrases_from_questionnaire,
)
from researchcall.dataphase import (
    anonymise_deliberately,
    call_detail,
    seal_dataset,
)
from researchcall.questionnaire import (
    build_task,
    load_questionnaire_file,
    ai_disclosure_sentence,
    deletion_sentence,
    missing_disclosure_settings,
    privacy_sentence,
    result_schema,
    scope_sentence,
    stop_right_sentence,
    withdrawal_route_sentence,
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
    eligible_count,
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

    def test_a_withdrawn_number_is_not_redialled_via_a_different_frame_row(self) -> None:
        """RC7 (Endabnahme 2026-08-22, Pruefffrage): the ``dialed`` register
        showed several rows for the same (override) number with a different
        ``do_not_call`` value. Root cause: the dial guard checked only whether
        THIS frame row had been withdrawn, never whether the NUMBER itself was
        already marked ``do_not_call`` in the ``dialed`` register — a person
        who withdrew, then reappeared under a different ``external_ref`` in a
        later import batch (a second field day, a corrected frame file), was
        dialable again. Fixed at both checkpoints: ``draw_sample``/
        ``eligible_count`` (sampling.py) and ``_claim_next`` (runner.py, the
        last gate before a real call), because a sample can in principle exist
        for a number before that number's withdrawal is recorded.
        """
        phone = "+15550199001"
        import_frame_rows(self.connection, self.study_id, [("person-a", phone)])
        draw_sample(self.connection, self.study_id, 1, seed=1)
        first_sample = self.connection.execute(
            "SELECT id, time_window FROM sample"
        ).fetchone()

        fixture_client = FixtureCallClient.from_file(OUTCOMES)
        withdrawal_outcome = CallOutcome(
            status="COMPLETED",
            run_id="rest-call-withdrawal",
            structured_result={
                "consent": "granted",
                "withdrawal_requested": True,
                "asked_verbatim": True,
                "spoken_consent_wording": self.questionnaire["consent_text"],
                "spoken_wording": {},
                "answers": {},
                "raw_answers": {},
            },
            detail={"transport": "live-api"},
            transcript=(
                f'[00:00] BOT: {self.questionnaire["consent_text"]}\n'
                "[00:04] USER: Bitte loeschen Sie alles."
            ),
        )
        with patch.object(fixture_client, "call", return_value=withdrawal_outcome):
            run_day(
                self.connection,
                get_study(self.connection, "study"),
                first_sample["time_window"],
                1,
                fixture_client,
            )

        dialed = self.connection.execute(
            "SELECT do_not_call FROM dialed WHERE study_id = ? AND phone_e164 = ?",
            (self.study_id, phone),
        ).fetchone()
        self.assertEqual(dialed["do_not_call"], 1)

        # A second field day re-imports the same person under a new reference —
        # a fresh frame row, unrelated to the one that was withdrawn.
        import_frame_rows(
            self.connection, self.study_id, [("person-a-reimport", phone)]
        )
        self.assertEqual(eligible_count(self.connection, self.study_id), 0)
        with self.assertRaises(ValueError):
            draw_sample(self.connection, self.study_id, 1, seed=2)

        # And even a sample that already exists for that number — drawn before
        # this guard ran, or inserted by any other path — is refused at the
        # last checkpoint before a real call goes out.
        second_frame = self.connection.execute(
            "SELECT id FROM frame WHERE external_ref = ?", ("person-a-reimport",)
        ).fetchone()
        self.connection.execute(
            "INSERT INTO sample(study_id, frame_id, time_window, drawn_at) "
            "VALUES (?, ?, ?, ?)",
            (self.study_id, second_frame["id"], DEFAULT_WINDOWS[0], utc_now()),
        )
        self.connection.commit()
        counts = run_day(
            self.connection,
            get_study(self.connection, "study"),
            DEFAULT_WINDOWS[0],
            5,
            fixture_client,
        )
        self.assertEqual(counts, {})
        self.assertIsNone(
            self.connection.execute(
                "SELECT a.id FROM attempt a JOIN sample s ON s.id = a.sample_id "
                "WHERE s.frame_id = ?",
                (second_frame["id"],),
            ).fetchone()
        )

    # --- The floor every call stands on --------------------------------------

    def study_with_disclosure(self, **overrides: Any) -> dict[str, Any]:
        return dict(
            self.questionnaire,
            commissioner="Universität Beispielstadt",
            withdrawal_contact="widerruf@example.invalid",
            **overrides,
        )

    def test_every_call_discloses_the_machine_and_the_right_to_stop(self) -> None:
        """Measured in the first live call: neither was said.

        The transcript opened with the study's own consent sentence and nothing
        else — no word that a machine was calling, no way out during the call,
        no route to withdraw afterwards. None of that may depend on what a
        researcher happened to write into their instrument.
        """
        task = build_task(self.study_with_disclosure())

        self.assertIn("künstliche Intelligenz", task)
        self.assertIn("Universität Beispielstadt", task)
        self.assertIn("jederzeit", task)
        # RC2: an e-mail address is quoted in its spoken form, not written form
        # — the raw "@" never reaches a sentence the agent must say verbatim.
        self.assertIn("widerruf at example Punkt invalid", task)
        self.assertNotIn("widerruf@example.invalid", task)
        # Order: the machine is named before consent is asked, and consent is
        # asked before any question. The withdrawal route comes at the end.
        disclosure = task.index("künstliche Intelligenz")
        consent = task.index("CONSENT (say exactly)")
        first_question = task.index(self.questionnaire["questions"][0]["wording"])
        withdrawal = task.index("widerruf at example Punkt invalid")
        self.assertLess(disclosure, consent)
        self.assertLess(consent, first_question)
        self.assertLess(first_question, withdrawal)

    def test_the_floor_speaks_the_study_language(self) -> None:
        english = build_task(
            self.study_with_disclosure(language="en", consent_text="May we ask you three questions?")
        )

        self.assertIn("artificial intelligence", english)
        self.assertIn("at any time", english)
        self.assertIn("withdraw", english)
        self.assertNotIn("künstliche Intelligenz", english)

    def test_the_disclosure_and_the_stop_right_are_audited_like_consent(self) -> None:
        questionnaire = self.full_study()
        phrases = {phrase.key for phrase in phrases_from_questionnaire(questionnaire)}
        self.assertEqual(
            phrases,
            {"consent_question", "ai_disclosure", "stop_right", "data_statement"},
        )

        spoken_without_disclosure = transcript_from_turns(
            [
                {
                    "offset_seconds": 0,
                    "speaker": "bot",
                    "text": questionnaire["consent_text"],
                },
                {"offset_seconds": 9, "speaker": "bot", "text": stop_right_sentence("de")},
            ]
        )
        findings = audit_transcript(
            spoken_without_disclosure, phrases_from_questionnaire(questionnaire)
        )

        self.assertIn("ai_disclosure", findings["gates_missed"])
        self.assertIn("stop_right", findings["gates_seen"])

    def test_a_study_without_a_withdrawal_route_cannot_go_live(self) -> None:
        """Fail-closed: no route to withdraw, no live call.

        A dry run still works — refusing it would stop the rehearsal that is
        supposed to surface exactly this — but it says what is missing.
        """
        stripped = {
            key: value
            for key, value in self.questionnaire.items()
            if key not in ("commissioner", "withdrawal_contact")
        }
        self.connection.execute(
            "UPDATE study SET questionnaire_json = ? WHERE id = ?",
            (json.dumps(stripped, ensure_ascii=False), self.study_id),
        )
        self.connection.commit()
        self.assertEqual(
            missing_disclosure_settings(stripped), ["commissioner", "withdrawal_contact"]
        )
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        window = self.connection.execute("SELECT time_window FROM sample").fetchone()[0]
        self.connection.close()
        arguments = [
            "--db", str(self.db_path), "run-day", "--study", "study",
            "--window", window, "--limit", "1",
        ]

        stderr = io.StringIO()
        with patch(
            "researchcall.cli.LiveCallClient.from_environment",
            side_effect=AssertionError("no live client may be built"),
        ), contextlib.redirect_stderr(stderr):
            code = cli.main(
                [*arguments, "--live", "--confirm-live", "CALL 1", "--consent-attested"]
            )
        self.assertEqual(code, 2)
        self.assertIn("withdrawal_contact", stderr.getvalue())

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(cli.main(arguments), 0)
        self.assertIn("disclosure_incomplete", stdout.getvalue())

    def test_the_right_to_stop_is_not_said_twice(self) -> None:
        """The workbench already puts it into the consent sentence.

        Saying it again as its own block would be harmless but sloppy, and the
        check for it is literal: the sentence is either in the consent text or
        it is not.
        """
        from researchcall import instrument
        from test_instrument import VALUES

        built, _ = instrument.build_questionnaire(dict(VALUES), "de")
        built["commissioner"] = "Universität Beispielstadt"
        built["withdrawal_contact"] = "widerruf@example.invalid"

        task = build_task(built)

        self.assertEqual(task.count(stop_right_sentence("de")), 1)
        self.assertIn("künstliche Intelligenz", task)

    def test_the_withdrawal_contact_is_spoken_not_spelt_out(self) -> None:
        """RC2 (Endabnahme 2026-08-22): a configured e-mail contact came back on
        the phone read letter by letter ("w, i, d, e, r, r, u, f, at, e, x,
        ... dot invalid") — technically correct and unintelligible. An e-mail
        address must reach the agent already in its ordinary spoken form, so
        the sentence it has to say verbatim reads naturally; the literal "@"
        must never appear in it, in either study language.
        """
        german = build_task(
            dict(
                self.questionnaire,
                commissioner="Universität Beispielstadt",
                withdrawal_contact="widerruf@example.invalid",
            )
        )
        english = build_task(
            dict(
                self.questionnaire,
                language="en",
                consent_text="May we ask you three questions?",
                commissioner="Example University",
                withdrawal_contact="withdraw@example.invalid",
            )
        )
        self.assertIn("widerruf at example Punkt invalid", german)
        self.assertNotIn("@", german)
        self.assertIn("withdraw at example dot invalid", english)
        self.assertNotIn("@", english)

        # A contact not shaped like an e-mail address is left exactly as
        # configured — there is no single spoken form to guess for a phone
        # number or a postal address.
        untouched = build_task(
            dict(
                self.questionnaire,
                commissioner="Universität Beispielstadt",
                withdrawal_contact="Büro für Datenschutz, Hauptstraße 1",
            )
        )
        self.assertIn("Büro für Datenschutz, Hauptstraße 1", untouched)

    def test_a_mid_interview_withdrawal_is_announced_before_the_call_ends(self) -> None:
        """RC5 (Endabnahme 2026-08-22, live befund): a person aborted mid-
        interview, the purge ran (``runner._purge_frame``: 0 rows left in
        ``response``), but the agent never said the answers would be deleted
        before ending the call — the task text told it only to "stop
        immediately". This is a string assertion on the LIVE goal-generation
        path (``build_task``, the same function ``LiveCallClient.call`` sends
        as ``payload["task"]``), not on a fixture.
        """
        task = build_task(self.full_study())
        self.assertIn(
            "If the person withdraws consent or asks to end the interview early, "
            'say exactly: "Ihre bisherigen Antworten werden jetzt gelöscht." '
            "— then end the call immediately and set withdrawal_requested=true.",
            task,
        )

        english = build_task(
            self.full_study(
                language="en",
                consent_text="May we ask you three questions?",
                privacy_short=(
                    "Your answers are stored pseudonymously and deleted after two years."
                ),
            )
        )
        self.assertIn(
            "If the person withdraws consent or asks to end the interview early, "
            'say exactly: "The answers you have given so far will now be deleted." '
            "— then end the call immediately and set withdrawal_requested=true.",
            english,
        )

    # --- Floor sentences that are not gates, but still owed ------------------

    def spoken(self, *keys: str) -> str:
        """A transcript containing exactly the named floor sentences, in order."""
        study = self.full_study()
        sentences = {
            "disclosure": ai_disclosure_sentence(study),
            "scope": scope_sentence(study),
            "data": privacy_sentence(study),
            "stop": stop_right_sentence(study["language"]),
            "deletion": deletion_sentence(study),
            "consent": study["consent_text"],
            "withdrawal": withdrawal_route_sentence(study),
        }
        return transcript_from_turns(
            [
                {"offset_seconds": index * 5, "speaker": "bot", "text": sentences[key]}
                for index, key in enumerate(keys)
            ]
        )

    def test_a_skipped_floor_sentence_is_a_hole_and_is_reported(self) -> None:
        """The gap this map found: composed, spoken, and verified by nothing.

        A sentence is owed when a LATER one was spoken — the order is fixed, so
        anything before something that was said must have been said too. That is
        a literal rule over the sequence, not a judgement about the call.
        """
        findings = audit_floor(
            self.spoken("disclosure", "data", "stop", "deletion", "consent"),
            self.full_study(),
        )

        self.assertEqual(findings["floor_missing"], ["scope"])
        self.assertNotIn("withdrawal", findings["floor_missing"])

    def test_a_call_that_ended_early_is_not_accused_of_skipping(self) -> None:
        """Somebody hung up during the opening; nothing was skipped.

        The same reasoning that kept the withdrawal route out of the gates: a
        conversation that never got that far never owed the sentence, and
        flagging it would fill the queue with hang-ups instead of findings.
        """
        findings = audit_floor(self.spoken("disclosure", "scope"), self.full_study())

        self.assertEqual(findings["floor_missing"], [])
        self.assertEqual(
            findings["floor_not_reached"], ["data", "stop", "deletion", "withdrawal"]
        )

    def test_the_withdrawal_route_is_owed_once_the_interview_ran(self) -> None:
        """It is the one sentence whose debt depends on the outcome, not the order."""
        complete = self.spoken(
            "disclosure", "scope", "data", "stop", "deletion", "consent", "withdrawal"
        )
        without_route = self.spoken(
            "disclosure", "scope", "data", "stop", "deletion", "consent"
        )

        self.assertEqual(
            audit_floor(complete, self.full_study(), completed=True)["floor_missing"], []
        )
        self.assertEqual(
            audit_floor(without_route, self.full_study(), completed=True)["floor_missing"],
            ["withdrawal"],
        )
        # …and an unfinished call still owes nothing for it.
        self.assertEqual(
            audit_floor(without_route, self.full_study(), completed=False)["floor_missing"],
            [],
        )

    def test_a_hole_in_the_floor_opens_a_review_case(self) -> None:
        structured = self.fixture_structured_result()
        turns = [
            {"offset_seconds": 0, "speaker": "bot", "text": ai_disclosure_sentence(self.questionnaire)},
            # scope deliberately left out
            {"offset_seconds": 4, "speaker": "bot", "text": privacy_sentence(self.questionnaire)},
            {"offset_seconds": 6, "speaker": "bot", "text": stop_right_sentence(self.questionnaire["language"])},
            {"offset_seconds": 8, "speaker": "bot", "text": deletion_sentence(self.questionnaire)},
            {"offset_seconds": 10, "speaker": "bot", "text": self.questionnaire["consent_text"]},
        ]
        offset = 20
        for question in self.questionnaire["questions"]:
            turns.append({"offset_seconds": offset, "speaker": "bot", "text": question["wording"]})
            turns.append(
                {
                    "offset_seconds": offset + 3,
                    "speaker": "user",
                    "text": structured["raw_answers"][question["id"]],
                }
            )
            offset += 10
        detail, _ = self.call_with_transcript(
            transcript_from_turns(turns).splitlines()
        )

        self.assertEqual(detail["floor_missing"], ["scope", "withdrawal"])
        reason = self.connection.execute("SELECT reason FROM review").fetchone()
        self.assertIsNotNone(reason, "a skipped floor sentence must reach the queue")
        self.assertIn("floor_missed", reason["reason"])

    # --- What the service says when it refuses (Befund F) --------------------

    def test_a_refused_service_answer_names_its_reason(self) -> None:
        """HTTP 402 arrived live as a bare RuntimeError — unreadable for anyone.

        The bearer token travels in the header, never in the body, so the code,
        the message and the reason code are diagnostics rather than secrets. The
        body as a whole is still not stored: only those three fields are.
        """
        client = LiveCallClient(
            api_key="fixture-token", base_url="https://example.invalid",
            first_poll_seconds=0, poll_seconds=0, poll_timeout_seconds=1,
        )
        body = json.dumps(
            {
                "error": {
                    "code": "insufficient_balance",
                    "message": "Insufficient CALL-E balance. Please top up at https://example.invalid/billing and try again.",
                    "details": {"reason_code": "iams_balance_insufficient"},
                }
            }
        ).encode("utf-8")

        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                "https://example.invalid/v1/calls", 402, "Payment Required", {}, io.BytesIO(body)
            )

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(CalleAPIError) as caught:
                client.call(
                    {"sample_id": 1, "phone_e164": "+15550123456"},
                    self.full_study(),
                    "key",
                )

        error = caught.exception
        self.assertEqual(error.status_code, 402)
        self.assertEqual(error.code, "insufficient_balance")
        self.assertEqual(error.reason_code, "iams_balance_insufficient")
        self.assertIn("top up", error.message)
        self.assertFalse(error.dialled, "402 is refused before any call exists")

    def test_a_refusal_does_not_burn_the_people_it_never_dialled(self) -> None:
        """The expensive half of the finding.

        A 402 after the third of ten calls must leave seven records callable.
        The attempt row is claimed before the request, so a refusal that never
        reached the wire has to give it back.
        """
        self.import_rows(3)
        draw_sample(self.connection, self.study_id, 3, 3)
        window = self.connection.execute("SELECT time_window FROM sample").fetchone()[0]

        class RefusingClient:
            calls = 0

            def call(self, sample, asked, idempotency_key):
                RefusingClient.calls += 1
                raise CalleAPIError(402, "insufficient_balance", "no balance", "iams")

        with self.assertRaises(CalleAPIError):
            run_day(
                self.connection,
                get_study(self.connection, "study"),
                window,
                3,
                RefusingClient(),
            )

        self.assertEqual(RefusingClient.calls, 1, "the run stops at the first refusal")
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) AS n FROM attempt").fetchone()["n"],
            0,
            "a record that was never dialled must stay callable",
        )

    def test_a_transport_error_that_did_reach_the_service_keeps_its_attempt(self) -> None:
        """A timeout mid-call is not a refusal: that person WAS dialled."""
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        window = self.connection.execute("SELECT time_window FROM sample").fetchone()[0]

        class TimingOut:
            def call(self, sample, asked, idempotency_key):
                raise TimeoutError("polling exceeded")

        run_day(
            self.connection, get_study(self.connection, "study"), window, 1, TimingOut()
        )

        row = self.connection.execute(
            "SELECT call_status, detail_json FROM attempt"
        ).fetchone()
        self.assertEqual(row["call_status"], "FAILED")
        self.assertIn("TimeoutError", row["detail_json"])

    def test_the_command_line_explains_a_refusal_instead_of_a_stack_trace(self) -> None:
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        window = self.connection.execute("SELECT time_window FROM sample").fetchone()[0]
        self.connection.close()
        stderr = io.StringIO()

        class Refusing:
            @staticmethod
            def from_environment(progress_callback=None):
                class Client:
                    def call(self, *args):
                        raise CalleAPIError(
                            402,
                            "insufficient_balance",
                            "Insufficient CALL-E balance. Please top up at https://example.invalid/billing",
                            "iams_balance_insufficient",
                        )

                return Client()

        with patch("researchcall.cli.LiveCallClient", Refusing), contextlib.redirect_stderr(stderr):
            code = cli.main(
                [
                    "--db", str(self.db_path), "run-day", "--study", "study",
                    "--window", window, "--limit", "1", "--live",
                    "--confirm-live", "CALL 1", "--consent-attested",
                ]
            )

        self.assertEqual(code, 3, "a refused service gets its own exit code")
        message = stderr.getvalue()
        self.assertIn("402", message)
        self.assertIn("insufficient_balance", message)
        self.assertIn("top up", message)
        self.assertIn("nothing was dialled", message)

    # --- The floor after live findings A-E (2026-08-11) ----------------------

    def full_study(self, **overrides: Any) -> dict[str, Any]:
        study = dict(
            self.questionnaire,
            commissioner="Universität Beispielstadt",
            withdrawal_contact="widerruf@example.invalid",
            privacy_short=(
                "Ihre Antworten werden pseudonym gespeichert und nach zwei Jahren gelöscht."
            ),
        )
        study.update(overrides)
        return study

    def test_the_floor_says_scope_privacy_and_deletion_in_one_fixed_order(self) -> None:
        """What the live calls showed missing, in the order a person needs it."""
        task = build_task(self.full_study())

        disclosure = task.index("künstliche Intelligenz")
        scope = task.index("umfasst bis zu")
        privacy = task.index("pseudonym gespeichert")
        stop = task.index("jederzeit ohne Angabe von Gründen beenden")
        consent = task.index("CONSENT (say exactly)")
        first_question = task.index(self.questionnaire["questions"][0]["wording"])
        # RC2: the spoken form, not the written e-mail address.
        withdrawal = task.index("widerruf at example Punkt invalid")
        self.assertLess(disclosure, scope)
        self.assertLess(scope, privacy)
        self.assertLess(privacy, stop)
        self.assertLess(stop, consent)
        self.assertLess(consent, first_question)
        self.assertLess(first_question, withdrawal)
        self.assertIn("dauert etwa", task)

    def test_the_floor_speaks_english_too(self) -> None:
        english = build_task(
            self.full_study(
                language="en",
                consent_text="May we ask you three questions?",
                privacy_short="Your answers are stored pseudonymously and deleted after two years.",
            )
        )
        self.assertIn("artificial intelligence", english)
        self.assertIn("up to", english)
        self.assertIn("stored pseudonymously", english)
        self.assertIn("deleted", english)
        self.assertNotIn("umfasst bis zu", english)

    def test_no_ethics_promise_is_spoken_twice_in_either_path(self) -> None:
        """Befund A, measured on both paths rather than on one sentence.

        The old check counted occurrences of one exact sentence and passed
        while the same promise was made twice in different words — in the file
        path the voluntariness, in the workbench path the right to stop.
        """
        from researchcall import instrument
        from test_instrument import VALUES

        built, _ = instrument.build_questionnaire(dict(VALUES), "de")
        built.update(
            commissioner="Beispiel-Institut",
            withdrawal_contact="widerruf@example.invalid",
            privacy_short="Antworten werden pseudonym gespeichert.",
        )
        for name, questionnaire in (
            ("file", self.full_study()),
            ("workbench", built),
        ):
            with self.subTest(path=name):
                spoken = " ".join(re.findall(r'"([^"]{15,})"', build_task(questionnaire)))
                for promise in ("Teilnahme ist freiwillig", "jederzeit", "künstliche Intelligenz"):
                    self.assertEqual(
                        spoken.count(promise), 1, f"{promise!r} is said more than once"
                    )

    def test_the_duration_is_said_in_every_call(self) -> None:
        """Locked by user decision of 2026-08-11, like consent and the stop right."""
        task = build_task(self.full_study())
        self.assertIn("dauert etwa", task)
        self.assertIn("umfasst bis zu", task)

    def test_the_duration_is_grammatically_correct_for_one_minute(self) -> None:
        """RC3 (Endabnahme 2026-08-22): "dauert etwa 1 Minuten" was spoken aloud.

        A study whose instrument estimates exactly one minute must say "1
        Minute", not "1 Minuten" — the same rule that keeps "1 Frage" out of
        the plural.
        """
        task = build_task(self.full_study(estimated_minutes=1))
        self.assertIn("dauert etwa 1 Minute ", task)
        self.assertNotIn("1 Minuten", task)

        multiple = build_task(self.full_study(estimated_minutes=5))
        self.assertIn("dauert etwa 5 Minuten ", multiple)
        self.assertNotIn("5 Minute ", multiple)

        # Even a study that still carries the old off-switch says it: the field
        # is locked now, so an old value cannot silence the promise.
        self.assertIn("umfasst bis zu", build_task(self.full_study(announce_duration=False)))

    def test_a_study_without_a_privacy_sentence_cannot_go_live(self) -> None:
        self.assertEqual(
            missing_disclosure_settings(
                {k: v for k, v in self.full_study().items() if k != "privacy_short"}
            ),
            ["privacy_short"],
        )
        self.assertEqual(missing_disclosure_settings(self.full_study()), [])

    def test_the_deletion_promise_says_what_the_code_actually_does(self) -> None:
        """Befund E: deletion happens on request, not on every hang-up.

        A sentence promising deletion "if you stop" would be wrong: ending the
        call leaves partial answers, only `withdrawal_requested` purges them.
        """
        task = build_task(self.full_study())

        self.assertIn("sagen Sie es mir", task)
        self.assertNotIn("Wenn Sie abbrechen, werden Ihre", task)

    def test_the_task_bounds_how_often_one_question_may_be_repeated(self) -> None:
        """Befund B: repeating a question verbatim forever is not standardisation."""
        task = build_task(self.full_study())

        self.assertIn("at most twice", task)
        self.assertIn("do not repeat it a third time", task)
        self.assertIn("leave the entry in answers out", task)

    # --- What the first real call (2026-08-11) showed -------------------------

    LIVE_CONSENT_TURNS = [
        {"offset_seconds": 0, "speaker": "bot", "text": "Guten Tag."},
        {
            "offset_seconds": 0,
            "speaker": "bot",
            "text": "Wir führen eine kurze wissenschaftliche Befragung zur Mobilität durch.",
        },
        {"offset_seconds": 6, "speaker": "bot", "text": "Dürfen wir Ihnen drei Fragen stellen?"},
        {"offset_seconds": 11, "speaker": "user", "text": "Hallo. Ja."},
    ]

    def test_a_sentence_split_across_turns_still_counts_as_spoken(self) -> None:
        """Measured live: the agent says the consent sentence in three turns.

        Concatenated it is character-identical to the required phrase, so this
        is a line break, not a paraphrase. Recognition stays literal — the whole
        sentence must appear as one contiguous piece of what the bot said — but
        it is no longer defeated by the transcript's own timestamps sitting
        between the parts, nor by an interjection in the middle.
        """
        interrupted = list(self.LIVE_CONSENT_TURNS)
        interrupted.insert(2, {"offset_seconds": 4, "speaker": "user", "text": "Hallo?"})
        transcript = transcript_from_turns(interrupted)

        findings = audit_transcript(
            transcript, phrases_from_questionnaire(self.questionnaire)
        )

        self.assertIn("consent_question", findings["gates_seen"])
        self.assertNotIn("consent_question", findings["gates_missed"])

    def test_a_gate_is_not_satisfied_by_the_other_side_saying_it(self) -> None:
        """A gate is a sentence the agent owes, not one it may hear."""
        transcript = transcript_from_turns(
            [
                {"offset_seconds": 0, "speaker": "bot", "text": "Guten Tag."},
                {
                    "offset_seconds": 3,
                    "speaker": "user",
                    "text": self.questionnaire["consent_text"],
                },
            ]
        )

        findings = audit_transcript(
            transcript, phrases_from_questionnaire(self.questionnaire)
        )

        self.assertIn("consent_question", findings["gates_missed"])
        self.assertEqual(findings["gates_seen"], [])

    def test_the_wording_check_also_reads_across_turns(self) -> None:
        """The same split defeats the verbatim check one line further on.

        In the live record it stayed invisible: the schema error skipped the
        block before it could run. Once that is fixed it would open a wording
        mismatch for a sentence that was spoken exactly.
        """
        structured = self.fixture_structured_result()
        turns = [*self.floor_turns(), *self.LIVE_CONSENT_TURNS]
        offset = 20
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
        detail, _ = self.call_with_transcript(transcript_from_turns(turns).splitlines())

        self.assertTrue(detail["transcript_wording_matches"])
        self.assertEqual(detail["gates_missed"], [])

    def test_a_call_level_result_is_never_read_as_a_recipient_result(self) -> None:
        """The most likely cause of the live schema error, reproduced offline.

        Two schemas travel with every call: the recipient's, which carries the
        interview, and the call-level one, which counts completed calls. Where
        the service puts the call-level object under `structured_result`, the
        old lookup returned `{"completed_count": 1}` — and validation then said
        the fields do not match the recipient schema, which is true and useless.
        """
        ours = self.fixture_structured_result()
        shapes = {
            "beside": {
                "result": {"structured_result": {"completed_count": 1}},
                "recipients": [{"structured_result": ours}],
            },
            "nested": {
                "result": {
                    "structuredResult": {"completed_count": 1},
                    "recipients": [{"structured_result": ours}],
                }
            },
        }
        for name, payload in shapes.items():
            with self.subTest(shape=name):
                self.assertEqual(LiveCallClient._structured_result(payload), ours)

        # Nothing per recipient is not "no problem": a completed call owes a result.
        empty = {"result": {"structured_result": {"completed_count": 1}}, "recipients": [{}]}
        self.assertIsNone(LiveCallClient._structured_result(empty))
        self.assertEqual(
            LiveCallClient._unrecognised_result_fields(empty), ["completed_count"]
        )

        # But the shape measured on 2026-08-01 — the interview itself arriving
        # call-level — must keep working; it carries the recipient's fields.
        measured = {"result": {"structuredResult": ours}}
        self.assertEqual(LiveCallClient._structured_result(measured), ours)

    def test_a_completed_call_without_a_recipient_result_is_flagged(self) -> None:
        detail, _ = self.finish_one(
            CallOutcome("COMPLETED", "live-1", None, {"transport": "live-api"})
        )

        self.assertIn("no recipient result", detail["structured_result_error"])

    def test_a_rejected_result_is_kept_so_the_next_look_is_not_blind(self) -> None:
        """A schema error that hides the payload cannot be diagnosed at all.

        This is the one place foreign, unvalidated data enters the record. It is
        capped, it is stripped of numbers, and its values are only kept when the
        study keeps transcripts anyway — otherwise the error path would smuggle
        back the spoken words that switch is there to refuse.
        """
        detail, _ = self.finish_one(
            CallOutcome(
                "COMPLETED",
                "live-2",
                {"completed_count": 1, "phone": "+4915100000000"},
                {"transport": "live-api"},
            )
        )

        self.assertIn("completed_count", detail["structured_result_error"])
        self.assertIn("consent", detail["structured_result_error"])
        rejected = json.dumps(detail["structured_result_rejected"], ensure_ascii=False)
        self.assertIn("completed_count", rejected)
        self.assertNotIn("+4915100000000", rejected)

    def test_a_rehearsal_does_not_use_up_the_one_call_a_person_gets(self) -> None:
        """Rehearsing the machinery must not spend the person.

        Every record gets one call. A rehearsal that claims it leaves the study
        with nobody left to actually ring — which is what the first field trial
        ran into.
        """
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        window = self.connection.execute("SELECT time_window FROM sample").fetchone()[0]
        client = FixtureCallClient.from_file(OUTCOMES)
        study = get_study(self.connection, "study")

        rehearsed = run_day(self.connection, study, window, 1, client, rehearsal=True)
        real = run_day(self.connection, study, window, 1, client)
        blocked = run_day(self.connection, study, window, 1, client)

        self.assertEqual(sum(rehearsed.values()), 1)
        self.assertEqual(sum(real.values()), 1, "the person must still be callable")
        self.assertEqual(sum(blocked.values()), 0, "but only once for real")
        rows = self.connection.execute(
            "SELECT attempt_no, rehearsal FROM attempt ORDER BY attempt_no"
        ).fetchall()
        self.assertEqual([(r["attempt_no"], r["rehearsal"]) for r in rows], [(1, 1), (2, 0)])
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) AS n FROM dialed").fetchone()["n"],
            1,
            "only the real call belongs in the dialed register",
        )

    def test_a_database_from_before_rehearsals_gains_the_column(self) -> None:
        """The field trial's own state file must survive the upgrade."""
        old = sqlite3.connect(self.db_path)
        try:
            old.execute("ALTER TABLE attempt DROP COLUMN rehearsal")
            old.commit()
        finally:
            old.close()

        migrated = connect(self.db_path)
        self.addCleanup(migrated.close)
        applied = migrate(migrated)

        self.assertIn("attempt.rehearsal", applied)
        columns = {
            row["name"] for row in migrated.execute("PRAGMA table_info(attempt)")
        }
        self.assertIn("rehearsal", columns)

    def test_the_command_line_offers_the_rehearsal_and_refuses_it_live(self) -> None:
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        window = self.connection.execute("SELECT time_window FROM sample").fetchone()[0]
        self.connection.close()
        stdout = io.StringIO()
        arguments = [
            "--db", str(self.db_path), "run-day", "--study", "study",
            "--window", window, "--limit", "1",
        ]
        with contextlib.redirect_stdout(stdout):
            code = cli.main([*arguments, "--rehearsal"])
        self.assertEqual(code, 0)
        self.assertIn("mode=rehearsal", stdout.getvalue())

        # A live call is never a rehearsal, and the two flags together are a
        # contradiction the operator should hear about, not a silent winner.
        self.assertEqual(
            cli.main([*arguments, "--rehearsal", "--live", "--confirm-live", "CALL 1"]),
            2,
        )

        connection = connect(self.db_path)
        self.addCleanup(connection.close)
        report = build_report(connection, get_study(connection, "study"))
        self.assertIn("Rehearsal attempts, excluded from every count: 1", report)
        self.assertIn("- Attempts recorded: 0", report)

    def test_a_rehearsed_withdrawal_does_not_destroy_the_person(self) -> None:
        """A fixture's withdrawal is a rehearsal of one, not a person's request."""
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        window = self.connection.execute("SELECT time_window FROM sample").fetchone()[0]
        fixture = FixtureCallClient.from_file(OUTCOMES)
        structured = fixture.call({"sample_id": 1}, self.questionnaire, "unused").structured_result
        structured["withdrawal_requested"] = True
        client = FixtureCallClient.from_file(OUTCOMES)
        with patch.object(
            client,
            "call",
            return_value=CallOutcome("COMPLETED", "rehearsal", structured, {}),
        ):
            run_day(
                self.connection,
                get_study(self.connection, "study"),
                window,
                1,
                client,
                rehearsal=True,
            )

        frame = self.connection.execute(
            "SELECT phone_e164, withdrawn_at FROM frame"
        ).fetchone()
        self.assertIsNotNone(frame["phone_e164"])
        self.assertIsNone(frame["withdrawn_at"])

    # --- Field trial: many played people, one consenting number ---------------

    def finish_one(self, outcome: CallOutcome) -> tuple[dict[str, Any], str | None]:
        """Put one prepared outcome through the runner and read its record."""
        self.import_rows(1)
        draw_sample(self.connection, self.study_id, 1, 3)
        window = self.connection.execute("SELECT time_window FROM sample").fetchone()[0]
        client = FixtureCallClient.from_file(OUTCOMES)
        with patch.object(client, "call", return_value=outcome):
            run_day(
                self.connection, get_study(self.connection, "study"), window, 1, client
            )
        detail = json.loads(
            self.connection.execute(
                "SELECT detail_json FROM attempt ORDER BY id DESC LIMIT 1"
            ).fetchone()["detail_json"]
        )
        return detail, outcome.transcript

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

    def floor_turns(self) -> list[dict[str, object]]:
        """What every call now opens with: who is calling, and the way out."""
        return [
            {
                "offset_seconds": 0,
                "speaker": "bot",
                "text": ai_disclosure_sentence(self.questionnaire),
            },
            {
                "offset_seconds": 2,
                "speaker": "bot",
                "text": privacy_sentence(self.questionnaire),
            },
            {
                "offset_seconds": 3,
                "speaker": "bot",
                "text": stop_right_sentence(self.questionnaire["language"]),
            },
        ]

    def interview_turns(self, structured: dict[str, object]) -> list[dict[str, object]]:
        """The turn list a completed interview leaves behind, as the API returns it."""
        turns: list[dict[str, object]] = [
            *self.floor_turns(),
            {
                "offset_seconds": 6,
                "speaker": "bot",
                "text": self.questionnaire["consent_text"],
            },
            {"offset_seconds": 10, "speaker": "user", "text": "Ja, gerne."},
        ]
        offset = 16
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
            lines[0], f"[00:00] BOT: {ai_disclosure_sentence(self.questionnaire)}"
        )
        # index 1 and 2 are the data statement and the right to stop
        self.assertEqual(
            lines[3], f'[00:06] BOT: {self.questionnaire["consent_text"]}'
        )
        self.assertEqual(lines[4], "[00:10] USER: Ja, gerne.")
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
        self.assertEqual(
            detail["gates_seen"],
            ["ai_disclosure", "consent_question", "data_statement", "stop_right"],
        )
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
