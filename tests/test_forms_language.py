"""The form definitions have to carry every language they promise.

A missing English label is not a cosmetic gap: the same definition feeds the
config, the agent's question and the interface, so a hole shows up in all three.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall.forms import (  # noqa: E402
    SOURCE_LANGUAGE,
    TRANSLATED_KEYS,
    _read_entries_plain,
    form,
    interview,
    load_fields,
    untranslated,
)


FORM_DIR = ROOT / "pipeline" / "_shared" / "forms"
LANGUAGES = ("de", "en")


class LanguageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fields = load_fields(FORM_DIR)

    def test_every_definition_carries_every_language(self) -> None:
        for language in LANGUAGES:
            if language == SOURCE_LANGUAGE:
                continue
            with self.subTest(language=language):
                self.assertEqual(untranslated(self.fields, language), [])

    def test_all_declared_languages_are_the_supported_ones(self) -> None:
        found: set[str] = set()
        for field in self.fields:
            found |= field.languages()
        self.assertEqual(found, set(LANGUAGES))

    def test_labels_and_questions_actually_change_with_the_language(self) -> None:
        by_path = {field.path: field for field in self.fields}
        method = by_path["sample.method"]
        self.assertEqual(method.text("label", "de"), "Ziehungsverfahren")
        self.assertEqual(method.text("label", "en"), "Sampling method")
        self.assertEqual(
            [option["label"] for option in method.options_in("en")],
            ["Random", "Stratified", "Census"],
        )
        self.assertEqual(
            [option["label"] for option in method.options_in("de")],
            ["Zufall", "Geschichtet", "Vollerhebung"],
        )

    def test_an_unknown_language_falls_back_to_the_source_text(self) -> None:
        field = next(f for f in self.fields if f.path == "sample.size")
        self.assertEqual(field.text("label", "fr"), field.label)
        self.assertEqual(
            [option["label"] for option in field.options_in("fr")],
            [option["label"] for option in field.options_in(SOURCE_LANGUAGE)],
        )

    def test_locked_fields_stay_invisible_in_every_language(self) -> None:
        locked = [field for field in self.fields if field.locked]
        self.assertTrue(locked)
        for language in LANGUAGES:
            visible = {entry["name"] for entry in form(self.fields, language=language)}
            asked = interview(self.fields, language=language)
            for field in locked:
                with self.subTest(language=language, field=field.path):
                    self.assertIsNone(field.as_form_field(language))
                    self.assertIsNone(field.as_question(language))
                    self.assertNotIn(field.path, visible)
                    self.assertNotIn(field.text("label", language), asked)

    def test_the_three_ways_in_agree_on_their_counts_in_both_languages(self) -> None:
        counts = {
            language: (
                len(form(self.fields, language=language)),
                len(interview(self.fields, language=language)),
            )
            for language in LANGUAGES
        }
        self.assertEqual(counts["de"], counts["en"])
        visible, asked = counts["de"]
        locked = sum(1 for field in self.fields if field.locked)
        self.assertEqual(visible + locked, len(self.fields))
        self.assertGreater(visible, asked)

    def test_the_dependency_free_reader_also_sees_the_translations(self) -> None:
        """PyYAML is optional, so the fallback reader must not lose a language."""
        entries = {
            entry["field"]: entry
            for entry in _read_entries_plain(FORM_DIR / "sampling.forms.yaml")
        }
        method = entries["sample.method"]
        for key in TRANSLATED_KEYS:
            self.assertIn(f"{key}_en", method, key)
        self.assertEqual(method["label_en"], "Sampling method")
        self.assertEqual(
            [option.get("label_en") for option in method["options"]],
            ["Random", "Stratified", "Census"],
        )


if __name__ == "__main__":
    unittest.main()
