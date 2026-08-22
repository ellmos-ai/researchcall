"""The coverage map, as tests: every researcher option against the prompt it makes.

`PROMPT-MAP.md` is the claim; this file is the measurement. Three kinds of check:

* **Floor** — the sentences every call owes, in their fixed order, in both languages.
* **Flips** — change one option, and the task changes in the documented way. An
  option that changes nothing when flipped is either app-side (fine, and the map
  says so) or a gap (not fine, and the map says that too).
* **Goldens** — four whole task texts kept on disk. They are the only check that
  notices an *unintended* change: a diff shows what moved, not merely that
  something did. Regenerate with ``RESEARCHCALL_WRITE_GOLDENS=1``.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from researchcall import instrument  # noqa: E402
from researchcall.questionnaire import build_task, result_schema  # noqa: E402
from test_instrument import ITEMS, VALUES  # noqa: E402

GOLDENS = Path(__file__).parent / "goldens"

#: The sentences a call owes, in the order they must be spoken. Their absence is
#: the failure class the first live calls exposed (FINDINGS sections 13 and 14).
FLOOR_ORDER_DE = (
    "künstliche Intelligenz",
    "umfasst bis zu",
    "Zum Datenschutz:",
    "jederzeit ohne Angabe von Gründen beenden",
    "sagen Sie es mir",
    "CONSENT (say exactly)",
)
FLOOR_ORDER_EN = (
    "artificial intelligence",
    "up to",
    "About your data:",
    "end this call at any time",
    "just say so",
    "CONSENT (say exactly)",
)


def study(language: str = "de", **overrides: object) -> dict:
    """A questionnaire built the way the workbench builds one."""
    values = dict(VALUES)
    values.update(
        {
            "ethics.commissioner": "Example Institute",
            "ethics.privacy_short": (
                "Antworten werden pseudonym gespeichert und nach zwei Jahren gelöscht."
                if language == "de"
                else "Answers are stored pseudonymously and deleted after two years."
            ),
            "ethics.withdrawal_contact": "withdraw@example.invalid",
        }
    )
    values.update(overrides)  # type: ignore[arg-type]
    questionnaire, _ = instrument.build_questionnaire(values, language)
    return questionnaire


class FloorTestCase(unittest.TestCase):
    """What every call says, whatever the researcher configured."""

    def test_the_floor_is_complete_and_ordered_in_both_languages(self) -> None:
        for language, order in (("de", FLOOR_ORDER_DE), ("en", FLOOR_ORDER_EN)):
            with self.subTest(language=language):
                task = build_task(study(language))
                positions = []
                for fragment in order:
                    self.assertIn(fragment, task, f"{fragment!r} missing from the call")
                    positions.append(task.index(fragment))
                self.assertEqual(
                    positions, sorted(positions), "the floor is spoken out of order"
                )
                # And the withdrawal route closes the call, after every question.
                last_question = max(
                    task.index(question["wording"])
                    for question in study(language)["questions"]
                    if question["wording"] in task
                )
                self.assertLess(last_question, task.index("WITHDRAWAL"))

    def test_no_language_leaks_into_the_other(self) -> None:
        german, english = build_task(study("de")), build_task(study("en"))
        for fragment in ("künstliche Intelligenz", "Zum Datenschutz:", "umfasst bis zu"):
            self.assertNotIn(fragment, english)
        for fragment in ("artificial intelligence", "About your data:", "has up to"):
            self.assertNotIn(fragment, german)


class OptionFlipTestCase(unittest.TestCase):
    """One option at a time: does the prompt change the way the map says?"""

    def flip(self, **overrides: object) -> tuple[str, str]:
        return build_task(study("de")), build_task(study("de", **overrides))

    def test_a_filter_rule_adds_a_filter_instruction_and_nothing_else_does(self) -> None:
        with_rule, without = self.flip(**{"questionnaire.jump_rules": ""})
        self.assertIn("FILTER: Ask only if", with_rule)
        self.assertNotIn("FILTER: Ask only if", without)

    def test_an_open_item_is_asked_freely_and_never_categorised(self) -> None:
        task = build_task(study("de"))
        self.assertIn("(open question, your own words)", task)
        self.assertIn("do not add an entry for this question in answers at all", task)
        # …and its id carries no category property in the schema at all.
        open_ids = [
            question["id"]
            for question in study("de")["questions"]
            if instrument.is_open(question)
        ]
        answers = result_schema(study("de"))["properties"]["answers"]["properties"]
        for open_id in open_ids:
            self.assertNotIn(open_id, answers)

    def test_asking_for_a_refusal_reason_reaches_the_task_and_the_schema(self) -> None:
        without = build_task(study("de", **{"ethics.on_refusal.ask_reason": False}))
        with_reason = build_task(study("de"))
        self.assertIn("what made them decline", with_reason)
        self.assertNotIn("what made them decline", without)
        self.assertIn(
            "refusal_reason",
            result_schema(study("de"))["properties"],
        )

    def test_offering_a_callback_reaches_the_task_and_the_schema(self) -> None:
        without = build_task(study("de", **{"ethics.on_refusal.offer_callback": False}))
        self.assertIn("call at another time", build_task(study("de")))
        self.assertNotIn("call at another time", without)

    def test_a_randomised_order_does_not_change_what_is_promised(self) -> None:
        """Order is a run-time property; the promise of scope must not move."""
        fixed = build_task(study("de", **{"questionnaire.order": "fixed"}))
        randomised = build_task(study("de", **{"questionnaire.order": "randomised"}))
        for task in (fixed, randomised):
            self.assertIn("umfasst bis zu", task)
        self.assertEqual(
            fixed.count("(say exactly)"), randomised.count("(say exactly)")
        )

    def test_the_scope_sentence_counts_the_questions_this_person_may_get(self) -> None:
        small = study("de", items=[ITEMS[0]])
        large = study("de", items=ITEMS * 2)
        # RC3: "1 Frage", singular, not "1 Fragen" — the noun is inflected.
        small_word = "Frage" if len(small["questions"]) == 1 else "Fragen"
        large_word = "Frage" if len(large["questions"]) == 1 else "Fragen"
        self.assertIn(f"bis zu {len(small['questions'])} {small_word}", build_task(small))
        self.assertIn(f"bis zu {len(large['questions'])} {large_word}", build_task(large))

    def test_app_side_options_leave_the_prompt_untouched(self) -> None:
        """Documented as app-side in the map: they must NOT reach the task.

        A setting that steers the run has no business in the spoken instruction.
        If one of these ever shows up in the task text, either the map or the
        code is wrong — and this test says which.
        """
        baseline = build_task(study("de"))
        for path, value in (
            ("contact_rules.attempts_per_person", 3),
            ("contact_rules.daily_quota", 7),
            ("sample.size", 99),
            ("fieldwork.keep_transcript", False),
            ("fieldwork.stop_on_error", True),
        ):
            with self.subTest(option=path):
                self.assertEqual(build_task(study("de", **{path: value})), baseline)


class MapAccountingTestCase(unittest.TestCase):
    """The numbers in PROMPT-MAP.md are counted, not typed.

    A map that quietly disagrees with the code is worse than none: it is read as
    current. So the two counts it leads with, and every field it calls declared,
    are checked against the registry itself.
    """

    def setUp(self) -> None:
        from researchcall import effect, forms

        self.effect, self.fields = effect, forms.load_fields()
        self.map_text = (ROOT / "PROMPT-MAP.md").read_text(encoding="utf-8")

    def test_the_map_states_the_number_of_settings_there_are(self) -> None:
        self.assertIn(f"configured in {len(self.fields)} settings", self.map_text)

    def test_every_declared_field_is_named_in_the_map(self) -> None:
        declared = [
            field.path
            for field in self.fields
            if self.effect.EFFECTS.get(field.path, ("?",))[0] == self.effect.DECLARED
        ]
        self.assertIn(f"{len(declared)} of {len(self.fields)} fields are `declared`", self.map_text)
        for path in declared:
            with self.subTest(path=path):
                self.assertIn(path, self.map_text)

    def test_the_map_names_every_gate_the_code_actually_checks(self) -> None:
        from researchcall.phrases import phrases_from_questionnaire

        keys = {phrase.key for phrase in phrases_from_questionnaire(study("de"))}
        self.assertEqual(
            keys, {"ai_disclosure", "consent_question", "data_statement", "stop_right"}
        )
        for key in keys:
            with self.subTest(gate=key):
                self.assertIn(key, self.map_text)


class GoldenTaskTestCase(unittest.TestCase):
    """Whole task texts on disk: the check that notices what nobody expected."""

    SCENARIOS = {
        "de-standard": dict(language="de"),
        "en-standard": dict(language="en"),
        "de-no-filters": dict(language="de", **{"questionnaire.jump_rules": ""}),
        "de-no-refusal-questions": dict(
            language="de",
            **{
                "ethics.on_refusal.ask_reason": False,
                "ethics.on_refusal.offer_callback": False,
            },
        ),
    }

    def test_the_generated_call_matches_its_golden(self) -> None:
        GOLDENS.mkdir(exist_ok=True)
        writing = os.environ.get("RESEARCHCALL_WRITE_GOLDENS") == "1"
        for name, arguments in self.SCENARIOS.items():
            with self.subTest(scenario=name):
                language = str(arguments.pop("language"))
                task = build_task(study(language, **arguments))
                path = GOLDENS / f"task-{name}.txt"
                if writing:
                    path.write_text(task + "\n", encoding="utf-8")
                    continue
                self.assertTrue(
                    path.exists(),
                    f"missing golden {path.name}; regenerate with "
                    f"RESEARCHCALL_WRITE_GOLDENS=1",
                )
                self.assertEqual(
                    task.strip(),
                    path.read_text(encoding="utf-8").strip(),
                    f"the call changed for {name}; read the diff before updating",
                )


if __name__ == "__main__":
    unittest.main()
