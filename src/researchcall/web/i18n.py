"""Interface text in every supported language.

The mechanism is the one already in use in this workshop's PySide tooling
(``translator.py`` / ``manage_translations.py`` in Editor-PythonBox): one flat
JSON table ``{key: {"de": ..., "en": ...}}``, a ``t(key)`` lookup, and a scanner
that reports keys without a translation.

Two things are adapted rather than copied:

* the key is the **English** source string, because this repository is written in
  English and an untranslated key then still renders as correct English;
* ``t()`` never writes. The desktop original appends unknown strings to the table
  on first use, which is a side effect a web process must not have on a request.
  ``manage_translations.py`` does the writing instead.

Field text is *not* here. A field's label, question and help live in its form
definition under ``pipeline/_shared/forms/`` and are read from there in every
language, so that a decision has exactly one place — see ``researchcall.forms``.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any


LOCALES = pathlib.Path(__file__).resolve().parent / "locales"
TABLE_PATH = LOCALES / "ui.json"

# The first entry is what a visitor gets before choosing: the jury of an
# English-language competition reads English. German is complete and one click
# away — the same arrangement as README.md beside README_de.md.
LANGUAGES: tuple[str, ...] = ("en", "de")
DEFAULT_LANGUAGE = LANGUAGES[0]

LANGUAGE_NAMES = {"en": "English", "de": "Deutsch"}


def load_table(path: pathlib.Path | None = None) -> dict[str, dict[str, str]]:
    """Read the translation table from disk."""
    path = path or TABLE_PATH
    if not path.exists():
        return {}
    loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path}: translation table is not an object")
    return loaded


def normalize(language: str | None) -> str:
    """Any incoming language hint, reduced to one we actually serve."""
    if not language:
        return DEFAULT_LANGUAGE
    code = str(language).strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


class Translator:
    """Reads one language. Immutable, so concurrent requests cannot collide."""

    def __init__(
        self,
        language: str = DEFAULT_LANGUAGE,
        table: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.language = normalize(language)
        self._table = table if table is not None else load_table()

    def t(self, key: str) -> str:
        """The key in the current language; the key itself when untranslated."""
        entry = self._table.get(key)
        if not entry:
            return key
        return entry.get(self.language) or entry.get(DEFAULT_LANGUAGE) or key

    def switch(self, language: str) -> "Translator":
        return Translator(language, self._table)

    def other_languages(self) -> list[tuple[str, str]]:
        """The languages a visitor can switch to, as (code, name)."""
        return [
            (code, LANGUAGE_NAMES.get(code, code.upper()))
            for code in LANGUAGES
            if code != self.language
        ]


def untranslated(
    keys: list[str],
    language: str,
    table: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    """Which of these keys have no text in that language."""
    table = table if table is not None else load_table()
    missing = []
    for key in keys:
        entry = table.get(key)
        if not entry or not entry.get(language):
            missing.append(key)
    return missing
