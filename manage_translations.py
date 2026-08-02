"""Keep the interface translation table complete.

Scans the web package for ``t("...")`` calls, adds unknown keys to
``src/researchcall/web/locales/ui.json`` with an empty slot per language, and
reports what is still missing. Same idea as the ``manage_translations.py`` used by
the PySide tooling in this workshop; the patterns match this project's call style
instead of Qt's, and the key is the English source string.

Field text is deliberately out of scope. A field's label, question and help live
in its form definition under ``pipeline/_shared/forms/`` in every language, so
that a decision exists in exactly one place. ``--fields`` checks those too and
reports anything untranslated, but never edits them: a missing English label is a
gap in the definition, not in a translation table.

    python manage_translations.py            # scan, add, report
    python manage_translations.py --check    # report only, exit 1 when incomplete
    python manage_translations.py --fields   # also check the form definitions
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "src" / "researchcall" / "web"
TABLE = SOURCE / "locales" / "ui.json"
FORMS = ROOT / "pipeline"

LANGUAGES = ("en", "de")

# How interface text is written in this project.
PATTERNS = [
    re.compile(r'\.t\(\s*"((?:[^"\\]|\\.)+)"\s*\)'),
    re.compile(r'\.t\(\s*\'((?:[^\'\\]|\\.)+)\'\s*\)'),
]


_ESCAPE = re.compile(r"\\(.)")
_ESCAPED = {"n": "\n", "t": "\t", "r": "\r"}


def _unescape(text: str) -> str:
    """Undo source-level escaping only — never touch non-ASCII characters."""
    return _ESCAPE.sub(lambda m: _ESCAPED.get(m.group(1), m.group(1)), text)


def dynamic_keys() -> set[str]:
    """Keys looked up through a variable, which no regex can see.

    The station titles are the only ones: ``t(STATION_TITLES[station])``. They are
    read from the mapping itself, so a new station cannot be forgotten here.
    """
    sys.path.insert(0, str(ROOT / "src"))
    from researchcall.web.render import STATION_TITLES  # noqa: PLC0415

    return set(STATION_TITLES.values())


def used_keys() -> list[str]:
    found: set[str] = set(dynamic_keys())
    for path in sorted(SOURCE.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for pattern in PATTERNS:
            for match in pattern.findall(text):
                found.add(_unescape(match))
    return sorted(found)


def load() -> dict[str, dict[str, str]]:
    if not TABLE.exists():
        return {}
    return json.loads(TABLE.read_text(encoding="utf-8"))


def save(table: dict[str, dict[str, str]]) -> None:
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    temporary = TABLE.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(dict(sorted(table.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(TABLE)


def check_fields() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from researchcall import forms  # noqa: PLC0415  (tool-only import)

    fields = forms.load_fields(FORMS)
    problems = 0
    for language in LANGUAGES:
        if language == forms.SOURCE_LANGUAGE:
            continue
        missing = forms.untranslated(fields, language)
        if missing:
            problems += len(missing)
            print(f"[!] form definitions missing {language}: {len(missing)}")
            for path, key in missing[:20]:
                print(f"    - {path} -> {key}")
    if not problems:
        print(f"[ok] {len(fields)} form definitions carry every language.")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report only, never write")
    parser.add_argument("--fields", action="store_true", help="also check form definitions")
    args = parser.parse_args(argv)

    table = load()
    keys = used_keys()

    added = []
    for key in keys:
        if key not in table:
            table[key] = {"en": key, "de": ""}
            added.append(key)

    unused = sorted(set(table) - set(keys))
    missing = {
        language: [key for key in keys if not table.get(key, {}).get(language)]
        for language in LANGUAGES
    }

    if added and not args.check:
        save(table)
        print(f"[+] {len(added)} new key(s) added to {TABLE.relative_to(ROOT)}")
        for key in added[:20]:
            print(f"    - {key}")
    elif added:
        print(f"[!] {len(added)} key(s) used but not in the table")
        for key in added[:20]:
            print(f"    - {key}")

    for language, keys_missing in missing.items():
        if keys_missing:
            print(f"[!] {len(keys_missing)} key(s) without {language}")
            for key in keys_missing[:20]:
                print(f"    - {key}")
    if unused:
        print(f"[i] {len(unused)} key(s) in the table but no longer used")

    problems = len(added) if args.check else 0
    problems += sum(len(value) for value in missing.values())
    if args.fields:
        problems += check_fields()

    print(f"[i] {len(keys)} interface key(s) in use, {len(table)} in the table")
    if problems and args.check:
        return 1
    if not problems:
        print("[ok] every interface string has every language.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
