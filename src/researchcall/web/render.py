"""HTML for the workbench.

Plain functions returning strings. No template engine, no build step — the same
reason the rest of the tool has no runtime dependencies.

Two rules run through everything here:

* **No control is invented.** Every input on a station page comes from
  ``forms.form(fields, station, language)``. A setting that is not written down
  in a form definition cannot appear.
* **Locked settings show nothing at all** — not a disabled box, not a note.
  ``as_form_field()`` already returns ``None`` for them, so there is nothing to
  render. Consent and the right to stop are part of the frame, not a choice.
"""

from __future__ import annotations

import html
from typing import Any, Iterable

from .. import effect, forms
from .i18n import LANGUAGE_NAMES, Translator
from .workspace import STATIONS, Workspace


#: What each class of setting is called on screen. The keys are English source
#: strings, like every other piece of interface text.
EFFECT_LABELS = {
    effect.SCRIPT: "shapes the call",
    effect.RUN: "steers the run",
    effect.ANALYSIS: "shapes the analysis",
    effect.FRAME: "part of the frame",
    effect.DECLARED: "recorded only",
}

STATION_TITLES = {
    "01-research-question": "Research question",
    "02-instrument": "Instrument",
    "03-ethics": "Conversation and ethics frame",
    "04-sampling": "Sampling",
    "05-pretest": "Pretest",
    "06-fieldwork": "Fieldwork",
    "07-analysis": "Analysis",
    "08-reporting": "Reporting",
}

# Stations where the exact wording is spoken on the phone. The note is a measured
# finding (FINDINGS.md), not a property invented for a field.
WORDING_NOTE_STATIONS = {"02-instrument", "03-ethics"}


def e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


# The brand mark: a sheet holding a measured distribution — an instrument, not
# a chat window. Same shape as logo.svg, banner.png and the video thumbnail,
# generated from _calle-videos/_assets/logos/logos.py, so the workbench cannot
# drift away from the artwork. Inline, because the workbench has to render with
# no network and no build step.
BRAND_MARK = (
    '<svg class="brand-mark" xmlns="http://www.w3.org/2000/svg" '
    'viewBox="0 0 100 100" aria-hidden="true" focusable="false">'
    '<rect x="12.5" y="7" width="75" height="86" rx="14" fill="none" '
    'stroke="#38BDF8" stroke-width="8.5"/>'
    '<rect x="29" y="51" width="10" height="23" rx="5" fill="#38BDF8"/>'
    '<rect x="45" y="31" width="10" height="43" rx="5" fill="#38BDF8"/>'
    '<rect x="61" y="43" width="10" height="31" rx="5" fill="#64748B"/>'
    "</svg>"
)

# The same mark on the brand plate, as a data URI: a tab icon that costs no
# request and cannot 404.
FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E"
    "%3Crect width='512' height='512' rx='106' fill='%230B0F19'/%3E"
    "%3Cg transform='translate(97.28 97.28) scale(3.17)'%3E"
    "%3Crect x='12.5' y='7' width='75' height='86' rx='14' fill='none' "
    "stroke='%2338BDF8' stroke-width='8.5'/%3E"
    "%3Crect x='29' y='51' width='10' height='23' rx='5' fill='%2338BDF8'/%3E"
    "%3Crect x='45' y='31' width='10' height='43' rx='5' fill='%2338BDF8'/%3E"
    "%3Crect x='61' y='43' width='10' height='31' rx='5' fill='%2364748B'/%3E"
    "%3C/g%3E%3C/svg%3E"
)


STYLE = """
:root {
  --paper: #edf2f7;
  --card: #ffffff;
  --ink: #0f172a;
  --muted: #64748b;
  --line: #cbd5e1;
  --accent: #0284c7;
  --accent-strong: #0369a1;
  --accent-soft: #f0f9ff;
  --rail: #0f172a;
  --rail-card: #1e293b;
  --rail-ink: #e2e8f0;
  --focus: #0284c7;
  --warn: #c2410c;
  --warn-soft: #fff7ed;
  --ok: #15803d;
  --shadow-sm: 0 1px 2px 0 rgba(15, 23, 42, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.05);
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 14.5px/1.55 "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
  letter-spacing: -0.005em;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }
a:hover { color: #0369a1; }
code, .mono { font-family: "JetBrains Mono", "Cascadia Code", "SF Mono", Consolas, monospace; font-size: .84em; }

header.top {
  display: flex; flex-wrap: wrap; gap: 1rem; align-items: center;
  min-height: 56px; padding: .75rem 1.4rem; border-bottom: 1px solid #1e293b;
  background: #0b0f19; color: #f8fafc; position: sticky; top: 0; z-index: 20;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
header.top h1 {
  font-size: 1.12rem; margin: 0; letter-spacing: -.01em; font-weight: 700;
  color: #38bdf8; display: flex; align-items: center; gap: .4rem;
}
header.top .brand-mark { width: 26px; height: 26px; flex: none; display: block; }
header.top .brand-icon { font-size: 1.1rem; }
header.top .tag {
  color: #94a3b8; font-size: .78rem; font-weight: 500;
  padding: .2rem .6rem; background: rgba(255,255,255,0.05); border-radius: 4px;
  border: 1px solid rgba(255,255,255,0.08); letter-spacing: 0.01em;
}
header.top nav { margin-left: auto; display: flex; gap: .75rem; align-items: center; }
.lang a {
  text-decoration: none; border: 1px solid rgba(255,255,255,0.18); border-radius: 4px;
  padding: .22rem .7rem; font-size: .78rem; color: #e2e8f0; font-weight: 600;
  background: rgba(255,255,255,0.04); transition: all .15s ease;
}
.lang a:hover {
  background: rgba(56, 189, 248, 0.15); border-color: rgba(56, 189, 248, 0.5); color: #38bdf8;
}

.shell { display: grid; grid-template-columns: minmax(230px, 265px) 1fr; min-height: calc(100vh - 56px); }

nav.rail {
  border-right: 1px solid #1e293b; padding: 1.1rem .85rem; background: var(--rail);
  color: var(--rail-ink); position: sticky; top: 56px; height: calc(100vh - 56px);
  overflow-y: auto; align-self: start;
}
nav.rail .rail-summary {
  border-bottom: 1px solid #1e293b; margin: 0 .2rem .9rem; padding-bottom: .75rem;
  color: #94a3b8; font-size: .7rem; letter-spacing: .06em; text-transform: uppercase; font-weight: 700;
}
nav.rail ol { list-style: none; margin: 0; padding: 0; }
nav.rail li { margin: 0 0 .25rem; }
nav.rail a, nav.rail span.locked {
  display: flex; align-items: center; justify-content: space-between;
  padding: .5rem .7rem; border-radius: 5px; text-decoration: none;
  color: var(--rail-ink); font-size: .86rem; transition: background .12s ease, color .12s ease;
}
nav.rail a:hover { background: var(--rail-card); color: #ffffff; }
nav.rail a.current {
  background: #1e293b; color: #38bdf8; font-weight: 600;
  box-shadow: inset 3px 0 0 #38bdf8;
}
nav.rail span.locked { color: #475569; cursor: not-allowed; }
nav.rail .num { color: #64748b; font-size: .74rem; margin-right: .5rem; font-variant-numeric: tabular-nums; font-weight: 600; }
nav.rail .mark { font-size: .85rem; font-weight: bold; margin-left: auto; }
nav.rail .done { color: #34d399; }
nav.rail .extra { border-top: 1px solid #1e293b; margin-top: 1rem; padding-top: .85rem; }

main { padding: 1.8rem 2.2rem 3.5rem; min-width: 0; width: 100%; max-width: 1420px; margin: 0 auto; }
h2 { font-size: 1.48rem; font-weight: 700; line-height: 1.25; margin: 0 0 .35rem; letter-spacing: -.015em; color: #0f172a; }
.sub { color: var(--muted); font-size: .85rem; margin: 0 0 1.25rem; line-height: 1.45; }

.split { display: grid; grid-template-columns: minmax(0, 1fr) minmax(290px, 370px); gap: 1.6rem; align-items: start; }
.config-stack { display: grid; grid-template-columns: minmax(0, 1fr); gap: 1.6rem; align-items: start; }
@media (max-width: 1100px) { .split { grid-template-columns: 1fr; } }

fieldset { border: none; margin: 0; padding: 0; }
.field {
  background: var(--card); border: 1px solid var(--line); border-radius: 6px;
  padding: .85rem 1.1rem; margin: 0 0 .75rem; box-shadow: var(--shadow-sm);
  transition: border-color .15s ease, box-shadow .15s ease;
}
.field:hover { border-color: #94a3b8; box-shadow: var(--shadow-md); }
.field > label.name {
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
  font-weight: 650; margin-bottom: .45rem; color: #0f172a; font-size: .93rem; gap: .35rem;
}
.field .req { color: var(--warn); font-weight: 700; }
.field .help { color: #475569; font-size: .83rem; margin: .45rem 0 0; line-height: 1.45; }
.field .path {
  color: #64748b; font-size: .72rem; font-weight: 500; background: #f1f5f9;
  padding: .1rem .45rem; border-radius: 4px; border: 1px solid #e2e8f0; margin-left: auto;
}
.field.amended { border-left: 4px solid #ea580c; }
.field .amended-mark {
  display: inline-block; background: var(--warn-soft); color: var(--warn);
  font-size: .7rem; font-weight: 600; padding: .1rem .5rem; border-radius: 999px; border: 1px solid #ffedd5;
}
input[type=text], input[type=number], textarea, select {
  width: 100%; padding: .48rem .6rem; border: 1px solid #94a3b8; border-radius: 5px;
  background: #ffffff; color: var(--ink); font: inherit; font-size: .92rem;
  transition: border-color .15s ease, box-shadow .15s ease;
}
input:focus, textarea:focus, select:focus {
  outline: none; border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.2);
}
textarea { min-height: 4.8rem; resize: vertical; line-height: 1.45; }
.choices { display: flex; flex-wrap: wrap; gap: .4rem .95rem; padding: .2rem 0; }
.choices label { font-size: .91rem; display: flex; gap: .4rem; align-items: center; color: #1e293b; }
.switch { display: flex; gap: .45rem; align-items: center; font-size: .92rem; }

button, .button {
  font: inherit; font-size: .88rem; font-weight: 600; padding: .52rem 1.1rem; border-radius: 5px;
  border: 1px solid var(--accent-strong); background: var(--accent-strong); color: #fff;
  cursor: pointer; text-decoration: none; display: inline-block; transition: all .15s ease;
  box-shadow: var(--shadow-sm);
}
button:hover, .button:hover { background: var(--accent); border-color: var(--accent); box-shadow: var(--shadow-md); }
button.quiet, .button.quiet { background: #f8fafc; border-color: #cbd5e1; color: var(--accent-strong); }
button.quiet:hover, .button.quiet:hover { background: #f1f5f9; border-color: var(--accent); color: var(--accent); }
.actions { display: flex; gap: .75rem; align-items: center; margin-top: 1.25rem; flex-wrap: wrap; }

aside .panel {
  background: var(--card); border: 1px solid var(--line); border-radius: 6px;
  padding: 1rem 1.15rem; margin-bottom: 1rem; box-shadow: var(--shadow-sm);
}
aside h3 {
  font-size: .74rem; text-transform: uppercase; letter-spacing: .07em;
  color: var(--muted); margin: 0 0 .65rem; font-weight: 700;
}
aside ol.asks { margin: 0; padding-left: 1.15rem; font-size: .9rem; line-height: 1.5; color: #334155; }
aside ol.asks li { margin-bottom: .45rem; }
aside .none { color: var(--muted); font-size: .88rem; margin: 0; line-height: 1.45; }
pre.config {
  margin: 0; white-space: pre-wrap; word-break: break-word;
  font-family: "JetBrains Mono", "SF Mono", Consolas, monospace; font-size: .8rem;
  color: var(--ink); max-height: 24rem; overflow: auto; line-height: 1.5;
}

.note {
  border-left: 4px solid var(--accent); background: var(--accent-soft);
  padding: .75rem 1rem; border-radius: 0 6px 6px 0; font-size: .86rem; margin: 0 0 1rem;
  color: #0c4a6e; line-height: 1.5; border-top: 1px solid #e0f2fe; border-right: 1px solid #e0f2fe; border-bottom: 1px solid #e0f2fe;
}
.note.warn {
  border-left-color: var(--warn); background: var(--warn-soft); color: #7c2d12;
  border-top: 1px solid #ffedd5; border-right: 1px solid #ffedd5; border-bottom: 1px solid #ffedd5;
}
.note.locked-note {
  border-left-color: var(--muted); background: transparent;
  border: 1px dashed var(--line); border-radius: 6px; color: var(--muted);
}

table.data { border-collapse: collapse; width: 100%; font-size: .88rem; }
table.data th, table.data td {
  border-bottom: 1px solid #e2e8f0; padding: .45rem .7rem; text-align: left;
}
table.data th {
  color: #475569; background: #f1f5f9; font-weight: 700; font-size: .72rem;
  text-transform: uppercase; letter-spacing: .05em; position: sticky; top: 0; z-index: 1;
  border-bottom: 2px solid #cbd5e1;
}
table.data td.n { text-align: right; font-variant-numeric: tabular-nums; }
.bar { height: .55rem; border-radius: 999px; background: var(--accent); display: block; min-width: 2px; }
.bar.loss { background: var(--warn); }
.scroll { overflow-x: auto; border-radius: 6px; border: 1px solid var(--line); background: var(--card); }

.counts { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: .7rem; margin: 0 0 1.25rem; }
.counts div {
  background: var(--card); border: 1px solid var(--line); border-radius: 6px;
  padding: .75rem .9rem; box-shadow: var(--shadow-sm);
}
.counts .big { display: block; font-size: 1.6rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.1; color: #0f172a; }
.counts .cap { color: var(--muted); font-size: .76rem; font-weight: 500; }
.log {
  font-family: "JetBrains Mono", "SF Mono", Consolas, monospace; font-size: .82rem;
  background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 6px;
  padding: .8rem 1rem; max-height: 22rem; overflow: auto; line-height: 1.6;
}
.log div { padding: .08rem 0; }
.log .st { color: #38bdf8; font-weight: 600; }

.eff {
  display: inline-block; font-size: .68rem; letter-spacing: .03em;
  text-transform: uppercase; padding: .12rem .55rem; border-radius: 999px;
  border: 1px solid #bae6fd; background: #e0f2fe; color: #0369a1;
  vertical-align: .1rem; font-weight: 600;
}
.eff-declared { border-color: #ffedd5; color: #c2410c; background: #fff7ed; }
.field.declared { border-left: 4px dashed #f59e0b; background: #fafaf9; }
.why { color: var(--muted); font-size: .78rem; margin: .4rem 0 0; font-style: italic; }
ul.plain { margin: .35rem 0 0; padding-left: 1.15rem; font-size: .88rem; line-height: 1.5; }
ul.plain li { margin-bottom: .3rem; }
pre.script {
  margin: 0; white-space: pre-wrap; word-break: break-word;
  font-family: "JetBrains Mono", "SF Mono", Consolas, monospace;
  font-size: .84rem; line-height: 1.55; max-height: 28rem; overflow: auto; color: #1e293b;
}
.problem { color: var(--warn); font-size: .85rem; font-weight: 600; }
@media (max-width: 860px) {
  .shell { grid-template-columns: 1fr; min-height: auto; }
  nav.rail { position: static; height: auto; border-right: 0; border-bottom: 1px solid #334155; padding: .55rem; overflow-x: auto; }
  nav.rail .rail-summary { display: none; }
  nav.rail ol { display: flex; gap: .25rem; min-width: max-content; }
  nav.rail li { margin: 0; }
  nav.rail .extra { border-top: 0; border-left: 1px solid #334155; margin: 0 0 0 .35rem; padding: 0 0 0 .55rem; }
  main { padding: 1.25rem 1rem 2.5rem; }
  .field > label.name { flex-direction: column; align-items: flex-start; }
  .field .path { margin-left: 0; }
}
"""


def page(title: str, body: str, translator: Translator, active: str = "") -> str:
    """The full document."""
    switch = " ".join(
        f'<a href="?lang={e(code)}" title="{e(name)}">{e(name)}</a>'
        for code, name in translator.other_languages()
    )
    return (
        "<!doctype html>"
        f'<html lang="{e(translator.language)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{e(title)} · ResearchCall</title>"
        f'<link rel="icon" href="{FAVICON}">'
        f"<style>{STYLE}</style>"
        '<script src="/static/htmx.min.js" defer></script>'
        '<script src="/static/huckepack.js" defer></script>'
        "</head><body>"
        f'<header class="top"><h1>{BRAND_MARK}ResearchCall</h1>'
        f'<span class="tag">{e(translator.t("Survey workbench · dry run · no calls"))}</span>'
        f'<nav><span class="lang">{switch}</span></nav></header>'
        f"{body}"
        "</body></html>"
    )


def rail(workspace: Workspace, translator: Translator, active: str) -> str:
    """The eight stations, in order, with the gate visible."""
    items = []
    for index, station in enumerate(STATIONS, start=1):
        title = translator.t(STATION_TITLES[station])
        done = station in workspace.completed
        mark = '<span class="mark done">✓</span>' if done else ""
        if workspace.is_open(station):
            css = "current" if station == active else ""
            items.append(
                f'<li><a class="{css}" href="/station/{e(station)}?lang={e(translator.language)}">'
                f'<span class="num">{index}</span>{e(title)}{mark}</a></li>'
            )
        else:
            items.append(
                f'<li><span class="locked" title="{e(translator.t("Finish the station before this one first."))}">'
                f'<span class="num">{index}</span>{e(title)} ·</span></li>'
            )
    extras = (
        f'<li class="extra"><a class="{"current" if active == "instrument" else ""}" '
        f'href="/instrument?lang={e(translator.language)}">{e(translator.t("The call, as written"))}</a></li>'
        f'<li><a class="{"current" if active == "pretest" else ""}" '
        f'href="/pretest?lang={e(translator.language)}">{e(translator.t("Instrument check"))}</a></li>'
        f'<li><a class="{"current" if active == "fieldwork" else ""}" '
        f'href="/fieldwork?lang={e(translator.language)}">{e(translator.t("Field phase"))}</a></li>'
        f'<li><a class="{"current" if active == "report" else ""}" '
        f'href="/report?lang={e(translator.language)}">{e(translator.t("Report"))}</a></li>'
        f'<li><a class="{"current" if active == "config" else ""}" '
        f'href="/config?lang={e(translator.language)}">{e(translator.t("Configuration"))}</a></li>'
    )
    progress = translator.t("{done} of 8 stations finished").replace(
        "{done}", str(len(workspace.completed))
    )
    return (
        f'<nav class="rail"><div class="rail-summary">{e(progress)}</div>'
        f'<ol>{"".join(items)}{extras}</ol></nav>'
    )


# --- one control per field ----------------------------------------------------

def control(descriptor: dict[str, Any], value: Any) -> str:
    """The input for one field descriptor, chosen by its declared type."""
    name = e(descriptor["name"])
    kind = descriptor["type"]
    required = " required" if descriptor.get("required") else ""

    if kind == "bool":
        checked = " checked" if bool(value) else ""
        return (
            f'<span class="switch"><input type="checkbox" id="{name}" '
            f'name="{name}" value="on"{checked}></span>'
        )
    if kind == "number":
        shown = "" if value is None else e(value)
        return f'<input type="number" step="any" id="{name}" name="{name}" value="{shown}"{required}>'
    if kind == "longtext":
        return f'<textarea id="{name}" name="{name}"{required}>{e(value or "")}</textarea>'
    if kind in {"list", "table"}:
        lines = "\n".join(str(item) for item in value) if isinstance(value, list) else e(value or "")
        return f'<textarea id="{name}" name="{name}"{required}>{e(lines)}</textarea>'
    if kind == "choice":
        options = []
        for option in descriptor.get("options", []):
            selected = " selected" if str(value) == str(option["value"]) else ""
            options.append(
                f'<option value="{e(option["value"])}"{selected}>{e(option["label"])}</option>'
            )
        return f'<select id="{name}" name="{name}"{required}>{"".join(options)}</select>'
    if kind == "multi":
        chosen = {str(item) for item in (value or [])} if isinstance(value, (list, tuple)) else set()
        boxes = []
        for option in descriptor.get("options", []):
            checked = " checked" if str(option["value"]) in chosen else ""
            boxes.append(
                f'<label><input type="checkbox" name="{name}" '
                f'value="{e(option["value"])}"{checked}>{e(option["label"])}</label>'
            )
        return f'<div class="choices">{"".join(boxes)}</div>'
    shown = "" if value is None else e(value)
    return f'<input type="text" id="{name}" name="{name}" value="{shown}"{required}>'


def effect_badge(path: str, translator: Translator) -> str:
    """Where this setting acts — or that it does not act yet.

    A control that changes nothing looks exactly like one that changes
    everything. The badge is the only thing that tells them apart, so it is
    attached to the control rather than mentioned in a document.
    """
    name = effect.effect_of(path)
    label = translator.t(EFFECT_LABELS[name])
    css = " eff-declared" if name == effect.DECLARED else ""
    return f'<span class="eff{css}">{e(label)}</span>'


def field_block(
    descriptor: dict[str, Any],
    value: Any,
    translator: Translator,
    amended: bool = False,
) -> str:
    path = descriptor["name"]
    declared = not effect.is_effective(path)
    mark = (
        f'<span class="amended-mark">{e(translator.t("added later"))}</span>'
        if amended
        else ""
    )
    required = (
        f' <span class="req" title="{e(translator.t("Required"))}">*</span>'
        if descriptor.get("required")
        else ""
    )
    help_text = (
        f'<p class="help">{e(descriptor["help"])}</p>' if descriptor.get("help") else ""
    )
    why = (
        f'<p class="why">{e(translator.t("Nothing reads this value yet:"))} '
        f'{e(translator.t(effect.reason_of(path)))}</p>'
        if declared
        else f'<p class="why">{e(translator.t(effect.reason_of(path)))}</p>'
    )
    classes = "field"
    if amended:
        classes += " amended"
    if declared:
        classes += " declared"
    return (
        f'<div class="{classes}">'
        f'<label class="name" for="{e(path)}">'
        f'<span class="path mono">{e(path)}</span>'
        f'{e(descriptor["label"])}{required}{mark}'
        f"{effect_badge(path, translator)}</label>"
        f"{control(descriptor, value)}{help_text}{why}</div>"
    )


# --- the station page ---------------------------------------------------------

def station_view(
    station: str,
    fields: list[forms.Field],
    workspace: Workspace,
    translator: Translator,
    message: str = "",
    missing: Iterable[str] = (),
    panels: str = "",
) -> str:
    language = translator.language
    descriptors = forms.form(fields, station, language)
    amended = workspace.amended_fields(station)
    by_path = {field.path: field for field in fields}

    blocks = "".join(
        field_block(
            descriptor,
            workspace.value(by_path[descriptor["name"]]),
            translator,
            descriptor["name"] in amended,
        )
        for descriptor in descriptors
    )

    notes = []
    if station in WORDING_NOTE_STATIONS:
        notes.append(
            f'<p class="note">{e(translator.t("Text in double quotes is spoken word for word. Everything outside the quotes is rephrased by the agent — a behaviour measured in a real call."))}</p>'
        )
    missing = list(missing)
    if missing:
        notes.append(
            f'<p class="note warn">{e(translator.t("Still missing before this station can be finished:"))} '
            f'<span class="mono">{e(", ".join(missing))}</span></p>'
        )
    if message:
        notes.append(f'<p class="note">{e(message)}</p>')
    if station in workspace.completed:
        notes.append(
            f'<p class="note">{e(translator.t("Finished on"))} '
            f'{e(workspace.completed[station])} · '
            f'{e(translator.t("later changes stay possible and are marked as later additions."))}</p>'
        )

    asks = forms.interview(fields, station, language)
    ask_list = (
        "<ol class=\"asks\">" + "".join(f"<li>{e(item)}</li>" for item in asks) + "</ol>"
        if asks
        else f'<p class="none">{e(translator.t("Nothing — every value here has a default, so an agent would not ask."))}</p>'
    )

    index = STATIONS.index(station) + 1
    title = translator.t(STATION_TITLES[station])
    declared_here = effect.declared_only(fields, station)
    counts = translator.t("{visible} settings shown · an agent asks {asked} · {declared} are recorded without effect")
    counts = (
        counts.replace("{visible}", str(len(descriptors)))
        .replace("{asked}", str(len(asks)))
        .replace("{declared}", str(len(declared_here)))
    )
    if declared_here:
        notes.append(
            f'<p class="note warn">{e(translator.t("Some settings on this station are kept but not yet read by anything. They are marked, because a control that quietly changes nothing is worse than one that is missing."))}</p>'
        )

    body = (
        f'<main><h2>{index}. {e(title)}</h2>'
        f'<p class="sub">{e(counts)}</p>'
        f'{"".join(notes)}'
        '<div class="split"><section>'
        f'<form method="post" action="/station/{e(station)}?lang={e(language)}">'
        f"<fieldset>{blocks}</fieldset>"
        '<div class="actions">'
        f'<button type="submit" name="action" value="save">{e(translator.t("Save"))}</button>'
        f'<button type="submit" name="action" value="complete" class="quiet">'
        f'{e(translator.t("Save and finish station"))}</button>'
        "</div></form></section>"
        "<aside>"
        f"{panels}"
        f'<div class="panel"><h3>{e(translator.t("The same decisions, asked by an agent"))}</h3>{ask_list}</div>'
        f'<div class="panel"><h3>{e(translator.t("One definition, three ways in"))}</h3>'
        f'<p class="none">{e(translator.t("Every control on the left is rendered from a form definition under pipeline/_shared/forms/. The same definition produces the config value and the spoken question. The interface adds no field of its own."))}</p></div>'
        "</aside></div></main>"
    )
    return body


# --- the instrument -----------------------------------------------------------

def problem_list(problems: Iterable[Any], translator: Translator) -> str:
    problems = list(problems)
    if not problems:
        return ""
    rows = "".join(
        f'<li><span class="mono">{e(problem.text)}</span><br>'
        f'<span class="problem">{e(translator.t("line"))} {problem.line}: '
        f"{e(problem.message)}</span></li>"
        for problem in problems
    )
    return (
        f'<div class="panel"><h3>{e(translator.t("What could not be read"))}</h3>'
        f'<ul class="plain">{rows}</ul></div>'
    )


def instrument_panel(plan: dict[str, Any], translator: Translator) -> str:
    """The short version beside the form: how many items, how long, what broke."""
    body = (
        f'<p class="none">{e(translator.t("items"))}: <strong>{plan["questions"]}</strong> · '
        f'{e(translator.t("open"))}: <strong>{plan["open_questions"]}</strong><br>'
        f'{e(translator.t("announced duration"))}: <strong>{plan["minutes"]} '
        f'{e(translator.t("minutes"))}</strong><br>'
        f'{e(translator.t("item order"))}: <strong>{e(plan["order"])}</strong></p>'
        f'<p class="none"><a href="/instrument?lang={e(translator.language)}">'
        f'{e(translator.t("Read the call as it will be spoken"))}</a></p>'
    )
    if plan["problems"]:
        body += (
            f'<p class="problem">{len(plan["problems"])} '
            f'{e(translator.t("lines could not be read — the field phase will refuse to start."))}</p>'
        )
    return f'<div class="panel"><h3>{e(translator.t("The instrument so far"))}</h3>{body}</div>'


def instrument_view(
    plan: dict[str, Any],
    script: list[str],
    translator: Translator,
    downloadable: bool = True,
) -> str:
    """The whole call, in the order it is spoken, ready to be read or handed on."""
    questionnaire = plan["questionnaire"]
    rows = []
    for number, question in enumerate(questionnaire["questions"], start=1):
        condition = question.get("ask_if")
        filter_text = ""
        if condition:
            values = condition["equals"]
            values = [values] if isinstance(values, str) else list(values)
            filter_text = f'{e(condition["question"])} = {e(" / ".join(values))}'
        categories = ", ".join(question.get("categories") or []) or "—"
        rows.append(
            "<tr>"
            f'<td class="n">{number}</td>'
            f'<td class="mono">{e(question["id"])}</td>'
            f'<td>{e(question.get("format", ""))}</td>'
            f'<td>{e(translator.t("word for word")) if question.get("verbatim", True) else e(translator.t("freely phrased"))}</td>'
            f"<td>{e(categories)}</td>"
            f"<td>{filter_text}</td>"
            "</tr>"
        )
    table = (
        '<div class="scroll"><table class="data"><thead><tr>'
        f'<th></th><th>{e(translator.t("item"))}</th><th>{e(translator.t("format"))}</th>'
        f'<th>{e(translator.t("wording"))}</th><th>{e(translator.t("categories"))}</th>'
        f'<th>{e(translator.t("asked only if"))}</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        if rows
        else f'<p class="note warn">{e(translator.t("Station 2 carries no items yet, so there is nothing to ask."))}</p>'
    )
    return (
        f'<main><h2>{e(translator.t("The call, as written"))}</h2>'
        f'<p class="sub">{e(translator.t("Built from stations 1 to 4. Quoted lines are spoken word for word; everything else the agent phrases itself — a difference measured against the real service, not assumed."))}</p>'
        f'{problem_list(plan["problems"], translator)}'
        f"{table}"
        f'<h3>{e(translator.t("The spoken order"))}</h3>'
        f'<div class="panel"><pre class="script">{e(chr(10).join(script))}</pre></div>'
        + (
            f'<p class="sub"><a href="/instrument.md">{e(translator.t("Download as a document"))}</a> · '
            f'<a href="/instrument.task.txt">{e(translator.t("The task text an agent receives"))}</a></p>'
            if downloadable
            else f'<p class="sub">{e(translator.t("Handing the questionnaire around is switched off in station 5."))}</p>'
        )
        + "</main>"
    )


def pretest_view(
    result: dict[str, Any] | None,
    plan: dict[str, Any],
    translator: Translator,
    problem: str = "",
) -> str:
    """The instrument tested on itself, before a single real person is called."""
    language = translator.language
    intro = (
        f'<main><h2>{e(translator.t("Instrument check"))}</h2>'
        f'<p class="sub">{e(translator.t("A small study about the instrument: run the interview against the fixture transport and measure how faithfully it was delivered."))}</p>'
        f'<p class="note">{e(translator.t("This measures the local harness, not the CALL-E agent. A dry run can show that the instrument is enforced and audited; only a live call can show whether the agent speaks it."))}</p>'
    )
    if problem:
        return intro + f'<p class="note warn">{e(problem)}</p></main>'
    if plan["problems"]:
        return (
            intro
            + f'{problem_list(plan["problems"], translator)}</main>'
        )
    start = (
        f'<form hx-post="/pretest/run?lang={e(language)}" hx-target="#check" hx-swap="innerHTML">'
        f'<button type="submit">{e(translator.t("Run the check"))}</button>'
        "</form>"
    )
    return intro + start + f'<div id="check">{pretest_result(result, translator) if result else ""}</div></main>'


def pretest_result(result: dict[str, Any], translator: Translator) -> str:
    rows = []
    for name, entry in result["measured"].items():
        share = "n/a" if not entry["of"] else f"{100 * entry['value'] / entry['of']:.1f}%"
        rows.append(
            f'<tr><td class="mono">{e(name)}</td>'
            f'<td class="n">{entry["value"]} / {entry["of"]}</td>'
            f'<td class="n">{e(share)}</td>'
            f'<td>{e(translator.t(entry["note"]))}</td></tr>'
        )
    marker = result["marker"]
    if marker["used"]:
        rows.append(
            f'<tr><td class="mono">syntactic_marker</td>'
            f'<td class="n">{marker["intact"]} / {marker["asked"]}</td>'
            f'<td class="n">'
            + (
                f"{100 * marker['intact'] / marker['asked']:.1f}%"
                if marker["asked"]
                else "n/a"
            )
            + f'</td><td>{e(translator.t(marker["note"]))}</td></tr>'
        )
    order = result["order"]
    not_measurable = "".join(
        f'<li><span class="mono">{e(name)}</span> — {e(translator.t(note))}</li>'
        for name, note in result["not_measurable"].items()
    )
    return (
        f'<div class="counts" style="margin-top:1.4rem">'
        f'<div><span class="big">{result["calls"]}</span><span class="cap">'
        f'{e(translator.t("test interviews"))}</span></div>'
        f'<div><span class="big">{result["interviews"]}</span><span class="cap">'
        f'{e(translator.t("with consent"))}</span></div>'
        f'<div><span class="big">{order["distinct_orders"]}</span><span class="cap">'
        f'{e(translator.t("distinct item orders"))} ({e(order["mode"])})</span></div>'
        "</div>"
        '<div class="scroll"><table class="data"><thead><tr>'
        f'<th>{e(translator.t("criterion"))}</th><th>{e(translator.t("kept"))}</th>'
        f'<th>{e(translator.t("share"))}</th><th>{e(translator.t("what it means"))}</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        f'<h3>{e(translator.t("Not measurable in a dry run"))}</h3>'
        f'<ul class="plain">{not_measurable}</ul>'
        f'<p class="note warn">{e(translator.t(result["honest_note"]))}</p>'
    )


# --- field phase --------------------------------------------------------------

def fieldwork_view(
    plan: dict[str, Any],
    prepared: dict[str, int] | None,
    translator: Translator,
    ready: bool,
    problem: str = "",
) -> str:
    """Prepare and watch. There is no control here that could ring a telephone."""
    language = translator.language
    windows = ", ".join(plan["windows"]) or "—"
    facts = (
        f'<div class="counts">'
        f'<div><span class="big">{plan["size"]}</span><span class="cap">'
        f'{e(translator.t("sample size"))}</span></div>'
        f'<div><span class="big">{plan["questions"]}</span><span class="cap">'
        f'{e(translator.t("items"))} · {plan["minutes"]} {e(translator.t("minutes"))}</span></div>'
        f'<div><span class="big">{plan["attempts"]}</span><span class="cap">'
        f'{e(translator.t("attempts allowed per person"))}</span></div>'
        f'<div><span class="big">{plan["quota"]}</span><span class="cap">'
        f'{e(translator.t("daily quota"))}</span></div>'
        f'<div><span class="big">{len(plan["windows"])}</span><span class="cap">'
        f'{e(translator.t("time windows"))} · {e(windows)}</span></div>'
        "</div>"
    )
    if plan["attempts"] > 1:
        facts += (
            f'<p class="note warn">{e(translator.t("Repeated contact raises the yield and shifts the sample towards people who are reachable more often. The report states how many records it affected."))}</p>'
        )
    if plan["problems"]:
        facts = problem_list(plan["problems"], translator) + facts
    if problem:
        note = f'<p class="note warn">{e(problem)}</p>'
    else:
        note = ""
    drawn = ""
    if prepared:
        drawn = (
            f'<p class="note">{e(translator.t("Frame rows created:"))} {prepared["frame"]} · '
            f'{e(translator.t("drawn:"))} {prepared["drawn"]}</p>'
        )

    action_label = (
        translator.t("Continue prepared dry run")
        if ready
        else translator.t("Draw sample and start dry run")
    )
    start = (
        ""
        if plan["problems"] or problem
        else (
            f'<form hx-post="/fieldwork/prepare?lang={e(language)}" hx-target="#monitor" hx-swap="innerHTML">'
            f'<button type="submit">{e(action_label)}</button>'
            "</form>"
        )
    )
    # Merely opening this page is read-only. The EventSource, and therefore the
    # fixture run, appears only in the response to the explicit button above.
    monitor = ""

    return (
        f'<main><h2>{e(translator.t("Field phase"))}</h2>'
        f'<p class="sub">{e(translator.t("Dry run against fixtures. No network, no account, no call."))}</p>'
        f'<p class="note warn">{e(translator.t("This interface cannot place a real call. Only the command line can, and only after the intent is typed out in full."))}</p>'
        f"{note}{facts}{drawn}{start}"
        f'<div id="monitor">{monitor}</div></main>'
    )


def monitor_panel(translator: Translator) -> str:
    """The live view: a line per record, counts beside it."""
    return (
        '<div class="split" style="margin-top:1.4rem">'
        f'<section><h3 style="font-size:.82rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)">'
        f'{e(translator.t("Records"))}</h3>'
        '<div class="log" id="log"></div></section>'
        f'<aside><div class="panel"><h3>{e(translator.t("Outcomes so far"))}</h3>'
        '<div class="scroll"><table class="data" id="totals"><tbody></tbody></table></div>'
        f'<p class="none" id="progress">{e(translator.t("waiting…"))}</p>'
        f'<p class="none">{e(translator.t("NO_ANSWER is a time-of-day signal, DECLINED is refusal. They are never added together."))}</p>'
        "</div></aside></div>"
        "<script>"
        "(function(){"
        "var src=new EventSource('/fieldwork/stream');"
        "var log=document.getElementById('log');"
        "var totals=document.querySelector('#totals tbody');"
        "var progress=document.getElementById('progress');"
        "src.onmessage=function(ev){"
        "var d=JSON.parse(ev.data);"
        "if(d.done){progress.textContent=d.processed+' '+"
        f"{_js(translator.t('records processed'))}"
        ";src.close();return;}"
        "var line=document.createElement('div');"
        "line.innerHTML='<span class=\"st\">'+String(d.index).padStart(4,'0')+"
        "' '+d.window+'</span> '+d.status;"
        "log.appendChild(line);log.scrollTop=log.scrollHeight;"
        "totals.innerHTML='';"
        "Object.keys(d.totals).forEach(function(k){"
        "var tr=document.createElement('tr');"
        "tr.innerHTML='<td>'+k+'</td><td class=\"n\">'+d.totals[k]+'</td>';"
        "totals.appendChild(tr);});"
        "progress.textContent=d.index+' …';"
        "};})();"
        "</script>"
    )


def _js(text: str) -> str:
    """A Python string as a JavaScript string literal."""
    import json

    return json.dumps(text)


def report_view(data: dict[str, Any], translator: Translator) -> str:
    if not data.get("ready"):
        return (
            f'<main><h2>{e(translator.t("Report"))}</h2>'
            f'<p class="note">{e(translator.t("There is nothing to report yet. Run the field phase first."))}</p>'
            "</main>"
        )
    included = data["included"] or 1
    yield_percent = 100 * data["completed"] / included
    counts = (
        f'<div class="counts">'
        f'<div><span class="big">{yield_percent:.1f}%</span>'
        f'<span class="cap">{e(translator.t("completion yield"))}</span></div>'
        f'<div><span class="big">{data["completed"]}</span>'
        f'<span class="cap">{e(translator.t("completed"))}</span></div>'
        f'<div><span class="big">{data["attempted"]}</span>'
        f'<span class="cap">{e(translator.t("attempted"))}</span></div>'
        f'<div><span class="big">{data.get("attempts", data["attempted"])}</span>'
        f'<span class="cap">{e(translator.t("calls placed"))}</span></div>'
        f'<div><span class="big">{data.get("repeated", 0)}</span>'
        f'<span class="cap">{e(translator.t("dialled more than once"))}</span></div>'
        f'<div><span class="big">{data["included"]}</span>'
        f'<span class="cap">{e(translator.t("included in the sample"))}</span></div>'
        f'<div><span class="big">{data["withdrawn"]}</span>'
        f'<span class="cap">{e(translator.t("withdrawn"))}</span></div>'
        "</div>"
        f'<p class="sub">{e(translator.t("Take the data with you:"))} '
        f'<a href="/export/dataset.csv">dataset.csv</a> · '
        f'<a href="/export/free-text.csv">free-text.csv</a> · '
        f'<a href="/export/codebook.md">codebook.md</a> · '
        f'<a href="/export/findings.md">{e(data.get("findings_file", "findings.md"))}</a> · '
        f'<a href="/report.md">report.md</a></p>'
    )

    statuses = data["statuses"]
    widest = max(statuses.values(), default=1) or 1
    status_rows = "".join(
        f'<tr><td>{e(name)}</td><td class="n">{count}</td>'
        f'<td style="width:45%"><span class="bar{"" if name == "COMPLETED" else " loss"}" '
        f'style="width:{100 * count / widest:.0f}%"></span></td></tr>'
        for name, count in statuses.items()
    )

    window_names = sorted(data["by_window"])
    all_statuses = sorted({s for counts_ in data["by_window"].values() for s in counts_ if s != "drawn"})
    header = "".join(f"<th>{e(name)}</th>" for name in all_statuses)
    window_rows = "".join(
        "<tr><td>" + e(window) + "</td>"
        + f'<td class="n">{data["by_window"][window].get("drawn", 0)}</td>'
        + "".join(
            f'<td class="n">{data["by_window"][window].get(status, 0)}</td>'
            for status in all_statuses
        )
        + "</tr>"
        for window in window_names
    )
    report_heading = (
        "The report as it is written to disk"
        if data.get("report_written")
        else "Report preview — no report file exists for this earlier run"
    )

    return (
        f'<main><h2>{e(translator.t("Report"))}</h2>'
        f'<p class="sub">{e(translator.t("Descriptive. Differences between windows are shown, not declared significant."))}</p>'
        f"{counts}"
        f'<p class="note">{e(translator.t("NO_ANSWER is a time-of-day signal, DECLINED is refusal. They are never added together."))}</p>'
        f'<h3>{e(translator.t("Terminal outcomes"))}</h3>'
        f'<div class="scroll"><table class="data">{status_rows}</table></div>'
        f'<h3>{e(translator.t("Outcome structure by assigned time window"))}</h3>'
        f'<div class="scroll"><table class="data"><thead><tr>'
        f'<th>{e(translator.t("window"))}</th><th>{e(translator.t("drawn"))}</th>{header}'
        f"</tr></thead><tbody>{window_rows}</tbody></table></div>"
        f'<h3>{e(translator.t(report_heading))}</h3>'
        f'<div class="panel" style="background:var(--card);border:1px solid var(--line);border-radius:8px;padding:.9rem 1rem">'
        f'<pre class="config">{e(data["report"])}</pre></div>'
        "</main>"
    )


# --- configuration ------------------------------------------------------------

def config_view(
    fields: list[forms.Field], workspace: Workspace, translator: Translator
) -> str:
    import json

    visible_fields = [field for field in fields if not field.locked]
    config = workspace.config(visible_fields)
    summary = effect.summary(visible_fields)
    declared = effect.declared_only(fields)
    declared_rows = "".join(
        f'<tr><td class="mono">{e(f.path)}</td>'
        f'<td>{e(translator.t(effect.reason_of(f.path)))}</td></tr>'
        for f in declared
    )
    counts = " · ".join(
        f"{summary[name]} {translator.t(EFFECT_LABELS[name])}"
        for name in effect.ORDER
        if summary[name]
    )
    return (
        f'<main><h2>{e(translator.t("Configuration"))}</h2>'
        f'<p class="sub">{e(translator.t("Editable configuration. Defaults from the visible form definitions, your answers on top."))}</p>'
        f'<p class="sub">{e(counts)}</p>'
        f'<div class="config-stack"><section><div class="panel"><pre class="config">{e(json.dumps(config, ensure_ascii=False, indent=2))}</pre></div></section>'
        f'<aside><div class="panel"><h3>{e(translator.t("Recorded, not yet read"))}</h3>'
        f'<p class="none">{e(translator.t("These values are kept and exported, but no part of the machinery acts on them yet. The list is generated from the code, so a setting cannot quietly move between the two groups."))}</p>'
        f'<div class="scroll"><table class="data">{declared_rows}</table></div>'
        "</div></aside></div></main>"
    )


# -- frame upload, withdrawal and the conflict queue -----------------------

def frame_panel(
    translator: Translator, uploaded_name: str | None, message: str = "", warn: bool = False
) -> str:
    """Bring your own frame — or let the dry run invent one."""
    t = translator.t
    note = ""
    if message:
        css = "note warn" if warn else "note"
        note = f'<p class="{css}">{e(message)}</p>'
    current = (
        f'<p class="sub">{e(t("Current frame:"))} <span class="mono">{e(uploaded_name)}</span> — '
        f'{e(t("it replaces the fictitious dry-run frame at preparation."))}</p>'
        if uploaded_name
        else f'<p class="sub">{e(t("No frame uploaded. The dry run will invent a fictitious one."))}</p>'
    )
    return (
        f'<div class="panel"><h3>{e(t("Sampling frame"))}</h3>'
        f'<p class="sub">{e(t("A .csv or .xlsx file with the columns external_ref and phone (E.164). This is how a vendor-drawn or self-generated frame enters the study."))}</p>'
        f"{current}{note}"
        f'<form method="post" action="/fieldwork/frame" enctype="multipart/form-data">'
        f'<input type="file" name="frame" accept=".csv,.xlsx" required> '
        f'<button type="submit">{e(t("Upload frame"))}</button>'
        f"</form></div>"
    )


def withdraw_panel(translator: Translator, message: str = "", warn: bool = False) -> str:
    """One person leaves the data; the row stays, unlinked from any number."""
    t = translator.t
    note = ""
    if message:
        css = "note warn" if warn else "note"
        note = f'<p class="{css}">{e(message)}</p>'
    return (
        f'<div class="panel"><h3>{e(t("Withdrawal"))}</h3>'
        f'<p class="sub">{e(t("Removes the phone number and the reference for one person. Their remaining data stays as one record that can no longer be linked to a number, and they leave every later denominator."))}</p>'
        f"{note}"
        f'<form method="post" action="/fieldwork/withdraw">'
        f'<input type="text" name="external_ref" placeholder="external_ref" required> '
        f'<button type="submit">{e(t("Anonymize this person"))}</button>'
        f"</form></div>"
    )


def reviews_view(
    cases: list[dict], translator: Translator, message: str = "", warn: bool = False
) -> str:
    """The conflict queue: every case a person still has to look at."""
    t = translator.t
    note = ""
    if message:
        css = "note warn" if warn else "note"
        note = f'<p class="{css}">{e(message)}</p>'
    if not cases:
        body = f'<p class="none">{e(t("No open cases. Every flagged call has been decided."))}</p>'
    else:
        blocks = []
        for case in cases:
            reasons = ", ".join(case["reasons"])
            transcript = case.get("transcript") or t("No transcript was recorded for this attempt.")
            gates_missed = ", ".join(case.get("gates_missed") or []) or "—"
            blocks.append(
                f'<div class="panel"><h3>#{case["review_id"]} · {e(t("attempt"))} {case["attempt_no"]} · '
                f'<span class="mono">{e(case["call_status"])}</span></h3>'
                f'<p class="sub">{e(t("Flagged:"))} {e(reasons)} · {e(t("opened"))} {e(case["opened_at"][:19])}</p>'
                f'<p class="sub">{e(t("Gate phrases not seen:"))} <span class="mono">{e(gates_missed)}</span></p>'
                f'<details><summary>{e(t("Transcript"))}</summary>'
                f'<pre class="config">{e(transcript)}</pre></details>'
                f'<form method="post" action="/reviews/decide">'
                f'<input type="hidden" name="review_id" value="{case["review_id"]}">'
                f'<input type="text" name="note" placeholder="{e(t("Grounds for the decision (required)"))}" required> '
                f'<button type="submit" name="decision" value="gate_passed">{e(t("Gate passed"))}</button> '
                f'<button type="submit" name="decision" value="dropout">{e(t("Dropout"))}</button> '
                f'<button type="submit" name="decision" value="excluded">{e(t("Exclude"))}</button>'
                f"</form></div>"
            )
        body = "".join(blocks)
    return (
        f'<main><h2>{e(t("Conflict review"))}</h2>'
        f'<p class="sub">{e(t("Calls whose after-call checks were not cleanly green. The recorded attempt is never overwritten; the decision is written beside it, with its grounds. Aggregation waits until this list is empty."))}</p>'
        f"{note}{body}</main>"
    )
