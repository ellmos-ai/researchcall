"""What the interface remembers between two clicks.

A workspace is a directory holding one JSON file. It carries the answers to the
form definitions, which stations are finished, and which values were changed
after their station had already been closed. That last list is the point: the
pipeline allows later additions but requires them to be *marked* as later ones.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
from datetime import datetime, timezone
from typing import Any, Iterable

from .. import forms
from ..huckepack_storage import session_document, store_session_document
from ..server_mode import current_mode


STATIONS: tuple[str, ...] = (
    "01-research-question",
    "02-instrument",
    "03-ethics",
    "04-sampling",
    "05-pretest",
    "06-fieldwork",
    "07-analysis",
    "08-reporting",
)

WORKSPACE_FILE = "workspace.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def coerce(raw: str | list[str] | None, field_type: str) -> Any:
    """Turn what a browser sends into what the config should carry."""
    if field_type == "bool":
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        return str(raw).lower() in {"on", "true", "1", "yes"}
    if field_type == "multi":
        if raw is None:
            return []
        return list(raw) if isinstance(raw, list) else [raw]
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    text = "" if raw is None else str(raw).strip()
    if field_type == "number":
        if text == "":
            return None
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return None
    if field_type in {"list", "table"}:
        return [line.strip() for line in text.splitlines() if line.strip()]
    return text or None


def is_answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


@dataclasses.dataclass
class Workspace:
    """The state of one study in preparation."""

    path: pathlib.Path
    values: dict[str, Any] = dataclasses.field(default_factory=dict)
    _completed: dict[str, str] = dataclasses.field(default_factory=dict, repr=False)
    _amendments: list[dict[str, str]] = dataclasses.field(default_factory=list, repr=False)
    test_mode: bool = False
    test_values: dict[str, Any] = dataclasses.field(default_factory=dict)
    test_completed: dict[str, str] = dataclasses.field(default_factory=dict)
    test_amendments: list[dict[str, str]] = dataclasses.field(default_factory=list)
    #: The language the example content in ``test_values`` was last written
    #: in. ``None`` before test mode has ever been enabled. See
    #: ``enable_test_mode`` and ``sync_test_mode_language`` — RC1
    #: (Endabnahme 2026-08-22).
    test_example_language: str | None = None

    # --- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "Workspace":
        """Read the workbench file — from disk, or from the browser's copy.

        In a huckepack mode this file must not land on the host's disk either,
        and it has to travel with an export: a backup that restored the
        database but not the answers would be a backup in name only. It is
        therefore kept inside the session database, which makes the snapshot
        the single artefact that carries everything.
        """
        directory = pathlib.Path(path)
        if current_mode().stores_in_browser:
            raw = session_document(WORKSPACE_FILE)
            if not raw:
                return cls(path=directory)
            stored = json.loads(raw)
            return cls(
                path=directory,
                values=dict(stored.get("values", {})),
                _completed=dict(stored.get("completed", {})),
                _amendments=list(stored.get("amendments", [])),
                test_mode=bool(stored.get("test_mode", False)),
                test_values=dict(stored.get("test_values", {})),
                test_completed=dict(stored.get("test_completed", {})),
                test_amendments=list(stored.get("test_amendments", [])),
                test_example_language=stored.get("test_example_language"),
            )
        file = directory / WORKSPACE_FILE
        if not file.exists():
            return cls(path=directory)
        stored = json.loads(file.read_text(encoding="utf-8"))
        return cls(
            path=directory,
            values=dict(stored.get("values", {})),
            _completed=dict(stored.get("completed", {})),
            _amendments=list(stored.get("amendments", [])),
            test_mode=bool(stored.get("test_mode", False)),
            test_values=dict(stored.get("test_values", {})),
            test_completed=dict(stored.get("test_completed", {})),
            test_amendments=list(stored.get("test_amendments", [])),
            test_example_language=stored.get("test_example_language"),
        )

    def save(self) -> None:
        payload = {
            "values": self.values,
            "completed": self._completed,
            "amendments": self._amendments,
            "test_mode": self.test_mode,
            "test_values": self.test_values,
            "test_completed": self.test_completed,
            "test_amendments": self.test_amendments,
            "test_example_language": self.test_example_language,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if current_mode().stores_in_browser:
            store_session_document(WORKSPACE_FILE, text)
            return
        self.path.mkdir(parents=True, exist_ok=True)
        target = self.path / WORKSPACE_FILE
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(target)

    # --- values ------------------------------------------------------------

    @property
    def completed(self) -> dict[str, str]:
        """The station progress for the active, isolated workspace."""
        return self.test_completed if self.test_mode else self._completed

    @completed.setter
    def completed(self, value: dict[str, str]) -> None:
        if self.test_mode:
            self.test_completed = value
        else:
            self._completed = value

    @property
    def amendments(self) -> list[dict[str, str]]:
        """The later additions for the active, isolated workspace."""
        return self.test_amendments if self.test_mode else self._amendments

    @amendments.setter
    def amendments(self, value: list[dict[str, str]]) -> None:
        if self.test_mode:
            self.test_amendments = value
        else:
            self._amendments = value

    def active_values(self) -> dict[str, Any]:
        return self.test_values if self.test_mode else self.values

    def enable_test_mode(self, examples: dict[str, Any], language: str) -> None:
        """Open or resume the example workspace without changing study answers.

        ``language`` is the interface language the caller generated
        ``examples`` in. It is recorded once, on the first enable, so a later
        UI-language switch has something to compare against (see
        ``sync_test_mode_language``). A later re-enable keeps whatever
        language was recorded before, even if the visitor is now viewing a
        different one — ``examples`` here never overwrites an existing value
        (``setdefault``), so recording the new language would only make a
        needed sync look already done.
        """
        for path, value in examples.items():
            self.test_values.setdefault(path, value)
        self.test_mode = True
        if self.test_example_language is None:
            self.test_example_language = language

    def disable_test_mode(self) -> None:
        """Return to the study exactly as it was before the tour."""
        self.test_mode = False

    def sync_test_mode_language(
        self,
        language: str,
        examples: dict[str, Any],
        previous_examples: dict[str, Any],
    ) -> bool:
        """Re-translate example content that is still untouched, after a
        visitor switches the interface language while test mode is active.

        RC1 (Endabnahme 2026-08-22): switching the workbench to German left
        the example study's text in English — ``enable_test_mode`` writes
        example values exactly once, and nothing ever revisited them when the
        visitor's chosen language changed afterwards.

        A field is only rewritten here when its CURRENT value still equals
        the example text in the language it was last generated in
        (``previous_examples``) — the same test that tells a genuine answer
        apart from an untouched example everywhere else in this class. A
        field the researcher has since edited never matches that value
        exactly and is left alone; the empty-tour default for a field the
        researcher cleared out is also left alone (it is not a key of
        ``examples`` in the first place, since ``example_values`` only
        returns declared, unlocked fields).

        Returns whether anything changed, so the caller knows whether the
        workspace needs saving.
        """
        if not self.test_mode or language == self.test_example_language:
            return False
        changed = False
        for path, new_value in examples.items():
            if path not in self.test_values:
                continue
            if self.test_values[path] == previous_examples.get(path):
                self.test_values[path] = new_value
                changed = True
        self.test_example_language = language
        return changed

    def artifact_directory(self) -> pathlib.Path:
        """Keep fixture-tour outputs separate from actual study outputs."""
        return self.path / "test-mode-artifacts" if self.test_mode else self.path

    def value(self, field: forms.Field) -> Any:
        """The stored answer, or the default the definition brings along."""
        active = self.active_values()
        if field.path in active:
            return active[field.path]
        return field.default

    def record(self, station: str, submitted: dict[str, Any]) -> list[str]:
        """Store answers for one station and return the paths counted as later additions."""
        amended: list[str] = []
        active = self.active_values()
        already_closed = station in self.completed
        for path, value in submitted.items():
            if already_closed and active.get(path) != value:
                amended.append(path)
                self.amendments.append(
                    {"station": station, "field": path, "at": utc_now()}
                )
            active[path] = value
        return amended

    # --- gating ------------------------------------------------------------

    def missing_required(self, fields: Iterable[forms.Field], station: str) -> list[str]:
        """Required, visible fields of this station that carry no answer."""
        missing = []
        for field in fields:
            if field.station != station or field.locked or not field.required:
                continue
            if not is_answered(self.value(field)):
                missing.append(field.path)
        return missing

    def is_open(self, station: str) -> bool:
        """A station is reachable once its predecessor is finished."""
        if self.test_mode:
            return True
        index = STATIONS.index(station)
        if index == 0:
            return True
        return STATIONS[index - 1] in self.completed

    def completed_through(self, station: str) -> bool:
        """Whether every station up to and including ``station`` is finished.

        Auxiliary views such as the instrument check and field-phase monitor are
        direct URLs. They must obey the same pipeline gate as the station rail;
        otherwise the navigation only *looks* gated while the actions are open.
        """
        if self.test_mode:
            return True
        end = STATIONS.index(station) + 1
        return all(name in self.completed for name in STATIONS[:end])

    def complete(self, fields: Iterable[forms.Field], station: str) -> list[str]:
        """Close a station. Returns what is still missing instead of closing it."""
        missing = self.missing_required(fields, station)
        if missing:
            return missing
        self.completed.setdefault(station, utc_now())
        return []

    def reopen(self, station: str) -> None:
        self.completed.pop(station, None)

    def amended_fields(self, station: str) -> set[str]:
        return {entry["field"] for entry in self.amendments if entry["station"] == station}

    # --- the config this produces -----------------------------------------

    def config(self, fields: Iterable[forms.Field]) -> dict[str, Any]:
        """The nested config the pipeline reads — defaults with the answers on top.

        Locked settings appear here even though no control shows them: they are
        part of the frame, so the config states them rather than hiding them.
        """
        fields = list(fields)
        nested = forms.config_defaults(fields)
        active = self.active_values()
        for field in fields:
            if field.path not in active:
                continue
            node = nested
            *parents, leaf = field.path.split(".")
            for part in parents:
                node = node.setdefault(part, {})
            node[leaf] = active[field.path]
        return nested
