"""Regressions for the data phase and the statistics.

The statistics tests deliberately avoid invented reference numbers: they check
mathematical properties (symmetry, known bounds, table intervals) instead of
asserting decimals nobody here computed independently.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall.database import connect, initialize, utc_now
from researchcall.dataphase import (
    anonymise_deliberately,
    call_list,
    change_history,
    correct_answer,
    dialed_register,
    is_sealed,
    mark_do_not_call,
    reconciliation,
    record_dialed,
    seal_dataset,
    suggest_decision,
)
from researchcall.review import ReviewDecision, ReviewReason, decide, decide_all_by_rule, flag_manually, open_cases, open_review
from researchcall.stats import describe, t_survival, welch_t_test


def fresh_db():
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    initialize(handle.name)
    return connect(handle.name)


def make_study(connection):
    connection.execute(
        "INSERT INTO study(study_key, title, questionnaire_json, created_at) "
        "VALUES ('s1', 'Test', '{}', ?)",
        (utc_now(),),
    )
    connection.commit()
    return int(connection.execute("SELECT id FROM study").fetchone()["id"])


def make_person(connection, study_id, ref, phone, with_attempt=True, status="COMPLETED"):
    connection.execute(
        "INSERT INTO frame(study_id, external_ref, phone_e164) VALUES (?, ?, ?)",
        (study_id, ref, phone),
    )
    frame_id = int(connection.execute("SELECT MAX(id) AS m FROM frame").fetchone()["m"])
    connection.execute(
        "INSERT INTO sample(study_id, frame_id, time_window, drawn_at) VALUES (?, ?, 'morning', ?)",
        (study_id, frame_id, utc_now()),
    )
    sample_id = int(connection.execute("SELECT MAX(id) AS m FROM sample").fetchone()["m"])
    attempt_id = None
    if with_attempt:
        connection.execute(
            "INSERT INTO attempt(sample_id, attempt_no, started_at, call_status, idempotency_key) "
            "VALUES (?, 1, ?, ?, ?)",
            (sample_id, utc_now(), status, f"k-{ref}"),
        )
        attempt_id = int(
            connection.execute("SELECT MAX(id) AS m FROM attempt").fetchone()["m"]
        )
    connection.commit()
    return frame_id, sample_id, attempt_id


class DialedRegisterTestCase(unittest.TestCase):
    def setUp(self):
        self.connection = fresh_db()
        self.study_id = make_study(self.connection)

    def test_the_register_keeps_one_row_per_number_across_attempts(self):
        record_dialed(self.connection, self.study_id, "+15550100011", "NO_ANSWER")
        record_dialed(self.connection, self.study_id, "+15550100011", "COMPLETED")
        self.connection.commit()
        register = dialed_register(self.connection, self.study_id)
        self.assertEqual(len(register), 1)
        self.assertEqual(register[0]["last_status"], "COMPLETED")

    def test_anonymisation_keeps_the_number_in_the_register(self):
        """The user's core requirement: the dialled list survives, the edge falls."""
        make_person(self.connection, self.study_id, "p1", "+15550100011")
        record_dialed(self.connection, self.study_id, "+15550100011", "COMPLETED")
        self.connection.commit()

        anonymise_deliberately(
            self.connection, self.study_id, "p1", "study closed, link no longer needed"
        )

        frame = self.connection.execute("SELECT phone_e164 FROM frame").fetchone()
        self.assertIsNone(frame["phone_e164"])           # edge cut
        register = dialed_register(self.connection, self.study_id)
        self.assertEqual(register[0]["phone_e164"], "+15550100011")  # number kept

    def test_anonymisation_without_grounds_is_refused(self):
        make_person(self.connection, self.study_id, "p1", "+15550100011")
        with self.assertRaises(ValueError) as caught:
            anonymise_deliberately(self.connection, self.study_id, "p1", "  ")
        self.assertIn("follow-up", str(caught.exception).lower())

    def test_anonymisation_lands_in_the_change_log(self):
        make_person(self.connection, self.study_id, "p1", "+15550100011")
        anonymise_deliberately(self.connection, self.study_id, "p1", "requested by IRB")
        history = change_history(self.connection, self.study_id)
        self.assertEqual(history[0]["field"], "phone_link")
        self.assertEqual(history[0]["reason"], "requested by IRB")

    def test_do_not_call_is_marked_and_counted(self):
        mark_do_not_call(self.connection, self.study_id, "+15550100011")
        self.connection.commit()
        register = dialed_register(self.connection, self.study_id)
        self.assertEqual(register[0]["do_not_call"], 1)
        counts = reconciliation(self.connection, self.study_id)
        self.assertEqual(counts["do_not_call"], 1)

    def test_reconciliation_compares_frame_and_register(self):
        make_person(self.connection, self.study_id, "p1", "+15550100011", with_attempt=False)
        make_person(self.connection, self.study_id, "p2", "+15550100012", with_attempt=False)
        record_dialed(self.connection, self.study_id, "+15550100011", "COMPLETED")
        self.connection.commit()
        counts = reconciliation(self.connection, self.study_id)
        self.assertEqual(counts["frame_total"], 2)
        self.assertEqual(counts["dialed"], 1)
        self.assertEqual(counts["not_yet_dialed"], 1)
        self.assertEqual(counts["successful"], 1)


class SealAndCorrectionTestCase(unittest.TestCase):
    def setUp(self):
        self.connection = fresh_db()
        self.study_id = make_study(self.connection)

    def test_sealing_needs_grounds_and_happens_once(self):
        with self.assertRaises(ValueError):
            seal_dataset(self.connection, self.study_id, " ")
        seal_dataset(self.connection, self.study_id, "fieldwork finished 2026-08-04")
        self.assertTrue(is_sealed(self.connection, self.study_id))
        with self.assertRaises(ValueError):
            seal_dataset(self.connection, self.study_id, "again")

    def _with_response(self):
        _, sample_id, _ = make_person(self.connection, self.study_id, "p1", "+15550100011")
        structured = {
            "answers": {"q1": "weekly"},
            "raw_answers": {"q1": "About once a week."},
        }
        self.connection.execute(
            "INSERT INTO response(sample_id, structured_json, consent, "
            "asked_verbatim_reported, wording_matches, received_at) VALUES (?, ?, 'granted', 1, 1, ?)",
            (sample_id, json.dumps(structured), utc_now()),
        )
        self.connection.commit()
        return sample_id

    def test_a_correction_changes_the_code_and_never_the_raw_words(self):
        sample_id = self._with_response()
        correct_answer(
            self.connection, self.study_id, sample_id, "q1", "monthly", "miscoded at entry"
        )
        row = self.connection.execute(
            "SELECT structured_json FROM response WHERE sample_id = ?", (sample_id,)
        ).fetchone()
        structured = json.loads(str(row["structured_json"]))
        self.assertEqual(structured["answers"]["q1"], "monthly")
        self.assertEqual(structured["raw_answers"]["q1"], "About once a week.")
        self.assertEqual(structured["corrections"][0]["from"], "weekly")

    def test_a_correction_without_grounds_or_without_change_is_refused(self):
        sample_id = self._with_response()
        with self.assertRaises(ValueError):
            correct_answer(self.connection, self.study_id, sample_id, "q1", "monthly", " ")
        with self.assertRaises(ValueError):
            correct_answer(
                self.connection, self.study_id, sample_id, "q1", "weekly", "same value"
            )

    def test_every_correction_lands_in_the_change_log_old_beside_new(self):
        sample_id = self._with_response()
        correct_answer(
            self.connection, self.study_id, sample_id, "q1", "monthly", "miscoded"
        )
        entry = change_history(self.connection, self.study_id)[0]
        self.assertEqual(json.loads(entry["old_value"]), "weekly")
        self.assertEqual(json.loads(entry["new_value"]), "monthly")
        self.assertEqual(entry["reason"], "miscoded")


class CallListTestCase(unittest.TestCase):
    def setUp(self):
        self.connection = fresh_db()
        self.study_id = make_study(self.connection)

    def test_statuses_are_derived_and_conflict_wins(self):
        make_person(self.connection, self.study_id, "p1", "+15550100011", status="COMPLETED")
        make_person(self.connection, self.study_id, "p2", "+15550100012", status="NO_ANSWER")
        make_person(self.connection, self.study_id, "p3", "+15550100013", with_attempt=False)
        _, _, attempt4 = make_person(
            self.connection, self.study_id, "p4", "+15550100014", status="COMPLETED"
        )
        open_review(self.connection, attempt4, [ReviewReason.WORDING_MISMATCH])
        self.connection.commit()

        by_ref = {e["external_ref"]: e["derived_status"] for e in call_list(self.connection, self.study_id)}
        self.assertEqual(by_ref["p1"], "successful")
        self.assertEqual(by_ref["p2"], "unsuccessful")
        self.assertEqual(by_ref["p3"], "not_attempted")
        self.assertEqual(by_ref["p4"], "conflict")  # paperwork state outranks outcome

    def test_the_filter_narrows_and_an_unknown_filter_is_refused(self):
        make_person(self.connection, self.study_id, "p1", "+15550100011", status="COMPLETED")
        make_person(self.connection, self.study_id, "p2", "+15550100012", with_attempt=False)
        successful = call_list(self.connection, self.study_id, "successful")
        self.assertEqual([e["external_ref"] for e in successful], ["p1"])
        with self.assertRaises(ValueError):
            call_list(self.connection, self.study_id, "greatest_hits")

    def test_a_manual_flag_turns_a_green_call_into_a_conflict(self):
        _, _, attempt_id = make_person(
            self.connection, self.study_id, "p1", "+15550100011", status="COMPLETED"
        )
        flag_manually(self.connection, attempt_id, "the transcript reads coached")
        entries = call_list(self.connection, self.study_id, "conflict")
        self.assertEqual(len(entries), 1)
        self.assertIn("manual_flag", entries[0]["review_reason"])
        self.assertIn("coached", entries[0]["review_note"])

    def test_rule_decisions_are_marked_as_rule_not_as_looked_at(self):
        _, _, attempt_id = make_person(
            self.connection, self.study_id, "p1", "+15550100011", status="COMPLETED"
        )
        open_review(self.connection, attempt_id, [ReviewReason.SCHEMA_ERROR])
        self.connection.commit()
        closed = decide_all_by_rule(
            self.connection, self.study_id, ReviewDecision.DROPOUT, "default policy"
        )
        self.assertEqual(closed, 1)
        entry = call_list(self.connection, self.study_id)[0]
        self.assertEqual(entry["review_decided_by"], "rule")

    def test_there_is_no_rule_that_passes_gates(self):
        with self.assertRaises(ValueError):
            decide_all_by_rule(
                self.connection, self.study_id, ReviewDecision.GATE_PASSED, "wave through"
            )


class SuggestionTestCase(unittest.TestCase):
    def test_wording_only_suggests_gate_passed(self):
        decision, _ = suggest_decision(["wording_mismatch"])
        self.assertEqual(decision, "gate_passed")

    def test_structural_problems_suggest_dropout(self):
        for reasons in (["schema_error"], ["unclear_consent"], ["gate_missed"],
                        ["wording_mismatch", "schema_error"]):
            decision, _ = suggest_decision(reasons)
            self.assertEqual(decision, "dropout", reasons)


class StatsTestCase(unittest.TestCase):
    """Properties and table intervals — no invented reference decimals."""

    def test_describe_matches_hand_computation(self):
        d = describe([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        self.assertEqual(d.n, 8)
        self.assertAlmostEqual(d.mean, 5.0)
        self.assertAlmostEqual(d.sd, 2.13809, places=4)  # sqrt(32/7)
        self.assertAlmostEqual(d.median, 4.5)

    def test_t_survival_at_zero_is_one_half(self):
        for df in (1, 5, 30, 200):
            self.assertAlmostEqual(t_survival(0.0, df), 0.5, places=10)

    def test_t_survival_matches_the_printed_table(self):
        # Any statistics book: t(df=10, upper 5%) = 1.812, upper 2.5% = 2.228.
        self.assertAlmostEqual(t_survival(1.812, 10), 0.05, places=3)
        self.assertAlmostEqual(t_survival(2.228, 10), 0.025, places=3)

    def test_identical_groups_give_t_zero_p_one(self):
        result = welch_t_test([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        self.assertAlmostEqual(result.t, 0.0)
        self.assertAlmostEqual(result.p_two_sided, 1.0)

    def test_the_test_is_symmetric_in_its_groups(self):
        a, b = [1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 9.0]
        forward = welch_t_test(a, b)
        backward = welch_t_test(b, a)
        self.assertAlmostEqual(forward.p_two_sided, backward.p_two_sided)
        self.assertAlmostEqual(forward.t, -backward.t)

    def test_clearly_separated_groups_get_a_tiny_p(self):
        result = welch_t_test([1.0, 1.1, 0.9, 1.05], [9.0, 9.1, 8.9, 9.05])
        self.assertLess(result.p_two_sided, 1e-6)

    def test_equal_variance_groups_reach_the_classic_df(self):
        # With equal n and equal variances Welch's df equals n1+n2-2.
        result = welch_t_test([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
        self.assertAlmostEqual(result.df, 4.0, places=6)

    def test_degenerate_input_is_refused(self):
        with self.assertRaises(ValueError):
            welch_t_test([1.0], [1.0, 2.0])
        with self.assertRaises(ValueError):
            welch_t_test([3.0, 3.0], [5.0, 5.0])  # both constant


if __name__ == "__main__":
    unittest.main()
