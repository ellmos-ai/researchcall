"""The instrument check: a study about the instrument, before the study.

Station 5 asks for something no other tool in this field does — dial a number of
test interviews and measure *how closely the agent kept to the instrument*. The
question is not academic. A model that smooths a clumsy sentence, reorders items
or adds a helpful probe destroys comparability without ever failing.

What this module can and cannot establish is stated in its own result, not in a
footnote somebody may skip:

* it measures what the **harness** returns, because the dry run has no agent;
* the fixture is built to deviate on purpose in some records, so a check that
  reports a hundred percent everywhere would itself be broken;
* the two criteria that need a real conversation — unplanned follow-ups, and the
  order the agent actually spoke in — are reported as *not measurable here*
  rather than as a passing score.

The syntactic marker is the sharpest of the criteria. A deliberately awkward
sentence is exactly what a language model wants to repair; if it comes back
untouched, verbatim delivery is real. Measured against the live service once
(FINDINGS.md §4), a quoted sentence survived down to an intentional typo.
"""

from __future__ import annotations

import pathlib
from collections import Counter
from typing import Any

from .calls import FixtureCallClient
from .instrument import for_call
from .questionnaire import normalize_structured_result, validate_structured_result


MARKER_ID = "marker"

#: Criteria a dry run cannot decide. Naming them beats scoring them.
NOT_MEASURABLE_OFFLINE = {
    "unplanned_follow_ups": (
        "Needs a transcript of a real conversation; the fixture transport has none."
    ),
    "order_kept": (
        "The structured result carries no order. What the instrument prescribed is "
        "measured below; whether the agent kept it needs a live transcript."
    ),
}

#: What each measured criterion actually says. Collected here rather than written
#: into the result so that the interface can find and translate them.
NOTES = {
    "asked_verbatim": "The agent's own report. It is a claim, not evidence.",
    "spoken_wording": "Returned wording compared with the required wording, item by item.",
    "ethics_blocks_complete": (
        "Consent sentence spoken word for word. Opening blocks are not part of the "
        "result schema and cannot be checked from it."
    ),
    "filters_respected": "A filtered item was asked exactly when its condition held.",
    "marker": "A deliberately clumsy sentence. Smoothing it out is the tell.",
    "order": "Distinct item orders the instrument produced across the test calls.",
}

HONEST_NOTE = (
    "This measures the local harness, not the CALL-E agent. A dry run can show that "
    "the instrument is enforced and audited; only a live call can show whether the "
    "agent speaks it."
)


def marker_item(marker: str) -> dict[str, Any]:
    """The clumsy sentence as an extra item, asked word for word."""
    return {
        "id": MARKER_ID,
        "wording": marker.strip(),
        "categories": ["heard", "unclear"],
        "format": "dichotomous",
        "verbatim": True,
        "hypothesis": "instrument fidelity",
    }


def check(
    questionnaire: dict[str, Any],
    calls: int,
    fixture: str | pathlib.Path,
    marker: str = "",
) -> dict[str, Any]:
    """Run ``calls`` dry-run interviews and measure how faithful they were.

    Nothing is written anywhere. The check is an experiment *about* the
    instrument, and its records must never end up in the survey's dataset.
    """
    calls = max(1, int(calls))
    tested = dict(questionnaire)
    tested["questions"] = list(questionnaire.get("questions", []))
    if marker.strip():
        tested["questions"] = tested["questions"] + [marker_item(marker)]

    binding = {
        question["id"]: question["wording"]
        for question in tested["questions"]
        if question.get("verbatim", True)
    }
    free = [
        question["id"]
        for question in tested["questions"]
        if not question.get("verbatim", True)
    ]

    client = FixtureCallClient.from_file(fixture)
    orders: set[tuple[str, ...]] = set()
    statuses: Counter[str] = Counter()
    interviews = 0
    verbatim_reported = 0
    wording_identical = 0
    marker_intact = 0
    marker_asked = 0
    consent_spoken = 0
    filtered_correctly = 0
    filtered_total = 0
    invalid = 0

    for sample_id in range(1, calls + 1):
        asked = for_call(tested, sample_id)
        orders.add(tuple(question["id"] for question in asked["questions"]))
        outcome = client.call({"sample_id": sample_id}, asked, f"pretest-{sample_id}")
        statuses[outcome.status] += 1
        result = outcome.structured_result
        if result is None:
            continue
        result = normalize_structured_result(tested, result)
        try:
            validate_structured_result(tested, result)
        except ValueError:
            invalid += 1
            continue
        if result["consent"] != "granted":
            continue
        interviews += 1
        if result["asked_verbatim"]:
            verbatim_reported += 1
        if result["spoken_consent_wording"] == tested["consent_text"]:
            consent_spoken += 1

        spoken = result["spoken_wording"]
        deviations = [
            question_id
            for question_id, wording in binding.items()
            if spoken.get(question_id) is not None and spoken[question_id] != wording
        ]
        if not deviations:
            wording_identical += 1
        if MARKER_ID in binding and spoken.get(MARKER_ID) is not None:
            marker_asked += 1
            if spoken[MARKER_ID] == binding[MARKER_ID]:
                marker_intact += 1

        for question in tested["questions"]:
            condition = question.get("ask_if")
            if not isinstance(condition, dict):
                continue
            filtered_total += 1
            equals = condition["equals"]
            allowed = [equals] if isinstance(equals, str) else list(equals)
            source = result["answers"].get(condition["question"])
            should_ask = source in allowed
            was_asked = spoken.get(question["id"]) is not None
            if should_ask == was_asked:
                filtered_correctly += 1

    return {
        "calls": calls,
        "interviews": interviews,
        "invalid_results": invalid,
        "statuses": dict(sorted(statuses.items())),
        "measured": {
            "asked_verbatim": {
                "of": interviews,
                "value": verbatim_reported,
                "note": NOTES["asked_verbatim"],
            },
            "spoken_wording": {
                "of": interviews,
                "value": wording_identical,
                "note": NOTES["spoken_wording"],
            },
            "ethics_blocks_complete": {
                "of": interviews,
                "value": consent_spoken,
                "note": NOTES["ethics_blocks_complete"],
            },
            "filters_respected": {
                "of": filtered_total,
                "value": filtered_correctly,
                "note": NOTES["filters_respected"],
            },
        },
        "marker": {
            "used": bool(marker.strip()),
            "asked": marker_asked,
            "intact": marker_intact,
            "note": NOTES["marker"],
        },
        "order": {
            "mode": tested.get("order", "fixed"),
            "distinct_orders": len(orders),
            "note": NOTES["order"],
        },
        "free_items": free,
        "not_measurable": dict(NOT_MEASURABLE_OFFLINE),
        "transport": "fixture",
        "honest_note": HONEST_NOTE,
    }


def summarize(result: dict[str, Any]) -> list[str]:
    """The check as readable lines, for the report and for a file."""
    lines = [
        "# Instrument check (dry run)",
        "",
        f"- Test interviews attempted: {result['calls']}",
        f"- Interviews with consent granted: {result['interviews']}",
        f"- Results the schema rejected: {result['invalid_results']}",
        "",
    ]
    for name, entry in result["measured"].items():
        share = "n/a" if not entry["of"] else f"{100 * entry['value'] / entry['of']:.1f}%"
        lines.append(f"- {name}: {entry['value']} of {entry['of']} ({share}) — {entry['note']}")
    marker = result["marker"]
    if marker["used"]:
        lines.append(
            f"- syntactic marker: asked {marker['asked']} times, returned untouched "
            f"{marker['intact']} times — {marker['note']}"
        )
    else:
        lines.append("- syntactic marker: none set, so the sharpest criterion is unused.")
    order = result["order"]
    lines.append(
        f"- item order ({order['mode']}): {order['distinct_orders']} distinct orders — {order['note']}"
    )
    lines.extend(["", "## Not measurable in a dry run", ""])
    for name, note in result["not_measurable"].items():
        lines.append(f"- {name}: {note}")
    lines.extend(["", result["honest_note"], ""])
    return lines
