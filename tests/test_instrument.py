"""The instrument, the rules that act on it, and what leaves at the end.

These tests exist because round one collected settings that nothing read. Each
one below pins a value from a form definition to an observable consequence: a
sentence that is spoken, a record that is dialled twice, a column that appears in
the dataset. A setting whose test would only assert that it was saved does not
belong here — it belongs in the register of settings that admit they do nothing.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall import coding, effect, export, forms, instrument, pretest  # noqa: E402
from researchcall.calls import FixtureCallClient  # noqa: E402
from researchcall.database import connect, create_study, get_study, initialize  # noqa: E402
from researchcall.questionnaire import (  # noqa: E402
    UNLISTED_CODE,
    build_task,
    validate_questionnaire,
    validate_structured_result,
)
from researchcall.reporting import build_report  # noqa: E402
from researchcall.runner import ContactRules, run_day  # noqa: E402
from researchcall.sampling import draw_sample, import_frame_rows  # noqa: E402

OUTCOMES = ROOT / "src" / "researchcall" / "fixtures" / "outcomes.json"
TEST_TEMP_ROOT = ROOT / "out" / "tests"

ITEMS = [
    'i1 | H1 | dichotom | "Nutzen Sie den Bus?"',
    'i2 | H1 | skala | "Wie zufrieden sind Sie?" | scale=5:sehr unzufrieden..sehr zufrieden',
    'i3 | H1 | skala_umgepolt | "Der Bus stoert mich." | scale=5:gar nicht..sehr',
    'i4 | H2 | offen | "Was muesste sich aendern?" | free | probe=2 | rule=induktiv',
]

VALUES = {
    "question": "Wie wirkt der Takt auf die Verkehrsmittelwahl?",
    "items": ITEMS,
    "questionnaire.order": "randomised",
    "questionnaire.jump_rules": ["wenn i1 = no ueberspringe i2, i3"],
    "ethics.instruction": "Eine unabhaengige Studie zur Mobilitaet.",
    "ethics.privacy_text": "Antworten werden pseudonym gespeichert.",
    "ethics.number_origin": "einem oeffentlichen Verzeichnis",
    "ethics.greeting": ["Guten Tag."],
    "ethics.closing": ["Vielen Dank."],
    "ethics.time_estimate": True,
    "ethics.on_refusal.ask_reason": True,
    "ethics.on_refusal.offer_callback": True,
}


def build(**overrides):
    values = dict(VALUES)
    values.update(overrides)
    return instrument.build_questionnaire(values, "de")


class ItemGrammarTestCase(unittest.TestCase):
    def test_every_format_produces_the_categories_it_promises(self) -> None:
        items, problems = instrument.parse_items(ITEMS)
        self.assertEqual(problems, [])
        by_id = {item.id: item for item in items}
        self.assertEqual(by_id["i1"].categories, ("yes", "no"))
        self.assertEqual(by_id["i2"].categories, ("1", "2", "3", "4", "5"))
        self.assertTrue(by_id["i3"].scale["reversed"])
        self.assertEqual(by_id["i4"].categories, ())
        self.assertEqual(by_id["i4"].max_follow_ups, 2)
        self.assertEqual(by_id["i4"].analysis_rule, "induktiv")

    def test_a_scale_says_its_poles_out_loud(self) -> None:
        """A scale nobody hears the ends of is a request for interpretation."""
        questionnaire, _ = build()
        wording = {q["id"]: q["wording"] for q in questionnaire["questions"]}
        self.assertIn("Wie zufrieden sind Sie?", wording["i2"])
        self.assertIn("sehr unzufrieden", wording["i2"])
        self.assertIn("sehr zufrieden", wording["i2"])
        self.assertIn("1 bis 5", wording["i2"])

    def test_quantitative_items_are_bound_to_their_wording_and_open_ones_are_not(self) -> None:
        questionnaire, _ = build()
        binding = {q["id"]: q["verbatim"] for q in questionnaire["questions"]}
        self.assertTrue(binding["i1"])
        self.assertTrue(binding["i2"])
        self.assertFalse(binding["i4"])
        task = build_task(questionnaire)
        self.assertIn('i1 (say exactly): "Nutzen Sie den Bus?"', task)
        self.assertIn("i4 (open question, your own words):", task)
        self.assertIn("at most 2 follow-up question(s)", task)

    def test_a_standardised_item_may_not_carry_follow_up_probes(self) -> None:
        _, problems = instrument.parse_items(
            ['i1 | H1 | dichotom | "Nutzen Sie den Bus?" | probe=3']
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("sound the same for everyone", problems[0].message)

    def test_unreadable_lines_are_reported_instead_of_guessed(self) -> None:
        _, problems = instrument.parse_items(
            [
                "only-two | parts",
                'i1 | H1 | telepathy | "?"',
                'i2 | H1 | skala | "?" ',
                'i3 | H1 | dichotom | "a" | categories=one,two,three',
                'i4 | H1 | offen | "?" | categories=a,b',
            ]
        )
        messages = " ".join(problem.message for problem in problems)
        self.assertEqual(len(problems), 5)
        self.assertIn("at least id", messages)
        self.assertIn("unknown format", messages)
        self.assertIn("scale=<steps>", messages)
        self.assertIn("exactly two categories", messages)
        self.assertIn("not coded into fixed categories", messages)


class SkipRuleTestCase(unittest.TestCase):
    def test_a_skip_rule_becomes_a_filter_on_the_item_it_skips(self) -> None:
        questionnaire, problems = build()
        self.assertEqual(problems, [])
        by_id = {q["id"]: q for q in questionnaire["questions"]}
        self.assertEqual(by_id["i2"]["ask_if"], {"question": "i1", "equals": ["yes"]})
        self.assertNotIn("ask_if", by_id["i1"])
        validate_questionnaire(questionnaire)

    def test_a_rule_pointing_backwards_or_at_a_stranger_is_refused(self) -> None:
        _, problems = build(
            **{
                "questionnaire.jump_rules": [
                    "wenn i2 = 1 ueberspringe i1",
                    "wenn i9 = ja ueberspringe i2",
                    "wenn i1 = vielleicht ueberspringe i3",
                    "wenn i4 = irgendwas ueberspringe i2",
                ]
            }
        )
        messages = " ".join(problem.message for problem in problems)
        self.assertIn("cannot depend on it", messages)
        self.assertIn("unknown item: i9", messages)
        self.assertIn("no category", messages)
        self.assertIn("open item", messages)


class OrderTestCase(unittest.TestCase):
    def test_the_order_is_drawn_per_respondent_and_repeatable_for_the_same_one(self) -> None:
        questionnaire, _ = build()
        orders = {
            tuple(q["id"] for q in instrument.ordered_questions(questionnaire, n))
            for n in range(1, 40)
        }
        self.assertGreater(len(orders), 1, "a randomised order must actually vary")
        first = instrument.ordered_questions(questionnaire, 7)
        again = instrument.ordered_questions(questionnaire, 7)
        self.assertEqual([q["id"] for q in first], [q["id"] for q in again])

    def test_a_filtered_item_never_moves_in_front_of_the_item_it_depends_on(self) -> None:
        questionnaire, _ = build()
        for sample_id in range(1, 60):
            ordered = [q["id"] for q in instrument.ordered_questions(questionnaire, sample_id)]
            self.assertLess(ordered.index("i1"), ordered.index("i2"), ordered)
            self.assertLess(ordered.index("i1"), ordered.index("i3"), ordered)

    def test_a_fixed_order_stays_as_written(self) -> None:
        questionnaire, _ = build(**{"questionnaire.order": "fixed"})
        ordered = [q["id"] for q in instrument.ordered_questions(questionnaire, 3)]
        self.assertEqual(ordered, ["i1", "i2", "i3", "i4"])


class ConversationFrameTestCase(unittest.TestCase):
    def test_the_frame_is_spoken_in_the_order_station_three_prescribes(self) -> None:
        questionnaire, _ = build()
        kinds = [block["kind"] for block in questionnaire["opening"]]
        self.assertEqual(
            kinds, ["greeting", "instruction", "number_origin", "time_estimate", "privacy"]
        )
        task = build_task(questionnaire)
        self.assertIn('instruction (say exactly): "Eine unabhaengige Studie', task)
        self.assertIn("greeting (your own words): Guten Tag.", task)
        self.assertIn("CLOSING (your own words): Vielen Dank.", task)

    def test_the_announced_duration_is_computed_from_the_instrument(self) -> None:
        """A duration typed by hand drifts away from the questionnaire it promises."""
        short, _ = build(items=[ITEMS[0]])
        long, _ = build(items=ITEMS * 4)
        self.assertLess(short["estimated_minutes"], long["estimated_minutes"])
        spoken = [
            block["text"]
            for block in short["opening"]
            if block["kind"] == "time_estimate"
        ]
        self.assertEqual(spoken, [f"Die Befragung dauert etwa {short['estimated_minutes']} Minuten."])

    def test_a_switched_off_time_estimate_is_the_only_thing_that_removes_it(self) -> None:
        questionnaire, _ = build(**{"ethics.time_estimate": False})
        self.assertNotIn(
            "time_estimate", [block["kind"] for block in questionnaire["opening"]]
        )

    def test_the_right_to_stop_is_said_and_not_merely_stored(self) -> None:
        """It is a locked setting, so it cannot be switched off — but it must be heard."""
        questionnaire, _ = build()
        self.assertIn("jederzeit beenden", questionnaire["consent_text"])
        self.assertIn(
            f'CONSENT (say exactly): "{questionnaire["consent_text"]}"',
            build_task(questionnaire),
        )

    def test_refusals_are_asked_about_and_the_schema_can_carry_the_answer(self) -> None:
        questionnaire, _ = build()
        task = build_task(questionnaire)
        self.assertIn("what made them decline", task)
        self.assertIn("callback_wanted", task)
        client = FixtureCallClient.from_file(OUTCOMES)
        outcome = client.call({"sample_id": 3}, questionnaire, "unused")
        self.assertEqual(outcome.structured_result["consent"], "declined")
        self.assertTrue(outcome.structured_result["refusal_reason"])
        validate_structured_result(questionnaire, outcome.structured_result)

    def test_both_study_languages_speak_their_own_sentences(self) -> None:
        """Neither language is the afterthought of the other.

        Every sentence ResearchCall itself contributes to the call — scale
        poles, right to stop, consent question, duration, number origin — comes
        from the study language, and none of it leaks the other language. The
        researcher's own texts are their own business; these are ours.
        """
        german = instrument.build_questionnaire(dict(VALUES), "de")[0]
        english = instrument.build_questionnaire(dict(VALUES), "en")[0]

        spoken_de = " ".join(
            [german["consent_text"], *(q["wording"] for q in german["questions"])]
            + [str(block.get("text", "")) for block in german["opening"]]
        )
        spoken_en = " ".join(
            [english["consent_text"], *(q["wording"] for q in english["questions"])]
            + [str(block.get("text", "")) for block in english["opening"]]
        )

        self.assertIn("jederzeit beenden", spoken_de)
        self.assertIn("Möchten Sie an der Befragung teilnehmen?", spoken_de)
        self.assertIn("Skala von 1 bis 5", spoken_de)
        self.assertIn("dauert etwa", spoken_de)

        self.assertIn("end this call at any time", spoken_en)
        self.assertIn("Would you like to take part in the survey?", spoken_en)
        self.assertIn("scale from 1 to 5", spoken_en)
        self.assertIn("takes about", spoken_en)

        for german_fragment in ("jederzeit beenden", "Befragung dauert", "Skala von"):
            self.assertNotIn(german_fragment, spoken_en)
        for english_fragment in ("end this call", "survey takes", "scale from"):
            self.assertNotIn(english_fragment, spoken_de)

    def test_the_task_carries_the_language_directive_in_that_same_language(self) -> None:
        """The directive is addressed to the agent, so it speaks its language too."""
        german, _ = instrument.build_questionnaire(dict(VALUES), "de")
        english, _ = instrument.build_questionnaire(dict(VALUES), "en")

        german_task = build_task(german)
        english_task = build_task(english)

        self.assertIn("GESPRÄCHSSPRACHE", german_task)
        self.assertIn("auf Deutsch", german_task)
        self.assertNotIn("CONVERSATION LANGUAGE", german_task)

        self.assertIn("CONVERSATION LANGUAGE", english_task)
        self.assertIn("in English", english_task)
        self.assertNotIn("GESPRÄCHSSPRACHE", english_task)

    def test_an_unanswered_entry_may_be_absent_instead_of_null(self) -> None:
        """Absence is what the API-compatible schema leaves behind (issue #120).

        Nullable unions are rejected at create time, so unanswered entries are
        omitted rather than sent as null. Validation has to read both, because
        fixtures and stored records keep the explicit null form.
        """
        questionnaire, _ = build()
        client = FixtureCallClient.from_file(OUTCOMES)
        result = client.call({"sample_id": 1}, questionnaire, "unused").structured_result
        last = questionnaire["questions"][-1]["id"]
        for field in ("answers", "raw_answers", "spoken_wording"):
            result[field].pop(last, None)

        validate_structured_result(questionnaire, result)

    def test_an_open_item_stays_uncategorized_however_it_is_sent(self) -> None:
        questionnaire, _ = build()
        client = FixtureCallClient.from_file(OUTCOMES)
        result = client.call({"sample_id": 1}, questionnaire, "unused").structured_result
        open_ids = [
            question["id"]
            for question in questionnaire["questions"]
            if instrument.is_open(question)
        ]
        self.assertTrue(open_ids, "this frame needs an open item for the check")
        open_id = open_ids[0]

        result["answers"].pop(open_id)          # absent: the new wire form
        validate_structured_result(questionnaire, result)
        result["answers"][open_id] = None       # null: the stored form
        validate_structured_result(questionnaire, result)
        result["answers"][open_id] = "categorized anyway"
        with self.assertRaisesRegex(ValueError, "must not be categorized"):
            validate_structured_result(questionnaire, result)

    def test_the_consent_wording_may_only_be_missing_when_it_was_never_asked(self) -> None:
        """Absence is allowed where null was allowed — not one case further."""
        questionnaire, _ = build()
        client = FixtureCallClient.from_file(OUTCOMES)
        result = client.call({"sample_id": 1}, questionnaire, "unused").structured_result
        self.assertEqual(result["consent"], "granted")
        del result["spoken_consent_wording"]
        with self.assertRaisesRegex(ValueError, "spoken_consent_wording"):
            validate_structured_result(questionnaire, result)

        result["consent"] = "not_obtained"
        validate_structured_result(questionnaire, result)

    def test_a_frame_without_the_refusal_question_carries_no_field_for_it(self) -> None:
        questionnaire, _ = build(
            **{"ethics.on_refusal.ask_reason": False, "ethics.on_refusal.offer_callback": False}
        )
        client = FixtureCallClient.from_file(OUTCOMES)
        outcome = client.call({"sample_id": 3}, questionnaire, "unused")
        self.assertNotIn("refusal_reason", outcome.structured_result)
        validate_structured_result(questionnaire, outcome.structured_result)


class CodingRuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.questionnaire, _ = build()

    def result_with(self, answer):
        return {
            "consent": "granted",
            "withdrawal_requested": False,
            "asked_verbatim": True,
            "spoken_consent_wording": self.questionnaire["consent_text"],
            "spoken_wording": {q["id"]: q["wording"] for q in self.questionnaire["questions"]},
            "answers": {"i1": answer, "i2": "3", "i3": "2", "i4": None},
            "raw_answers": {
                "i1": "Weiss nicht so recht.",
                "i2": "3",
                "i3": "2",
                "i4": "Mehr Abfahrten.",
            },
        }

    def test_an_answer_outside_the_categories_follows_the_rule_fixed_in_advance(self) -> None:
        for rule, expected in (("as_other", UNLISTED_CODE), ("discard", None), ("let_model_map", None)):
            with self.subTest(rule=rule):
                questionnaire = dict(self.questionnaire, coding={"unlisted_answers": rule})
                adjusted, notes = coding.apply_unlisted_policy(
                    questionnaire, self.result_with("weiss nicht")
                )
                self.assertEqual(adjusted["answers"]["i1"], expected)
                self.assertEqual(len(notes), 1)
                self.assertEqual(notes[0]["rule"], rule)
                self.assertEqual(notes[0]["raw_kept"], "yes")
                validate_structured_result(questionnaire, adjusted)

    def test_a_fitting_answer_is_left_alone(self) -> None:
        adjusted, notes = coding.apply_unlisted_policy(self.questionnaire, self.result_with("yes"))
        self.assertEqual(notes, [])
        self.assertEqual(adjusted["answers"]["i1"], "yes")

    def test_a_reversed_item_is_turned_back_around(self) -> None:
        item = [q for q in self.questionnaire["questions"] if q["id"] == "i3"][0]
        self.assertEqual(coding.reverse_scale_value(item, "1"), "5")
        self.assertEqual(coding.reverse_scale_value(item, "4"), "2")
        self.assertIsNone(coding.reverse_scale_value(item, None))
        plain = [q for q in self.questionnaire["questions"] if q["id"] == "i2"][0]
        self.assertEqual(coding.reverse_scale_value(plain, "1"), "1")


class FieldworkTestCase(unittest.TestCase):
    """The contact rules, measured on a running database rather than asserted."""

    def setUp(self) -> None:
        TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tempdir = tempfile.TemporaryDirectory(dir=TEST_TEMP_ROOT)
        self.addCleanup(self.tempdir.cleanup)
        path = Path(self.tempdir.name) / "state.db"
        initialize(path)
        self.questionnaire, problems = build()
        self.assertEqual(problems, [])
        self.connection = connect(path)
        self.addCleanup(self.connection.close)
        self.study_id = create_study(self.connection, "s", self.questionnaire)
        self.connection.commit()
        import_frame_rows(
            self.connection,
            self.study_id,
            [(f"p-{n:03d}", f"+155502{n:05d}") for n in range(1, 41)],
        )
        self.client = FixtureCallClient.from_file(OUTCOMES)

    def work(self, rules: ContactRules, rounds: int = 3) -> None:
        study = get_study(self.connection, "s")
        for _ in range(rounds):
            for window in rules.windows:
                run_day(self.connection, study, window, 50, self.client, rules)

    def attempts_per_sample(self) -> dict[int, int]:
        rows = self.connection.execute(
            "SELECT sample_id, COUNT(*) AS n FROM attempt GROUP BY sample_id"
        ).fetchall()
        return {int(row["sample_id"]): int(row["n"]) for row in rows}

    def test_the_default_dials_every_person_exactly_once(self) -> None:
        draw_sample(self.connection, self.study_id, 12, 5)
        self.work(ContactRules(windows=("morning", "afternoon", "evening")))
        self.assertEqual(set(self.attempts_per_sample().values()), {1})

    def test_an_extra_attempt_is_used_only_after_nobody_answered(self) -> None:
        draw_sample(self.connection, self.study_id, 12, 5)
        self.work(
            ContactRules(
                attempts_per_person=1, windows=("morning", "afternoon", "evening")
            )
        )
        counts = self.attempts_per_sample()
        self.assertGreater(max(counts.values()), 1, "no record was ever repeated")
        self.assertLessEqual(max(counts.values()), 2, "the configured bound was exceeded")
        repeated = self.connection.execute(
            """
            SELECT a.call_status FROM attempt a
            WHERE a.attempt_no = 1
              AND EXISTS (SELECT 1 FROM attempt b
                          WHERE b.sample_id = a.sample_id AND b.attempt_no = 2)
            """
        ).fetchall()
        self.assertTrue(repeated)
        for row in repeated:
            self.assertIn(row["call_status"], {"NO_ANSWER", "BUSY", "VOICEMAIL", "DECLINED"})

    def test_a_refusal_alone_is_never_dialled_again(self) -> None:
        """Only an explicit invitation reopens a record that said no."""
        draw_sample(self.connection, self.study_id, 12, 5)
        self.work(
            ContactRules(
                attempts_per_person=2,
                callback_after_refusal_max=0,
                windows=("morning", "afternoon", "evening"),
            )
        )
        rows = self.connection.execute(
            """
            SELECT a.sample_id FROM attempt a
            WHERE a.call_status = 'DECLINED'
              AND EXISTS (SELECT 1 FROM attempt b
                          WHERE b.sample_id = a.sample_id AND b.attempt_no > a.attempt_no)
            """
        ).fetchall()
        self.assertEqual(rows, [])

    def test_a_repeat_lands_in_a_different_time_of_day(self) -> None:
        draw_sample(self.connection, self.study_id, 12, 5)
        rules = ContactRules(
            attempts_per_person=1, windows=("morning", "afternoon", "evening")
        )
        self.work(rules)
        moved = self.connection.execute(
            """
            SELECT a.id FROM attempt a JOIN sample s ON s.id = a.sample_id
            WHERE a.attempt_no > 1 AND a.time_window != s.assigned_window
            """
        ).fetchall()
        self.assertTrue(moved, "a repeat stayed in the window that had already failed")

    def test_the_report_states_the_repeats_instead_of_folding_them_in(self) -> None:
        draw_sample(self.connection, self.study_id, 12, 5)
        self.work(
            ContactRules(
                attempts_per_person=1, windows=("morning", "afternoon", "evening")
            )
        )
        report = build_report(self.connection, get_study(self.connection, "s"))
        self.assertIn("## Repeated contact", report)
        self.assertIn("Records dialled more than once:", report)
        self.assertNotIn("Records dialled more than once: 0", report)
        self.assertIn("Item order was drawn separately for every respondent", report)

    def test_the_dataset_carries_one_row_per_person_and_a_codebook_beside_it(self) -> None:
        draw_sample(self.connection, self.study_id, 12, 5)
        self.work(ContactRules(windows=("morning", "afternoon", "evening")))
        study = get_study(self.connection, "s")
        rows = export.dataset_csv(self.connection, study).splitlines()
        header = rows[0].split(",")
        self.assertIn("i1", header)
        self.assertIn("i3_recoded", header)
        self.assertIn("i4_text", header)
        self.assertNotIn("i4", header, "an open item has no coded column")
        included = self.connection.execute(
            "SELECT COUNT(*) AS n FROM sample WHERE excluded_at IS NULL"
        ).fetchone()["n"]
        self.assertEqual(len(rows) - 1, included)
        book = export.codebook(self.connection, study)
        self.assertIn("`i3_recoded` the turned-around value", book)
        self.assertIn("Asked only if `i1`", book)

    def test_free_text_follows_the_rule_and_can_be_kept_out_entirely(self) -> None:
        for rule, expected in (("in_dataset", True), ("separate", False), ("discard", False)):
            with self.subTest(rule=rule):
                questionnaire, _ = build()
                questionnaire["coding"]["free_comments"] = rule
                path = Path(self.tempdir.name) / f"{rule}.db"
                initialize(path)
                connection = connect(path)
                try:
                    study_id = create_study(connection, "s", questionnaire)
                    connection.commit()
                    import_frame_rows(
                        connection,
                        study_id,
                        [(f"p-{n:03d}", f"+155503{n:05d}") for n in range(1, 21)],
                    )
                    draw_sample(connection, study_id, 6, 3)
                    study = get_study(connection, "s")
                    for window in ("morning", "afternoon", "evening"):
                        run_day(connection, study, window, 10, self.client)
                    header = export.dataset_csv(connection, study).splitlines()[0]
                    self.assertEqual("i4_text" in header, expected)
                    separate = export.free_text_csv(connection, study)
                    self.assertIn("record,item,text", separate)
                finally:
                    connection.close()

    def test_no_export_ever_carries_a_phone_number(self) -> None:
        draw_sample(self.connection, self.study_id, 12, 5)
        self.work(ContactRules(windows=("morning", "afternoon", "evening")))
        study = get_study(self.connection, "s")
        for text in (
            export.dataset_csv(self.connection, study),
            export.free_text_csv(self.connection, study),
            export.codebook(self.connection, study),
            build_report(self.connection, study),
        ):
            self.assertNotIn("+15550", text)


class InstrumentCheckTestCase(unittest.TestCase):
    def test_the_check_measures_fidelity_and_says_what_it_cannot_measure(self) -> None:
        questionnaire, _ = build()
        result = pretest.check(
            questionnaire, 20, OUTCOMES, "Wuerden Sie sagen, dass Sie, den Bus, oft nutzen?"
        )
        self.assertEqual(result["calls"], 20)
        self.assertGreater(result["interviews"], 0)
        self.assertEqual(result["invalid_results"], 0)
        self.assertTrue(result["marker"]["used"])
        self.assertEqual(result["marker"]["asked"], result["interviews"])
        self.assertGreater(result["order"]["distinct_orders"], 1)
        self.assertEqual(
            set(result["not_measurable"]), {"unplanned_follow_ups", "order_kept"}
        )
        self.assertIn("not the CALL-E agent", result["honest_note"])

    def test_a_check_that_could_only_ever_pass_would_be_worthless(self) -> None:
        """The fixture deviates on purpose, so the score must not be perfect."""
        questionnaire, _ = build()
        result = pretest.check(questionnaire, 20, OUTCOMES)
        measured = result["measured"]["spoken_wording"]
        self.assertLess(measured["value"], measured["of"])
        self.assertGreater(measured["value"], 0)

    def test_the_check_writes_nothing_into_the_study(self) -> None:
        questionnaire, _ = build()
        summary = "\n".join(pretest.summarize(pretest.check(questionnaire, 5, OUTCOMES)))
        self.assertIn("Instrument check (dry run)", summary)
        self.assertIn("Not measurable in a dry run", summary)


class EffectRegisterTestCase(unittest.TestCase):
    """The register is the promise; these tests are what keeps it honest."""

    def setUp(self) -> None:
        self.fields = forms.load_fields()

    def test_every_form_definition_is_classified(self) -> None:
        self.assertEqual(effect.unclassified(self.fields), [])

    def test_the_register_names_no_setting_that_no_longer_exists(self) -> None:
        self.assertEqual(effect.stale(self.fields), [])

    def test_transcript_retention_is_no_longer_a_switch_without_a_wire(self) -> None:
        """User decision of 2026-08-11: transcripts are kept, so the switch works.

        While the register called this field `declared`, the interface told the
        researcher that nothing reads it. Keeping that sentence after wiring the
        switch would be the exact failure this register exists to prevent.
        """
        field = next(
            item for item in self.fields if item.path == "fieldwork.keep_transcript"
        )
        self.assertTrue(effect.is_effective(field))

    def test_a_setting_that_cannot_be_switched_off_must_actually_do_something(self) -> None:
        """A locked setting nothing reads would be a lie about the frame."""
        for field in self.fields:
            if field.locked:
                with self.subTest(field=field.path):
                    self.assertTrue(effect.is_effective(field))

    def test_every_class_carries_a_sentence_a_person_can_read(self) -> None:
        for field in self.fields:
            with self.subTest(field=field.path):
                reason = effect.reason_of(field)
                self.assertTrue(reason.endswith("."), reason)
                self.assertGreater(len(reason), 20, reason)


if __name__ == "__main__":
    unittest.main()
