"""Load form definitions and turn them into the three ways in.

One definition, three surfaces: a config default, a spoken question for an agent,
and a field for a user interface. Nothing here invents a field — everything comes
from the YAML files under pipeline/_shared/forms/ and the station folders, so a
setting that is not written down cannot appear in any of the three.
"""

from __future__ import annotations

import dataclasses
import pathlib
import re
from typing import Any, Iterable


# src/researchcall/forms.py -> src/researchcall -> src -> repo root
PIPELINE_ROOT = pathlib.Path(__file__).resolve().parents[2] / "pipeline"

REQUIRED_FORM_KEYS = {
    "field",
    "station",
    "label",
    "question",
    "type",
    "options",
    "default",
    "help",
    "required",
    "locked",
}

# The keys whose text is shown to a human and therefore needs every language.
TRANSLATED_KEYS = ("label", "question", "help")

# The language the bare keys are written in. A second language lives beside them
# as "<key>_<language>", so adding a third one is a matter of the YAML files, not
# of this module. Field text belongs to the field definition; putting it into a
# separate translation table would create a second source of truth for the same
# decision — the one thing this module exists to prevent.
SOURCE_LANGUAGE = "de"

_LOCALIZED = re.compile(r"^(?P<key>label|question|help)_(?P<language>[a-z]{2})$")


@dataclasses.dataclass(frozen=True)
class Field:
    """One decision, expressed once and read by all three ways in."""

    path: str                      # dotted path into the config, e.g. "sample.method"
    station: str
    label: str = ""
    question: str = ""
    type: str = "text"
    options: tuple[dict[str, str], ...] = ()
    default: Any = None
    help: str = ""
    required: bool = False
    locked: bool = False           # part of the frame, never an option
    # "<key>_<language>" -> text, e.g. {"label_en": "Sampling frame"}
    localized: dict[str, str] = dataclasses.field(default_factory=dict)

    # --- language ----------------------------------------------------------

    def text(self, key: str, language: str = SOURCE_LANGUAGE) -> str:
        """The text of one key in one language, falling back to the source."""
        if language != SOURCE_LANGUAGE:
            translated = self.localized.get(f"{key}_{language}")
            if translated:
                return translated
        return str(getattr(self, key, "") or "")

    def languages(self) -> set[str]:
        """Every language this field carries text for."""
        found = {SOURCE_LANGUAGE}
        for name in self.localized:
            match = _LOCALIZED.match(name)
            if match:
                found.add(match.group("language"))
        return found

    def options_in(self, language: str = SOURCE_LANGUAGE) -> list[dict[str, str]]:
        """The options with their labels in one language."""
        rendered = []
        for option in self.options:
            label = option.get("label", "")
            if language != SOURCE_LANGUAGE:
                label = option.get(f"label_{language}") or label
            rendered.append({"value": option.get("value", ""), "label": label})
        return rendered

    # --- the three ways in -------------------------------------------------

    def as_config_entry(self) -> tuple[str, Any]:
        """What the config carries."""
        return self.path, self.default

    def as_question(self, language: str = SOURCE_LANGUAGE) -> str | None:
        """What an agent asks.

        Returns None when the agent must not ask: locked settings are not up for
        discussion, and a value that already has a default is not worth a turn of
        conversation — it is mentioned only when it deviates.
        """
        if self.locked:
            return None
        if self.default is not None and not self.required:
            return None
        return (
            self.text("question", language)
            or self.text("label", language)
            or self.path
        )

    def as_form_field(self, language: str = SOURCE_LANGUAGE) -> dict[str, Any] | None:
        """What a user interface shows. Locked settings show nothing at all."""
        if self.locked:
            return None
        return {
            "name": self.path,
            "label": self.text("label", language) or self.path,
            "type": self.type,
            "options": self.options_in(language),
            "value": self.default,
            "help": self.text("help", language),
            "required": self.required,
        }


# --- reading -------------------------------------------------------------------

_SCALAR = re.compile(r"^(?P<key>[A-Za-z_][\w.]*):\s*(?P<value>.*)$")


def _coerce(raw: str) -> Any:
    """Turn a YAML scalar into a Python value, conservatively."""
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    if text in {"true", "True"}:
        return True
    if text in {"false", "False"}:
        return False
    if text in {"", "~", "null"}:
        return None
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_coerce(part) for part in inner.split(",")]
    return text


def load_fields(root: pathlib.Path | None = None) -> list[Field]:
    """Read every *.forms.yaml below the pipeline and return the fields.

    Uses PyYAML when available and falls back to a small reader otherwise, so the
    pipeline stays readable without pulling in a dependency for a handful of files.
    """
    root = root or PIPELINE_ROOT
    fields: list[Field] = []
    paths = [root] if root.is_file() else sorted(root.rglob("*.forms.yaml"))
    for path in paths:
        for entry in _read_entries(path):
            missing = REQUIRED_FORM_KEYS - entry.keys()
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(f"{path}: form entry missing keys: {names}")
            if not str(entry["field"]).strip():
                raise ValueError(f"{path}: form entry has an empty field")
            fields.append(
                Field(
                    path=entry["field"],
                    station=entry["station"],
                    label=entry["label"],
                    question=entry["question"],
                    type=entry["type"],
                    options=tuple(entry["options"] or ()),
                    default=entry["default"],
                    help=entry["help"],
                    required=bool(entry["required"]),
                    locked=bool(entry["locked"]),
                    localized={
                        name: str(value)
                        for name, value in entry.items()
                        if _LOCALIZED.match(name) and value is not None
                    },
                )
            )
    return fields


def untranslated(fields: Iterable[Field], language: str) -> list[tuple[str, str]]:
    """Which field texts are still missing in one language.

    An empty source text needs no translation — a locked field asks nothing, so
    its empty question stays empty everywhere.
    """
    missing = []
    for field in fields:
        for key in TRANSLATED_KEYS:
            if not getattr(field, key, ""):
                continue
            if not field.localized.get(f"{key}_{language}"):
                missing.append((field.path, f"{key}_{language}"))
        for option in field.options:
            if option.get("label") and not option.get(f"label_{language}"):
                missing.append((field.path, f"option:{option.get('value', '')}"))
    return missing


def _read_entries(path: pathlib.Path) -> Iterable[dict[str, Any]]:
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        return [e for e in loaded if isinstance(e, dict)]
    except ImportError:
        return _read_entries_plain(path)


def _read_entries_plain(path: pathlib.Path) -> list[dict[str, Any]]:
    """Minimal reader for the shape these files actually use.

    Handles a list of mappings with scalar values, inline option maps and folded
    help text. Anything more elaborate belongs in PyYAML, not here.
    """
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending_key: str | None = None
    folded: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        if line.startswith("- "):
            if current is not None:
                _flush(current, pending_key, folded)
                entries.append(current)
            current, pending_key, folded = {}, None, []
            line = "  " + line[2:]

        if current is None:
            continue

        stripped = line.strip()

        if stripped.startswith("- {") and pending_key == "options":
            if current.get("options") is None:
                current["options"] = []
            current["options"].append(_inline_map(stripped[2:]))
            continue

        match = _SCALAR.match(stripped)
        if not match:
            if pending_key:
                folded.append(stripped)
            continue

        _flush(current, pending_key, folded)
        folded = []
        key, value = match.group("key"), match.group("value")
        if value.strip() in {">", "|", ""}:
            pending_key = key
            if value.strip() == "":
                current[key] = None
                pending_key = key if key == "options" else key
        else:
            current[key] = _coerce(value)
            pending_key = None

    if current is not None:
        _flush(current, pending_key, folded)
        entries.append(current)
    return entries


def _flush(entry: dict[str, Any], key: str | None, folded: list[str]) -> None:
    if key and folded:
        entry[key] = " ".join(folded)


def _inline_map(text: str) -> dict[str, str]:
    inner = text.strip().lstrip("{").rstrip("}")
    out: dict[str, str] = {}
    for part in inner.split(","):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


# --- the three renderings ------------------------------------------------------

def config_defaults(fields: Iterable[Field]) -> dict[str, Any]:
    """Nested config skeleton with every default in place."""
    out: dict[str, Any] = {}
    for field in fields:
        if not field.path:
            continue
        node = out
        *parents, leaf = field.path.split(".")
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = field.default
    return out


def interview(
    fields: Iterable[Field],
    station: str | None = None,
    language: str = SOURCE_LANGUAGE,
) -> list[str]:
    """The questions an agent actually needs to ask — and no others."""
    questions = []
    for field in fields:
        if station and field.station != station:
            continue
        asked = field.as_question(language)
        if asked:
            questions.append(asked)
    return questions


def form(
    fields: Iterable[Field],
    station: str | None = None,
    language: str = SOURCE_LANGUAGE,
) -> list[dict[str, Any]]:
    """The visible fields of a user interface, locked ones removed."""
    rendered = []
    for field in fields:
        if station and field.station != station:
            continue
        entry = field.as_form_field(language)
        if entry:
            rendered.append(entry)
    return rendered
