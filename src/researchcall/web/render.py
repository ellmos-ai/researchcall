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

from .. import forms
from .i18n import LANGUAGE_NAMES, Translator
from .workspace import STATIONS, Workspace


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


STYLE = """
:root {
  --paper: #f7f5f0; --card: #fffefb; --ink: #1c1b19; --muted: #6b6862;
  --line: #ddd8cd; --accent: #2f5d62; --accent-soft: #e4ece9;
  --warn: #8a5a1e; --warn-soft: #f6ecdc; --ok: #2f6b3a;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #14161a; --card: #1b1e23; --ink: #e8e6e1; --muted: #9a968e;
    --line: #2e333a; --accent: #7fb3ab; --accent-soft: #1f2a2b;
    --warn: #d7a75c; --warn-soft: #2a2318; --ok: #7fc08c;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font: 16px/1.55 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
}
a { color: var(--accent); }
code, .mono { font-family: "SF Mono", "Cascadia Mono", Consolas, monospace; font-size: .85em; }

header.top {
  display: flex; flex-wrap: wrap; gap: 1rem; align-items: baseline;
  padding: 1rem 1.5rem; border-bottom: 1px solid var(--line); background: var(--card);
}
header.top h1 { font-size: 1.15rem; margin: 0; letter-spacing: .01em; }
header.top .tag { color: var(--muted); font-size: .8rem; }
header.top nav { margin-left: auto; display: flex; gap: .75rem; align-items: center; }
.lang a {
  text-decoration: none; border: 1px solid var(--line); border-radius: 999px;
  padding: .15rem .7rem; font-size: .8rem;
}

.shell { display: grid; grid-template-columns: minmax(210px, 260px) 1fr; gap: 0; }
@media (max-width: 860px) { .shell { grid-template-columns: 1fr; } }

nav.rail { border-right: 1px solid var(--line); padding: 1rem .75rem; }
nav.rail ol { list-style: none; margin: 0; padding: 0; }
nav.rail li { margin: 0 0 .2rem; }
nav.rail a, nav.rail span.locked {
  display: block; padding: .45rem .6rem; border-radius: 6px;
  text-decoration: none; color: var(--ink); font-size: .9rem;
}
nav.rail a:hover { background: var(--accent-soft); }
nav.rail a.current { background: var(--accent-soft); font-weight: 600; }
nav.rail span.locked { color: var(--muted); cursor: not-allowed; }
nav.rail .num { color: var(--muted); font-size: .75rem; margin-right: .45rem; }
nav.rail .mark { float: right; font-size: .8rem; }
nav.rail .done { color: var(--ok); }
nav.rail .extra { border-top: 1px solid var(--line); margin-top: .8rem; padding-top: .6rem; }

main { padding: 1.5rem 1.75rem 3rem; min-width: 0; }
h2 { font-size: 1.5rem; margin: 0 0 .2rem; }
.sub { color: var(--muted); font-size: .85rem; margin: 0 0 1.4rem; }

.split { display: grid; grid-template-columns: 1fr minmax(260px, 360px); gap: 1.75rem; }
@media (max-width: 1100px) { .split { grid-template-columns: 1fr; } }

fieldset { border: none; margin: 0; padding: 0; }
.field {
  background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: .85rem 1rem; margin: 0 0 .8rem;
}
.field > label.name { display: block; font-weight: 600; margin-bottom: .35rem; }
.field .req { color: var(--warn); font-weight: 400; }
.field .help { color: var(--muted); font-size: .82rem; margin-top: .4rem; }
.field .path { color: var(--muted); font-size: .72rem; float: right; font-weight: 400; }
.field.amended { border-left: 3px solid var(--warn); }
.field .amended-mark {
  display: inline-block; background: var(--warn-soft); color: var(--warn);
  font-size: .7rem; padding: .05rem .45rem; border-radius: 999px; margin-left: .4rem;
}
input[type=text], input[type=number], textarea, select {
  width: 100%; padding: .45rem .55rem; border: 1px solid var(--line); border-radius: 5px;
  background: var(--paper); color: var(--ink); font: inherit; font-size: .95rem;
}
textarea { min-height: 4.5rem; resize: vertical; }
.choices { display: flex; flex-wrap: wrap; gap: .4rem .9rem; }
.choices label { font-size: .92rem; display: flex; gap: .35rem; align-items: center; }
.switch { display: flex; gap: .45rem; align-items: center; font-size: .92rem; }

button, .button {
  font: inherit; font-size: .92rem; padding: .5rem 1.1rem; border-radius: 6px;
  border: 1px solid var(--accent); background: var(--accent); color: #fff;
  cursor: pointer; text-decoration: none; display: inline-block;
}
button.quiet, .button.quiet { background: transparent; color: var(--accent); }
.actions { display: flex; gap: .7rem; align-items: center; margin-top: 1.2rem; flex-wrap: wrap; }

aside .panel {
  background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: .9rem 1rem; margin-bottom: 1rem;
}
aside h3 { font-size: .82rem; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); margin: 0 0 .55rem; font-weight: 600; }
aside ol.asks { margin: 0; padding-left: 1.1rem; font-size: .9rem; }
aside ol.asks li { margin-bottom: .4rem; }
aside .none { color: var(--muted); font-size: .88rem; margin: 0; }
pre.config {
  margin: 0; white-space: pre-wrap; word-break: break-word;
  font-family: "SF Mono", "Cascadia Mono", Consolas, monospace; font-size: .78rem;
  color: var(--ink); max-height: 22rem; overflow: auto;
}

.note {
  border-left: 3px solid var(--accent); background: var(--accent-soft);
  padding: .6rem .9rem; border-radius: 0 6px 6px 0; font-size: .88rem; margin: 0 0 1.2rem;
}
.note.warn { border-left-color: var(--warn); background: var(--warn-soft); }
.note.locked-note { border-left-color: var(--muted); background: transparent;
  border: 1px dashed var(--line); border-radius: 6px; color: var(--muted); }

table.data { border-collapse: collapse; width: 100%; font-size: .88rem; }
table.data th, table.data td {
  border-bottom: 1px solid var(--line); padding: .35rem .6rem; text-align: left;
}
table.data th { color: var(--muted); font-weight: 600; font-size: .78rem;
  text-transform: uppercase; letter-spacing: .04em; }
table.data td.n { text-align: right; font-variant-numeric: tabular-nums; }
.bar { height: .5rem; border-radius: 3px; background: var(--accent); display: block; min-width: 1px; }
.bar.loss { background: var(--warn); }
.scroll { overflow-x: auto; }

.counts { display: flex; gap: 1.4rem; flex-wrap: wrap; margin: 0 0 1.2rem; }
.counts div { }
.counts .big { font-size: 1.9rem; font-variant-numeric: tabular-nums; line-height: 1.1; }
.counts .cap { color: var(--muted); font-size: .78rem; }
.log { font-family: "SF Mono", "Cascadia Mono", Consolas, monospace; font-size: .8rem;
  background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: .7rem .9rem; max-height: 20rem; overflow: auto; }
.log div { padding: .05rem 0; }
.log .st { color: var(--muted); }
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
        f"<style>{STYLE}</style>"
        '<script src="/static/htmx.min.js" defer></script>'
        "</head><body>"
        '<header class="top"><h1>ResearchCall</h1>'
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
        f'<li class="extra"><a class="{"current" if active == "fieldwork" else ""}" '
        f'href="/fieldwork?lang={e(translator.language)}">{e(translator.t("Field phase"))}</a></li>'
        f'<li><a class="{"current" if active == "report" else ""}" '
        f'href="/report?lang={e(translator.language)}">{e(translator.t("Report"))}</a></li>'
        f'<li><a class="{"current" if active == "config" else ""}" '
        f'href="/config?lang={e(translator.language)}">{e(translator.t("Configuration"))}</a></li>'
    )
    return f'<nav class="rail"><ol>{"".join(items)}{extras}</ol></nav>'


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


def field_block(
    descriptor: dict[str, Any],
    value: Any,
    translator: Translator,
    amended: bool = False,
) -> str:
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
    return (
        f'<div class="field{" amended" if amended else ""}">'
        f'<label class="name" for="{e(descriptor["name"])}">'
        f'<span class="path mono">{e(descriptor["name"])}</span>'
        f'{e(descriptor["label"])}{required}{mark}</label>'
        f"{control(descriptor, value)}{help_text}</div>"
    )


# --- the station page ---------------------------------------------------------

def station_view(
    station: str,
    fields: list[forms.Field],
    workspace: Workspace,
    translator: Translator,
    message: str = "",
    missing: Iterable[str] = (),
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
    locked_here = [f for f in fields if f.station == station and f.locked]
    if locked_here:
        notes.append(
            f'<p class="note locked-note">{e(translator.t("This station also carries settings that are part of the frame and cannot be switched off. They are therefore not shown as controls; the configuration states them."))}</p>'
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
    counts = translator.t("{visible} of {total} settings shown · {locked} belong to the frame · an agent asks {asked}")
    counts = (
        counts.replace("{visible}", str(len(descriptors)))
        .replace("{total}", str(sum(1 for f in fields if f.station == station)))
        .replace("{locked}", str(len(locked_here)))
        .replace("{asked}", str(len(asks)))
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
        f'<div class="panel"><h3>{e(translator.t("The same decisions, asked by an agent"))}</h3>{ask_list}</div>'
        f'<div class="panel"><h3>{e(translator.t("One definition, three ways in"))}</h3>'
        f'<p class="none">{e(translator.t("Every control on the left is rendered from a form definition under pipeline/_shared/forms/. The same definition produces the config value and the spoken question. The interface adds no field of its own."))}</p></div>'
        "</aside></div></main>"
    )
    return body


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
        f'<div><span class="big">{plan["quota"]}</span><span class="cap">'
        f'{e(translator.t("daily quota"))}</span></div>'
        f'<div><span class="big">{len(plan["windows"])}</span><span class="cap">'
        f'{e(translator.t("time windows"))} · {e(windows)}</span></div>'
        "</div>"
    )
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

    start = (
        f'<form hx-post="/fieldwork/prepare?lang={e(language)}" hx-target="#monitor" hx-swap="innerHTML">'
        f'<button type="submit">{e(translator.t("Draw sample and start dry run"))}</button>'
        "</form>"
    )
    monitor = monitor_panel(translator) if ready else ""

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
        f'<div><span class="big">{data["included"]}</span>'
        f'<span class="cap">{e(translator.t("included in the sample"))}</span></div>'
        f'<div><span class="big">{data["withdrawn"]}</span>'
        f'<span class="cap">{e(translator.t("withdrawn"))}</span></div>'
        "</div>"
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
        f'<h3>{e(translator.t("The report as it is written to disk"))}</h3>'
        f'<div class="panel" style="background:var(--card);border:1px solid var(--line);border-radius:8px;padding:.9rem 1rem">'
        f'<pre class="config">{e(data["report"])}</pre></div>'
        "</main>"
    )


# --- configuration ------------------------------------------------------------

def config_view(
    fields: list[forms.Field], workspace: Workspace, translator: Translator
) -> str:
    import json

    config = workspace.config(fields)
    locked = [f for f in fields if f.locked]
    locked_rows = "".join(
        f'<tr><td class="mono">{e(f.path)}</td><td>{e(f.text("help", translator.language))}</td></tr>'
        for f in locked
    )
    return (
        f'<main><h2>{e(translator.t("Configuration"))}</h2>'
        f'<p class="sub">{e(translator.t("What the pipeline reads. Defaults from the form definitions, your answers on top."))}</p>'
        f'<div class="split"><section><div class="panel"><pre class="config">{e(json.dumps(config, ensure_ascii=False, indent=2))}</pre></div></section>'
        f'<aside><div class="panel"><h3>{e(translator.t("Part of the frame"))}</h3>'
        f'<p class="none">{e(translator.t("These settings appear in no form and in no question. They are stated here so that nothing is hidden, not so that they can be changed."))}</p>'
        f'<div class="scroll"><table class="data">{locked_rows}</table></div>'
        "</div></aside></div></main>"
    )
