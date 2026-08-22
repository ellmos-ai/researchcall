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
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, Translator


#: The natural-language example content, one table per interface language.
#:
#: RC1 (Endabnahme 2026-08-22): switching the workbench to German left the
#: example study's text in English — there was only ever one table, and it
#: was English. A field is translated here only when its VALUE is what a
#: person reads or hears: the free-text question, hypothesis, item wording,
#: ethics text and the pretest's syntactic marker. Everything else — file
#: paths (``sample.source``, ``fieldwork.path``, ``reporting.findings_file``),
#: numbers, an e-mail address, and a ``type: choice`` field's stored VALUE
#: (``questionnaire.order``, ``reporting.journal_format``,
#: ``publication.target`` — the value is an internal key; its LABEL is
#: already localized by the form definition itself, see
#: ``pipeline/_shared/forms/``) is machine-facing and stays identical in
#: both tables on purpose: translating a file name or an enum key would not
#: fix anything a visitor can see, only risk breaking what reads it.
#:
#: Item and hypothesis lines keep the pipeline's own bilingual DSL (see
#: ``instrument.FORMATS``, e.g. "dichotom" alongside "dichotomous") rather
#: than a second, ad hoc translation scheme.
#:
#: ``pretest.instrument_check.syntactic_marker`` must stay deliberately
#: awkward in both languages — that is the field's entire purpose (see its
#: form definition: "which deliberately clumsy sentence reveals whether the
#: model rephrases the wording?"). The German line is not a smoothed-out
#: translation; it keeps the same kind of odd word order on purpose.
EXAMPLE_OVERRIDES: dict[str, dict[str, Any]] = {
    "en": {
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
        "ethics.greeting": [
            "Good afternoon",
            "Thank you for considering the demonstration",
        ],
        "ethics.closing": [
            "Thank you for your time",
            "Do you have a question about the study?",
        ],
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
    },
    "de": {
        "question": (
            "Wie wirkt sich die Taktfrequenz des lokalen Busverkehrs darauf aus, "
            "ob Anwohnerinnen und Anwohner den öffentlichen Nahverkehr nutzen?"
        ),
        "hypotheses": [
            "H1 | Ein dichterer Takt erhöht die regelmäßige Busnutzung | I1 | "
            "Kein Unterschied zwischen den Taktfrequenz-Gruppen"
        ],
        "questionnaire.order": "fixed",
        "questionnaire.jump_rules": [],
        "items": [
            'I1 | H1 | dichotom | "Nutzen Sie den Bus normalerweise für Ihren Arbeitsweg?"'
        ],
        "ethics.instruction": (
            "Dies ist ein automatisierter Forschungsanruf für eine reine "
            "Fixture-Demonstration einer lokalen Verkehrsstudie."
        ),
        "ethics.privacy_text": (
            "Antworten werden unter Fixture-IDs gespeichert, die Demonstration "
            "verwendet keine echten Personen, und jeder Testdatensatz kann "
            "lokal entfernt werden."
        ),
        "ethics.number_origin": "Erzeugter Fixture-Stichprobenrahmen",
        "ethics.greeting": [
            "Guten Tag",
            "Vielen Dank, dass Sie sich die Demonstration ansehen",
        ],
        "ethics.closing": [
            "Vielen Dank für Ihre Zeit",
            "Haben Sie eine Frage zur Studie?",
        ],
        "ethics.policies": ["Nur Fixture-Demonstration; keine zusätzliche Richtliniendatei"],
        "sample.source": "fixtures/example-frame.csv",
        "sample.size": 9,
        "pretest.send_to_reviewers": ["reviewer-a@example.invalid"],
        "pretest.call_reviewers": ["Eingewiesene Fixture-Teilnehmerin A"],
        "pretest.instrument_check.calls": 8,
        "pretest.instrument_check.syntactic_marker": (
            "Würden Sie sagen, dass Sie, der Bus, oft benutzen?"
        ),
        "fieldwork.path": "./out/test-mode",
        "reporting.findings_file": "TEST-FINDINGS.md",
        "reporting.journal_format": "interdisciplinary",
        "publication.target": "none",
    },
}

# Every served language must have a table, and every table must offer the
# same fields — a language missing one silently falls back to its default,
# which would look like the untranslated bug all over again, only harder to
# notice.
assert set(EXAMPLE_OVERRIDES) >= set(LANGUAGES), "EXAMPLE_OVERRIDES is missing a served language"
assert {frozenset(table) for table in EXAMPLE_OVERRIDES.values()} == {
    frozenset(EXAMPLE_OVERRIDES[DEFAULT_LANGUAGE])
}, "EXAMPLE_OVERRIDES tables must declare exactly the same fields in every language"


def example_values(
    fields: Iterable[forms.Field], language: str = DEFAULT_LANGUAGE
) -> dict[str, Any]:
    """Return one isolated example value for every visible declared field.

    ``language`` selects which of :data:`EXAMPLE_OVERRIDES` is read; an
    unknown code falls back to :data:`DEFAULT_LANGUAGE`, the same rule
    :func:`researchcall.web.i18n.normalize` uses for interface text.
    """
    overrides = EXAMPLE_OVERRIDES.get(language, EXAMPLE_OVERRIDES[DEFAULT_LANGUAGE])
    fields = list(fields)
    declared = {field.path for field in fields}
    locked = {field.path for field in fields if field.locked}
    unknown = set(overrides) - declared
    protected = set(overrides) & locked
    if unknown or protected:
        details = ", ".join(sorted(unknown | protected))
        raise ValueError(f"invalid test-mode example fields: {details}")

    return {
        field.path: copy.deepcopy(overrides.get(field.path, field.default))
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
