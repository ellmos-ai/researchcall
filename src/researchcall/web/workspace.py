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
    completed: dict[str, str] = dataclasses.field(default_factory=dict)
    amendments: list[dict[str, str]] = dataclasses.field(default_factory=list)

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
            completed=dict(stored.get("completed", {})),
            amendments=list(stored.get("amendments", [])),
        )

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        payload = {
            "values": self.values,
            "completed": self.completed,
            "amendments": self.amendments,
        }
        target = self.path / WORKSPACE_FILE
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(target)

    # --- values ------------------------------------------------------------

    def value(self, field: forms.Field) -> Any:
        """The stored answer, or the default the definition brings along."""
        if field.path in self.values:
            return self.values[field.path]
        return field.default

    def record(self, station: str, submitted: dict[str, Any]) -> list[str]:
        """Store answers for one station and return the paths counted as later additions."""
        amended: list[str] = []
        already_closed = station in self.completed
        for path, value in submitted.items():
            if already_closed and self.values.get(path) != value:
                amended.append(path)
                self.amendments.append(
                    {"station": station, "field": path, "at": utc_now()}
                )
            self.values[path] = value
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
        for field in fields:
            if field.path not in self.values:
                continue
            node = nested
            *parents, leaf = field.path.split(".")
            for part in parents:
                node = node.setdefault(part, {})
            node[leaf] = self.values[field.path]
        return nested
