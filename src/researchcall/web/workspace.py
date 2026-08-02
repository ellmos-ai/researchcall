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

    # --- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "Workspace":
        directory = pathlib.Path(path)
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
        )

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        payload = {
            "values": self.values,
            "completed": self._completed,
            "amendments": self._amendments,
            "test_mode": self.test_mode,
            "test_values": self.test_values,
            "test_completed": self.test_completed,
            "test_amendments": self.test_amendments,
        }
        target = self.path / WORKSPACE_FILE
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
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

    def enable_test_mode(self, examples: dict[str, Any]) -> None:
        """Open or resume the example workspace without changing study answers."""
        for path, value in examples.items():
            self.test_values.setdefault(path, value)
        self.test_mode = True

    def disable_test_mode(self) -> None:
        """Return to the study exactly as it was before the tour."""
        self.test_mode = False

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
