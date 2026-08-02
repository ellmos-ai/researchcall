"""A clearly labelled, fixture-only tour through all eight stations.

Test mode relaxes presentation order, not the research frame. It supplies a
coherent example study for the visible form fields and never supplies, exposes,
or changes a locked field. The web application still has no live-call route.
"""

from __future__ import annotations

import copy
import html
import urllib.parse
from typing import Any, Iterable

from .. import forms
from .i18n import Translator


EXAMPLE_OVERRIDES: dict[str, Any] = {
    "question": (
        "How does the frequency of local bus service affect whether residents "
        "choose public transport?"
    ),
    "hypotheses": [
        "H1 | More frequent service raises regular bus use | I1 | "
        "No difference between service-frequency groups"
    ],
    "questionnaire.order": "fixed",
    "questionnaire.jump_rules": [],
    "items": [
        'I1 | H1 | dichotomous | "Do you usually use the bus for your commute?"'
    ],
    "ethics.instruction": (
        "This is an automated research call for a fixture-only demonstration "
        "of a local transport study."
    ),
    "ethics.privacy_text": (
        "Answers are stored under fixture IDs, the demonstration uses no real "
        "people, and any test record can be removed locally."
    ),
    "ethics.number_origin": "Generated fixture sampling frame",
    "ethics.greeting": ["Good afternoon", "Thank you for considering the demonstration"],
    "ethics.closing": ["Thank you for your time", "Do you have a question about the study?"],
    "ethics.policies": ["Fixture demonstration only; no additional policy file"],
    "sample.source": "fixtures/example-frame.csv",
    "sample.size": 9,
    "pretest.send_to_reviewers": ["reviewer-a@example.invalid"],
    "pretest.call_reviewers": ["Briefed fixture participant A"],
    "pretest.instrument_check.calls": 8,
    "pretest.instrument_check.syntactic_marker": (
        "Would you say that you, the bus, use often?"
    ),
    "fieldwork.path": "./out/test-mode",
    "reporting.findings_file": "TEST-FINDINGS.md",
    "reporting.journal_format": "interdisciplinary",
    "publication.target": "none",
}


def example_values(fields: Iterable[forms.Field]) -> dict[str, Any]:
    """Return one isolated example value for every visible declared field."""
    fields = list(fields)
    declared = {field.path for field in fields}
    locked = {field.path for field in fields if field.locked}
    unknown = set(EXAMPLE_OVERRIDES) - declared
    protected = set(EXAMPLE_OVERRIDES) & locked
    if unknown or protected:
        details = ", ".join(sorted(unknown | protected))
        raise ValueError(f"invalid test-mode example fields: {details}")

    return {
        field.path: copy.deepcopy(EXAMPLE_OVERRIDES.get(field.path, field.default))
        for field in fields
        if not field.locked
    }


def safe_return_path(path: str | None) -> str:
    """Keep the toggle redirect inside the local workbench."""
    candidate = str(path or "/")
    exact = {"/", "/config", "/instrument", "/pretest", "/fieldwork", "/report"}
    if candidate in exact:
        return candidate
    if candidate.startswith("/station/") and candidate.count("/") == 2:
        return candidate
    return "/"


def banner(active: bool, translator: Translator, return_to: str) -> str:
    """Render the visible mode switch without adding a research-form field."""
    language = html.escape(translator.language, quote=True)
    target = urllib.parse.quote(safe_return_path(return_to), safe="")
    action = f"/test-mode/toggle?lang={language}&next={target}"
    if active:
        title = translator.t("Test mode — example data, not a real study")
        detail = translator.t("All eight stations are open. Ethical locked settings stay hidden. Network disabled · fixture transport · no real calls.")
        button = translator.t("Leave test mode")
        colors = "background:#fff3cd;border-color:#9a6700;color:#3d2b00"
        state = "active"
    else:
        title = translator.t("Test mode is off")
        detail = translator.t(
            "Enable a separate example workspace to inspect all eight stations in any order."
        )
        button = translator.t("Enable test mode")
        colors = "background:#eef4f8;border-color:#8aa1b1;color:#243541"
        state = "off"

    return (
        f'<section data-test-mode="{state}" role="status" '
        f'style="{colors};border-style:solid;border-width:0 0 2px 0;'
        'padding:.75rem 1rem;display:flex;gap:1rem;align-items:center;'
        'justify-content:space-between;flex-wrap:wrap">'
        f'<div><strong>{html.escape(title)}</strong>'
        f'<div style="font-size:.9rem;margin-top:.2rem">{html.escape(detail)}</div></div>'
        f'<form method="post" action="{html.escape(action, quote=True)}">'
        f'<button type="submit">{html.escape(button)}</button></form></section>'
    )
