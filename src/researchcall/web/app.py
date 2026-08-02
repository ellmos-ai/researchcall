"""The workbench as a web application.

FastAPI serves HTML fragments, HTMX swaps them, server-sent events carry the
field-phase progress. No build step, no bundler, no request to a third party: the
one script it loads is vendored beside this module.

The application is a *surface* on the pipeline, not a second implementation of
it. Its station pages render ``forms.form(...)``; its field phase drives
``runner.run_day``; its report is ``reporting.build_report``.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from .. import forms
from . import field_phase, render
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, Translator, load_table, normalize
from .workspace import STATIONS, Workspace, coerce

STATIC = pathlib.Path(__file__).resolve().parent / "static"
LANGUAGE_COOKIE = "researchcall_lang"
DEFAULT_WORKSPACE = pathlib.Path("out") / "workbench"


def workspace_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("RESEARCHCALL_WORKSPACE", str(DEFAULT_WORKSPACE)))


def create_app(
    workspace_dir: str | pathlib.Path | None = None,
    forms_root: pathlib.Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="ResearchCall workbench",
        description=(
            "Bilingual surface on the eight-station research pipeline. "
            "Dry run only — this interface cannot place a call."
        ),
    )
    directory = pathlib.Path(workspace_dir) if workspace_dir else workspace_path()
    fields = forms.load_fields(forms_root)
    table = load_table()

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    app.state.workspace_dir = directory
    app.state.fields = fields

    # --- request helpers ---------------------------------------------------

    def language_of(request: Request) -> str:
        asked = request.query_params.get("lang")
        if asked:
            return normalize(asked)
        cookie = request.cookies.get(LANGUAGE_COOKIE)
        if cookie:
            return normalize(cookie)
        header = request.headers.get("accept-language", "")
        for part in header.split(","):
            code = normalize(part.split(";")[0])
            if part.strip() and code in LANGUAGES and part.strip()[:2].lower() == code:
                return code
        return DEFAULT_LANGUAGE

    def translator_of(request: Request) -> Translator:
        return Translator(language_of(request), table)

    def load_workspace() -> Workspace:
        return Workspace.load(directory)

    def shell(request: Request, body: str, title: str, active: str) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        page = render.page(
            title,
            f'<div class="shell">{render.rail(workspace, translator, active)}{body}</div>',
            translator,
            active,
        )
        response = HTMLResponse(page)
        response.set_cookie(
            LANGUAGE_COOKIE, translator.language, max_age=31_536_000, samesite="lax"
        )
        return response

    # --- overview ----------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def overview(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        visible = len(forms.form(fields))
        asked = len(forms.interview(fields))
        locked = sum(1 for field in fields if field.locked)
        rows = []
        for index, station in enumerate(STATIONS, start=1):
            station_fields = [f for f in fields if f.station == station]
            rows.append(
                "<tr>"
                f'<td class="n">{index}</td>'
                f'<td><a href="/station/{render.e(station)}?lang={render.e(translator.language)}">'
                f"{render.e(translator.t(render.STATION_TITLES[station]))}</a></td>"
                f'<td class="n">{len(forms.form(station_fields, station, translator.language))}</td>'
                f'<td class="n">{sum(1 for f in station_fields if f.locked)}</td>'
                f'<td class="n">{len(forms.interview(station_fields, station, translator.language))}</td>'
                f"<td>{'✓' if station in workspace.completed else ''}</td>"
                "</tr>"
            )
        headline = (
            translator.t("{total} decisions in eight stations. An interface shows {visible}, an agent asks {asked}, and {locked} are part of the frame and appear nowhere.")
            .replace("{total}", str(len(fields)))
            .replace("{visible}", str(visible))
            .replace("{asked}", str(asked))
            .replace("{locked}", str(locked))
        )
        body = (
            f'<main><h2>{render.e(translator.t("A research method, not a call script"))}</h2>'
            f'<p class="sub">{render.e(headline)}</p>'
            f'<p class="note">{render.e(translator.t("Station N+1 opens once N is finished. Later changes stay possible and are marked as later additions — the point is transparency towards yourself."))}</p>'
            f'<p class="note">{render.e(translator.t("Analysis rules are fixed at the instrument, not after the results are in."))}</p>'
            '<div class="scroll"><table class="data"><thead><tr>'
            f'<th></th><th>{render.e(translator.t("Station"))}</th>'
            f'<th>{render.e(translator.t("shown"))}</th>'
            f'<th>{render.e(translator.t("frame"))}</th>'
            f'<th>{render.e(translator.t("asked"))}</th>'
            f'<th>{render.e(translator.t("done"))}</th>'
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
            f'<p class="sub" style="margin-top:1.2rem">{render.e(translator.t("Every number on this page is counted from the form definitions at request time."))}</p>'
            "</main>"
        )
        return shell(request, body, translator.t("Overview"), "")

    # --- stations ----------------------------------------------------------

    @app.get("/station/{station}", response_class=HTMLResponse)
    async def station_page(request: Request, station: str) -> Any:
        translator = translator_of(request)
        if station not in STATIONS:
            return RedirectResponse("/", status_code=303)
        workspace = load_workspace()
        if not workspace.is_open(station):
            return RedirectResponse(
                f"/station/{STATIONS[0]}?lang={translator.language}", status_code=303
            )
        body = render.station_view(station, fields, workspace, translator)
        return shell(request, body, translator.t(render.STATION_TITLES[station]), station)

    @app.post("/station/{station}", response_class=HTMLResponse)
    async def station_submit(request: Request, station: str) -> Any:
        translator = translator_of(request)
        if station not in STATIONS:
            return RedirectResponse("/", status_code=303)
        workspace = load_workspace()
        if not workspace.is_open(station):
            return RedirectResponse(
                f"/station/{STATIONS[0]}?lang={translator.language}", status_code=303
            )

        submitted = await request.form()
        action = submitted.get("action", "save")

        # Only fields this station actually declares are accepted. Anything else
        # in the payload is ignored — the definitions decide, not the browser.
        answers: dict[str, Any] = {}
        for field in fields:
            if field.station != station or field.locked:
                continue
            if field.type in {"multi"}:
                answers[field.path] = coerce(submitted.getlist(field.path), field.type)
            elif field.type == "bool":
                answers[field.path] = coerce(submitted.get(field.path), field.type)
            elif field.path in submitted:
                answers[field.path] = coerce(submitted.get(field.path), field.type)

        amended = workspace.record(station, answers)
        message = ""
        missing: list[str] = []
        if action == "complete":
            missing = workspace.complete(fields, station)
            if not missing:
                message = translator.t("Station finished. The next one is open.")
        elif amended:
            message = translator.t("Saved. Changes to a finished station are marked as later additions.")
        else:
            message = translator.t("Saved.")
        workspace.save()

        body = render.station_view(
            station, fields, workspace, translator, message=message, missing=missing
        )
        return shell(request, body, translator.t(render.STATION_TITLES[station]), station)

    # --- configuration -----------------------------------------------------

    @app.get("/config", response_class=HTMLResponse)
    async def config_page(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        body = render.config_view(fields, load_workspace(), translator)
        return shell(request, body, translator.t("Configuration"), "config")

    @app.get("/config.json")
    async def config_json() -> Any:
        return load_workspace().config(fields)

    # --- field phase -------------------------------------------------------

    @app.get("/fieldwork", response_class=HTMLResponse)
    async def fieldwork_page(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        plan = field_phase.planned(workspace, fields)
        problem = ""
        if plan["size"] <= 0:
            problem = translator.t("Set a sample size in station 4 before the field phase.")
        body = render.fieldwork_view(
            plan, None, translator, field_phase.exists(workspace), problem
        )
        return shell(request, body, translator.t("Field phase"), "fieldwork")

    @app.post("/fieldwork/prepare", response_class=HTMLResponse)
    async def fieldwork_prepare(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        try:
            field_phase.prepare(workspace, fields)
        except (ValueError, OSError) as error:
            return HTMLResponse(
                f'<p class="note warn">{render.e(str(error))}</p>', status_code=200
            )
        return HTMLResponse(render.monitor_panel(translator))

    @app.get("/fieldwork/stream")
    async def fieldwork_stream() -> StreamingResponse:
        workspace = load_workspace()

        def events():
            if not field_phase.exists(workspace):
                yield "data: " + json.dumps({"done": True, "processed": 0, "totals": {}}) + "\n\n"
                return
            for event in field_phase.run(workspace, fields):
                yield "data: " + json.dumps(event) + "\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    # --- report ------------------------------------------------------------

    @app.get("/report", response_class=HTMLResponse)
    async def report_page(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        body = render.report_view(field_phase.summary(load_workspace()), translator)
        return shell(request, body, translator.t("Report"), "report")

    @app.get("/report.md", response_class=PlainTextResponse)
    async def report_markdown() -> PlainTextResponse:
        workspace = load_workspace()
        if not field_phase.exists(workspace):
            return PlainTextResponse("No field phase has run yet.\n", status_code=404)
        return PlainTextResponse(field_phase.summary(workspace)["report"])

    return app


app = create_app()


def main() -> None:
    """Start the workbench locally."""
    import uvicorn

    host = os.environ.get("RESEARCHCALL_HOST", "127.0.0.1")
    port = int(os.environ.get("RESEARCHCALL_PORT", "8000"))
    print(f"ResearchCall workbench on http://{host}:{port}  (dry run, no calls)")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
