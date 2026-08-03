"""Mono-call or multi-call: decided by evidence, not by preference.

The CALL-E request format carries a ``recipients`` list, and the documentation
describes batch dispatch. This installation has verified exactly one thing with
a real call: the serial path — one recipient per request (EVIDENCE-001). The
batch path is documented but unproven here.

So the rule is availability-first, the way the operator put it: *the app tests
whether multi-call works; if not, it sets itself to mono-call.* Concretely:

* ``mono`` is the default and always available. It is the proven path.
* ``multi`` is only ever used when three things hold at once: the study asked
  for it, a recorded probe has verified it, and the transport in use actually
  offers a batch call. Anything else downgrades to mono — *with the reason
  written down*, because a silent downgrade would make the field report lie
  about how the calls were made.
* ``untested`` is a state of its own. A capability nobody has probed must not
  read like one that failed; the report says "untested", not "unavailable".

The probe itself is a deliberate, operator-started step: verifying batch
dispatch costs a real batch of calls to the operator's own numbers. This module
records and evaluates probe results; it never places calls on its own.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .database import transaction, utc_now


MULTI_CALL = "multi_call"


class DispatchMode(str, Enum):
    MONO = "mono"
    MULTI = "multi"


class CapabilityStatus(str, Enum):
    UNTESTED = "untested"
    VERIFIED = "verified"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class Capability:
    name: str
    status: CapabilityStatus
    evidence: dict[str, Any]
    checked_at: str | None


@dataclass(frozen=True)
class DispatchDecision:
    """What will actually happen, what was asked for, and why they differ."""

    mode: DispatchMode
    requested: DispatchMode
    downgrade_reason: str | None = None

    @property
    def downgraded(self) -> bool:
        return self.mode is not self.requested

    def to_detail(self) -> dict[str, Any]:
        """The lines every attempt record carries about its dispatch."""
        detail: dict[str, Any] = {
            "dispatch_mode": self.mode.value,
            "dispatch_requested": self.requested.value,
        }
        if self.downgrade_reason:
            detail["dispatch_downgrade_reason"] = self.downgrade_reason
        return detail


def get_capability(connection: sqlite3.Connection, name: str) -> Capability:
    row = connection.execute(
        "SELECT name, status, evidence_json, checked_at FROM capability WHERE name = ?",
        (name,),
    ).fetchone()
    if row is None:
        return Capability(
            name=name, status=CapabilityStatus.UNTESTED, evidence={}, checked_at=None
        )
    return Capability(
        name=str(row["name"]),
        status=CapabilityStatus(str(row["status"])),
        evidence=json.loads(str(row["evidence_json"])),
        checked_at=row["checked_at"],
    )


def record_capability(
    connection: sqlite3.Connection,
    name: str,
    status: CapabilityStatus,
    evidence: dict[str, Any],
) -> None:
    """Store what a probe actually saw. Evidence is mandatory for a verdict.

    A ``verified`` or ``unavailable`` row without evidence would be an assertion,
    not a measurement — exactly what this project refuses elsewhere.
    """
    if status is not CapabilityStatus.UNTESTED and not evidence:
        raise ValueError(
            f"recording '{status.value}' for {name} requires evidence of the probe"
        )
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO capability(name, status, evidence_json, checked_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                status = excluded.status,
                evidence_json = excluded.evidence_json,
                checked_at = excluded.checked_at
            """,
            (name, status.value, json.dumps(evidence, sort_keys=True), utc_now()),
        )


def evaluate_probe(outcomes: list[dict[str, Any]]) -> tuple[CapabilityStatus, dict[str, Any]]:
    """Judge a completed batch probe from its recorded outcomes.

    Verified means: at least two recipients in ONE request, each with its own
    run id, each reaching a terminal status. One call proving itself is what
    mono already does — a batch probe with one recipient proves nothing new.
    """
    if len(outcomes) < 2:
        return CapabilityStatus.UNAVAILABLE, {
            "probe": outcomes,
            "verdict_basis": "fewer than two recipients in the probe; batch not shown",
        }
    run_ids = [o.get("run_id") for o in outcomes]
    terminal = [bool(o.get("terminal")) for o in outcomes]
    if None in run_ids or len(set(run_ids)) != len(run_ids):
        return CapabilityStatus.UNAVAILABLE, {
            "probe": outcomes,
            "verdict_basis": "recipients did not receive distinct run ids",
        }
    if not all(terminal):
        return CapabilityStatus.UNAVAILABLE, {
            "probe": outcomes,
            "verdict_basis": "not every recipient reached a terminal status",
        }
    return CapabilityStatus.VERIFIED, {
        "probe": outcomes,
        "verdict_basis": "distinct run ids, all terminal, in one batch request",
    }


def resolve_dispatch(
    connection: sqlite3.Connection,
    requested: DispatchMode,
    client: Any,
) -> DispatchDecision:
    """The availability-first decision, in the order the reasons matter.

    Mono needs no permission. Multi needs a verified probe AND a transport that
    actually has a batch path — the fixture client has one for testing the
    machinery, the live client only gains one once the probe exists.
    """
    if requested is DispatchMode.MONO:
        return DispatchDecision(mode=DispatchMode.MONO, requested=requested)

    capability = get_capability(connection, MULTI_CALL)
    if capability.status is not CapabilityStatus.VERIFIED:
        return DispatchDecision(
            mode=DispatchMode.MONO,
            requested=requested,
            downgrade_reason=(
                f"multi-call is {capability.status.value}; the serial path is the "
                f"one this installation has proven"
            ),
        )
    if not hasattr(client, "call_batch"):
        return DispatchDecision(
            mode=DispatchMode.MONO,
            requested=requested,
            downgrade_reason="the transport in use offers no batch path",
        )
    return DispatchDecision(mode=DispatchMode.MULTI, requested=requested)
