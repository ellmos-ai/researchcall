from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall.forms import (
    REQUIRED_FORM_KEYS,
    _read_entries_plain,
    form,
    interview,
    load_fields,
)


FORM_DIR = ROOT / "pipeline" / "_shared" / "forms"
EXPECTED_FILES = {
    "analysis.forms.yaml",
    "ethics.forms.yaml",
    "fieldwork.forms.yaml",
    "instrument.forms.yaml",
    "pretest.forms.yaml",
    "reporting.forms.yaml",
    "research-question.forms.yaml",
    "sampling.forms.yaml",
}


class FormDefinitionTestCase(unittest.TestCase):
    def test_every_station_file_loads_individually(self) -> None:
        paths = sorted(FORM_DIR.glob("*.forms.yaml"))
        self.assertEqual({path.name for path in paths}, EXPECTED_FILES)
        for path in paths:
            with self.subTest(path=path.name):
                fields = load_fields(path)
                self.assertTrue(fields)
                self.assertTrue(all(field.path for field in fields))

    def test_every_entry_declares_the_complete_form_contract(self) -> None:
        for path in sorted(FORM_DIR.glob("*.forms.yaml")):
            for entry in _read_entries_plain(path):
                with self.subTest(path=path.name, field=entry.get("field")):
                    self.assertEqual(REQUIRED_FORM_KEYS - entry.keys(), set())
                    self.assertTrue(entry["field"])

    def test_locked_fields_create_neither_questions_nor_form_fields(self) -> None:
        fields = load_fields(FORM_DIR)
        locked = [field for field in fields if field.locked]
        self.assertTrue(locked)
        for field in locked:
            with self.subTest(field=field.path):
                self.assertIsNone(field.as_question())
                self.assertIsNone(field.as_form_field())

        visible_names = {entry["name"] for entry in form(fields)}
        self.assertTrue(all(field.path not in visible_names for field in locked))
        self.assertEqual(
            len(interview(fields)),
            sum(field.as_question() is not None for field in fields),
        )

    def test_dependency_free_reader_preserves_inline_list_defaults(self) -> None:
        sampling = {
            entry["field"]: entry
            for entry in _read_entries_plain(FORM_DIR / "sampling.forms.yaml")
        }
        self.assertEqual(
            sampling["sample.time_windows"]["default"],
            ["morning", "afternoon", "evening"],
        )


if __name__ == "__main__":
    unittest.main()
