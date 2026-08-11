"""Regressions for dispatch capability, the review queue, and gate phrases.

Three modules, one test file, because they guard one storyline: how a call may
be placed, what happens when its checks are not green, and which sentences must
demonstrably fall.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall.calls import FixtureCallClient
from researchcall.questionnaire import (
    ai_disclosure_sentence,
    privacy_sentence,
    stop_right_sentence,
)
from researchcall.database import connect, initialize, migrate, utc_now
from researchcall.dispatch import (
    MULTI_CALL,
    Capability,
    CapabilityStatus,
    DispatchMode,
    evaluate_probe,
    get_capability,
    record_capability,
    resolve_dispatch,
)
from researchcall.phrases import (
    GatePhrase,
    PhraseMonitor,
    audit_transcript,
    phrases_from_questionnaire,
)
from researchcall.review import (
    ReviewDecision,
    ReviewReason,
    decide,
    guard_aggregation,
    open_case_count,
    open_cases,
    open_review,
    reasons_for_attempt,
)


def memory_db():
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    initialize(handle.name)
    return connect(handle.name)


def make_study(connection):
    connection.execute(
        """
        INSERT INTO study(study_key, title, questionnaire_json, created_at)
        VALUES ('s1', 'Test', '{}', ?)
        """,
        (utc_now(),),
    )
    connection.commit()
    return int(connection.execute("SELECT id FROM study").fetchone()["id"])


def make_attempt(connection, study_id, sample_no=1):
    connection.execute(
        "INSERT INTO frame(study_id, external_ref, phone_e164) VALUES (?, ?, ?)",
        (study_id, f"p{sample_no}", f"+155501010{sample_no:02d}"),
    )
    frame_id = int(connection.execute("SELECT MAX(id) AS m FROM frame").fetchone()["m"])
    connection.execute(
        """
        INSERT INTO sample(study_id, frame_id, time_window, drawn_at)
        VALUES (?, ?, 'morning', ?)
        """,
        (study_id, frame_id, utc_now()),
    )
    sample_id = int(connection.execute("SELECT MAX(id) AS m FROM sample").fetchone()["m"])
    connection.execute(
        """
        INSERT INTO attempt(sample_id, attempt_no, started_at, call_status, idempotency_key)
        VALUES (?, 1, ?, 'COMPLETED', ?)
        """,
        (sample_id, utc_now(), f"key-{study_id}-{sample_no}"),
    )
    connection.commit()
    return int(connection.execute("SELECT MAX(id) AS m FROM attempt").fetchone()["m"])


class DispatchTestCase(unittest.TestCase):
    """Availability-first: multi only with a verified probe AND a batch path."""

    def setUp(self):
        self.connection = memory_db()
        self.fixture = FixtureCallClient(
            [{"status": "COMPLETED", "answers": {}, "raw_answers": {}}]
        )

    def test_an_unprobed_capability_reads_untested_not_unavailable(self):
        capability = get_capability(self.connection, MULTI_CALL)
        self.assertIs(capability.status, CapabilityStatus.UNTESTED)

    def test_mono_needs_no_permission(self):
        decision = resolve_dispatch(self.connection, DispatchMode.MONO, self.fixture)
        self.assertIs(decision.mode, DispatchMode.MONO)
        self.assertIsNone(decision.downgrade_reason)

    def test_multi_without_probe_downgrades_with_the_reason_written_down(self):
        decision = resolve_dispatch(self.connection, DispatchMode.MULTI, self.fixture)
        self.assertIs(decision.mode, DispatchMode.MONO)
        self.assertTrue(decision.downgraded)
        self.assertIn("untested", decision.downgrade_reason)
        self.assertIn("dispatch_downgrade_reason", decision.to_detail())

    def test_multi_with_verified_probe_and_batch_transport_is_granted(self):
        record_capability(
            self.connection,
            MULTI_CALL,
            CapabilityStatus.VERIFIED,
            {"probe": "two recipients, distinct run ids"},
        )
        decision = resolve_dispatch(self.connection, DispatchMode.MULTI, self.fixture)
        self.assertIs(decision.mode, DispatchMode.MULTI)
        self.assertFalse(decision.downgraded)

    def test_multi_with_verified_probe_but_serial_transport_downgrades(self):
        record_capability(
            self.connection, MULTI_CALL, CapabilityStatus.VERIFIED, {"probe": "x"}
        )

        class SerialOnly:
            pass

        decision = resolve_dispatch(self.connection, DispatchMode.MULTI, SerialOnly())
        self.assertIs(decision.mode, DispatchMode.MONO)
        self.assertIn("no batch path", decision.downgrade_reason)

    def test_a_verdict_without_evidence_is_refused(self):
        with self.assertRaises(ValueError):
            record_capability(
                self.connection, MULTI_CALL, CapabilityStatus.VERIFIED, {}
            )

    def test_probe_needs_two_recipients_with_distinct_run_ids_all_terminal(self):
        status, _ = evaluate_probe(
            [
                {"run_id": "a", "terminal": True},
                {"run_id": "b", "terminal": True},
            ]
        )
        self.assertIs(status, CapabilityStatus.VERIFIED)

    def test_probe_with_one_recipient_proves_nothing_new(self):
        status, evidence = evaluate_probe([{"run_id": "a", "terminal": True}])
        self.assertIs(status, CapabilityStatus.UNAVAILABLE)
        self.assertIn("fewer than two", evidence["verdict_basis"])

    def test_probe_with_shared_run_ids_fails(self):
        status, _ = evaluate_probe(
            [
                {"run_id": "a", "terminal": True},
                {"run_id": "a", "terminal": True},
            ]
        )
        self.assertIs(status, CapabilityStatus.UNAVAILABLE)

    def test_probe_with_a_non_terminal_recipient_fails(self):
        status, _ = evaluate_probe(
            [
                {"run_id": "a", "terminal": True},
                {"run_id": "b", "terminal": False},
            ]
        )
        self.assertIs(status, CapabilityStatus.UNAVAILABLE)

    def test_fixture_batch_marks_the_shared_request(self):
        questionnaire = {
            "questions": [],
            "consent_text": "May I ask you a few questions for a study?",
            "on_refusal": {},
        }
        outcomes = self.fixture.call_batch(
            [{"sample_id": 1, "phone_e164": "+15550100011"},
             {"sample_id": 2, "phone_e164": "+15550100012"}],
            questionnaire,
            "batch-key-1",
        )
        self.assertEqual(len(outcomes), 2)
        self.assertEqual(outcomes[0].detail["batch_key"], "batch-key-1")
        self.assertEqual(outcomes[1].detail["batch_position"], 1)

    def test_migrate_adds_the_capability_table_to_an_old_database(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        old = sqlite3.connect(handle.name)
        old.row_factory = sqlite3.Row
        old.executescript(
            """
            CREATE TABLE study (id INTEGER PRIMARY KEY, study_key TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL, questionnaire_json TEXT NOT NULL,
                created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE');
            """
        )
        applied = migrate(old)
        self.assertIn("capability", applied)
        self.assertIn("review", applied)


class ReviewTestCase(unittest.TestCase):
    """Conflicts land in the queue; decisions sit beside the record."""

    def setUp(self):
        self.connection = memory_db()
        self.study_id = make_study(self.connection)
        self.attempt_id = make_attempt(self.connection, self.study_id)

    def test_green_checks_file_no_case(self):
        reasons = reasons_for_attempt("COMPLETED", {}, wording_matches=True, response_error=None)
        self.assertEqual(reasons, [])
        open_review(self.connection, self.attempt_id, reasons)
        self.connection.commit()
        self.assertEqual(open_case_count(self.connection, self.study_id), 0)

    def test_wording_mismatch_and_schema_error_each_file_a_reason(self):
        reasons = reasons_for_attempt(
            "COMPLETED",
            {"gates_missed": ["consent_question"], "consent_unclear": True},
            wording_matches=False,
            response_error="answer outside categories",
        )
        self.assertEqual(
            {r.value for r in reasons},
            {"wording_mismatch", "schema_error", "unclear_consent", "gate_missed"},
        )

    def test_refiling_merges_reasons_and_keeps_one_case(self):
        open_review(self.connection, self.attempt_id, [ReviewReason.WORDING_MISMATCH])
        self.connection.commit()
        open_review(self.connection, self.attempt_id, [ReviewReason.GATE_MISSED])
        self.connection.commit()
        cases = open_cases(self.connection, self.study_id)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["reasons"], ["gate_missed", "wording_mismatch"])

    def test_a_decision_requires_a_note(self):
        open_review(self.connection, self.attempt_id, [ReviewReason.WORDING_MISMATCH])
        self.connection.commit()
        case = open_cases(self.connection, self.study_id)[0]
        with self.assertRaises(ValueError):
            decide(self.connection, case["review_id"], ReviewDecision.GATE_PASSED, "   ")

    def test_a_decision_is_not_rewritten(self):
        open_review(self.connection, self.attempt_id, [ReviewReason.WORDING_MISMATCH])
        self.connection.commit()
        case = open_cases(self.connection, self.study_id)[0]
        decide(self.connection, case["review_id"], ReviewDecision.GATE_PASSED, "checked the transcript")
        with self.assertRaises(ValueError):
            decide(self.connection, case["review_id"], ReviewDecision.DROPOUT, "changed my mind")

    def test_dropout_marks_the_sample_but_never_touches_the_attempt(self):
        open_review(self.connection, self.attempt_id, [ReviewReason.SCHEMA_ERROR])
        self.connection.commit()
        case = open_cases(self.connection, self.study_id)[0]
        before = self.connection.execute(
            "SELECT call_status, detail_json FROM attempt WHERE id = ?", (self.attempt_id,)
        ).fetchone()

        decide(self.connection, case["review_id"], ReviewDecision.DROPOUT, "uninterpretable")

        after = self.connection.execute(
            "SELECT call_status, detail_json FROM attempt WHERE id = ?", (self.attempt_id,)
        ).fetchone()
        self.assertEqual(tuple(before), tuple(after))
        sample = self.connection.execute("SELECT exclusion_reason FROM sample").fetchone()
        self.assertEqual(sample["exclusion_reason"], "review:dropout")

    def test_gate_passed_leaves_the_sample_in_the_denominators(self):
        open_review(self.connection, self.attempt_id, [ReviewReason.GATE_MISSED])
        self.connection.commit()
        case = open_cases(self.connection, self.study_id)[0]
        decide(self.connection, case["review_id"], ReviewDecision.GATE_PASSED, "phrase was in the audio")
        sample = self.connection.execute("SELECT excluded_at FROM sample").fetchone()
        self.assertIsNone(sample["excluded_at"])

    def test_aggregation_is_guarded_while_cases_are_open(self):
        open_review(self.connection, self.attempt_id, [ReviewReason.WORDING_MISMATCH])
        self.connection.commit()
        with self.assertRaises(ValueError):
            guard_aggregation(self.connection, self.study_id)
        case = open_cases(self.connection, self.study_id)[0]
        decide(self.connection, case["review_id"], ReviewDecision.GATE_PASSED, "fine")
        guard_aggregation(self.connection, self.study_id)  # no raise


class PhraseTestCase(unittest.TestCase):
    """Recognition of predefined sentences — never free judgement."""

    CONSENT = "May I ask you three short questions for a study on public transport?"

    def questionnaire(self):
        return {
            "consent_text": self.CONSENT,
            "gate_phrases": [
                {"key": "abort_offer", "text": "You can stop this interview at any time."},
            ],
        }

    def test_the_consent_text_is_always_a_gate(self):
        phrases = phrases_from_questionnaire({"consent_text": self.CONSENT})
        # Since 2026-08-11 two further sentences are owed in every call and are
        # gates for the same reason: that a machine is calling, and that the
        # person may stop at any time. Neither is configurable, so neither can
        # be absent from this list.
        self.assertEqual(
            [p.key for p in phrases],
            ["consent_question", "ai_disclosure", "stop_right", "data_statement"],
        )

    def test_a_fragment_too_short_to_recognise_is_refused(self):
        with self.assertRaises(ValueError):
            GatePhrase(key="greeting", text="Hello!")

    def test_duplicate_keys_are_refused(self):
        with self.assertRaises(ValueError):
            phrases_from_questionnaire(
                {
                    "consent_text": self.CONSENT,
                    "gate_phrases": [{"key": "consent_question", "text": self.CONSENT}],
                }
            )

    def test_a_seen_phrase_is_ticked_off_case_and_spacing_tolerant(self):
        monitor = PhraseMonitor(phrases=phrases_from_questionnaire(self.questionnaire()))
        monitor.observe("Bot is speaking: may i ask you three short  questions for a study on public transport?")
        self.assertEqual(monitor.seen, ["consent_question"])
        self.assertIn("abort_offer", monitor.missed)

    def test_a_sentence_split_across_two_lines_is_still_found(self):
        monitor = PhraseMonitor(phrases=phrases_from_questionnaire(self.questionnaire()))
        monitor.observe("Bot is speaking: You can stop this interview")
        monitor.observe("at any time.")
        self.assertIn("abort_offer", monitor.seen)

    def test_a_miss_is_a_fact_about_the_feed_not_a_verdict(self):
        monitor = PhraseMonitor(phrases=phrases_from_questionnaire(self.questionnaire()))
        findings = monitor.findings()
        self.assertEqual(
            findings["gates_missed"],
            [
                "abort_offer",
                "ai_disclosure",
                "consent_question",
                "data_statement",
                "stop_right",
            ],
        )
        self.assertIn("literal recognition", findings["gate_check_basis"])

    def test_transcript_audit_uses_the_same_matcher(self):
        # A complete call now also says who is calling, what happens with the
        # answers, and that the person may stop; a transcript without those is a
        # call with a gap.
        questionnaire = self.questionnaire()
        transcript = (
            "[00:00] BOT: " + ai_disclosure_sentence(questionnaire) + "\n"
            "[00:01] BOT: " + stop_right_sentence("en") + "\n"
            "[00:02] BOT: " + privacy_sentence(questionnaire) + "\n"
            "[00:03] BOT: " + self.CONSENT + "\n"
            "[00:05] CALLEE: Yes, go ahead.\n"
            "[00:07] BOT: You can stop this interview at any time.\n"
        )
        findings = audit_transcript(
            transcript, phrases_from_questionnaire(questionnaire)
        )
        self.assertEqual(findings["gates_missed"], [])

    def test_similar_but_different_wording_is_not_recognised(self):
        monitor = PhraseMonitor(phrases=phrases_from_questionnaire(self.questionnaire()))
        monitor.observe("Bot is speaking: Would you mind answering a few questions for a survey?")
        self.assertIn("consent_question", monitor.missed)


if __name__ == "__main__":
    unittest.main()
