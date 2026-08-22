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
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from datetime import datetime, timezone

from .. import effect, export, forms, huckepack_web, instrument, pretest
from ..questionnaire import build_task
from . import field_phase, render, test_mode
from .i18n import DEFAULT_LANGUAGE, LANGUAGES, Translator, load_table, normalize
from .workspace import STATIONS, Workspace, coerce

#: Stations where the instrument being built is the thing under discussion.
INSTRUMENT_PANEL_STATIONS = {"02-instrument", "03-ethics", "05-pretest", "06-fieldwork"}

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

    # Server modes: descriptor, browser snapshot, per-request session and key.
    huckepack_web.install(app)

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

    def panels_for(station: str, workspace: Workspace, translator: Translator) -> str:
        """The aside panels a station carries beyond its own form."""
        if station not in INSTRUMENT_PANEL_STATIONS:
            return ""
        plan = field_phase.planned(workspace, fields, translator.language)
        return render.instrument_panel(plan, translator)

    def shell(request: Request, body: str, title: str, active: str) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        # RC1 (Endabnahme 2026-08-22): a language switch used to leave the
        # test-mode example content in whichever language it was first
        # generated in. `shell()` renders on every page, so it is the one
        # place that reliably sees a language change and can persist the
        # catch-up before the visitor's next click. Content already built
        # into `body` by this same request still shows the old language once
        # — the fix takes effect from the next navigation.
        if workspace.test_mode and workspace.test_example_language != translator.language:
            workspace.sync_test_mode_language(
                translator.language,
                test_mode.example_values(fields, translator.language),
                test_mode.example_values(
                    fields, workspace.test_example_language or translator.language
                ),
            )
            workspace.save()
        mode_banner = test_mode.banner(workspace.test_mode, translator, request.url.path)
        page = render.page(
            title,
            f'{mode_banner}<div class="shell">'
            f'{render.rail(workspace, translator, active)}{body}</div>',
            translator,
            active,
        )
        response = HTMLResponse(page)
        response.set_cookie(
            LANGUAGE_COOKIE, translator.language, max_age=31_536_000, samesite="lax"
        )
        return response

    @app.post("/test-mode/toggle")
    async def toggle_test_mode(request: Request) -> RedirectResponse:
        """Switch the isolated fixture tour on or off; never changes live capability."""
        translator = translator_of(request)
        workspace = load_workspace()
        if workspace.test_mode:
            workspace.disable_test_mode()
        else:
            workspace.enable_test_mode(
                test_mode.example_values(fields, translator.language), translator.language
            )
        workspace.save()
        target = test_mode.safe_return_path(request.query_params.get("next"))
        separator = "&" if "?" in target else "?"
        response = RedirectResponse(
            f"{target}{separator}lang={translator.language}", status_code=303
        )
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
        rows = []
        for index, station in enumerate(STATIONS, start=1):
            station_fields = [f for f in fields if f.station == station]
            rows.append(
                "<tr>"
                f'<td class="n">{index}</td>'
                f'<td><a href="/station/{render.e(station)}?lang={render.e(translator.language)}">'
                f"{render.e(translator.t(render.STATION_TITLES[station]))}</a></td>"
                f'<td class="n">{len(forms.form(station_fields, station, translator.language))}</td>'
                f'<td class="n">{len(forms.interview(station_fields, station, translator.language))}</td>'
                f"<td>{'✓' if station in workspace.completed else ''}</td>"
                "</tr>"
            )
        headline = (
            translator.t("Eight stations contain {visible} visible decisions. An agent asks {asked} of them when no default is available.")
            .replace("{visible}", str(visible))
            .replace("{asked}", str(asked))
        )
        order_note = (
            translator.t(
                "Test mode opens every station in any order; the example workspace stays separate."
            )
            if workspace.test_mode
            else translator.t(
                "Station N+1 opens once N is finished. Later changes stay possible and are marked as later additions — the point is transparency towards yourself."
            )
        )
        body = (
            f'<main><h2>{render.e(translator.t("A research method, not a call script"))}</h2>'
            f'<p class="sub">{render.e(headline)}</p>'
            f'<p class="note">{render.e(order_note)}</p>'
            f'<p class="note">{render.e(translator.t("Analysis rules are fixed at the instrument, not after the results are in."))}</p>'
            '<div class="scroll"><table class="data"><thead><tr>'
            f'<th></th><th>{render.e(translator.t("Station"))}</th>'
            f'<th>{render.e(translator.t("shown"))}</th>'
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
        body = render.station_view(
            station, fields, workspace, translator, panels=panels_for(station, workspace, translator)
        )
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
            station,
            fields,
            workspace,
            translator,
            message=message,
            missing=missing,
            panels=panels_for(station, workspace, translator),
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

    # --- the instrument ----------------------------------------------------

    @app.get("/instrument", response_class=HTMLResponse)
    async def instrument_page(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        plan = field_phase.planned(workspace, fields, translator.language)
        script = instrument.describe(plan["questionnaire"], translator.language)
        values = field_phase.values_of(workspace, fields)
        body = render.instrument_view(
            plan,
            script,
            translator,
            downloadable=bool(values.get("pretest.export_questionnaire", True)),
        )
        return shell(request, body, translator.t("The call, as written"), "instrument")

    @app.get("/instrument.md", response_class=PlainTextResponse)
    async def instrument_markdown(request: Request) -> PlainTextResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        values = field_phase.values_of(workspace, fields)
        if not values.get("pretest.export_questionnaire", True):
            return PlainTextResponse(
                "Handing the questionnaire around is switched off in station 5 "
                "(pretest.export_questionnaire).\n",
                status_code=404,
            )
        plan = field_phase.planned(workspace, fields, translator.language)
        lines = instrument.describe(plan["questionnaire"], translator.language)
        if plan["problems"]:
            lines += ["", "## Lines that could not be read", ""]
            lines += [
                f"- line {problem.line}: {problem.message} — {problem.text}"
                for problem in plan["problems"]
            ]
        return PlainTextResponse("\n".join(lines) + "\n")

    @app.get("/instrument.task.txt", response_class=PlainTextResponse)
    async def instrument_task(request: Request) -> PlainTextResponse:
        """The exact text an agent would receive — the only channel this API has."""
        translator = translator_of(request)
        plan = field_phase.planned(load_workspace(), fields, translator.language)
        if not plan["questionnaire"]["questions"]:
            return PlainTextResponse(
                "Station 2 carries no items, so there is no task to build.\n",
                status_code=404,
            )
        return PlainTextResponse(build_task(plan["questionnaire"]))

    # --- pretest -----------------------------------------------------------

    @app.get("/pretest", response_class=HTMLResponse)
    async def pretest_page(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        plan = field_phase.planned(workspace, fields, translator.language)
        problem = ""
        if not workspace.completed_through("05-pretest"):
            problem = translator.t(
                "Finish stations 1 to 5 before running the instrument check."
            )
        body = render.pretest_view(None, plan, translator, problem=problem)
        return shell(request, body, translator.t("Instrument check"), "pretest")

    @app.post("/pretest/run", response_class=HTMLResponse)
    async def pretest_run(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        if not workspace.completed_through("05-pretest"):
            return HTMLResponse(
                f'<p class="note warn">'
                f'{render.e(translator.t("Finish stations 1 to 5 before running the instrument check."))}'
                "</p>"
            )
        plan = field_phase.planned(workspace, fields, translator.language)
        if plan["problems"] or not plan["questionnaire"]["questions"]:
            return HTMLResponse(
                f'<p class="note warn">'
                f'{render.e(translator.t("Station 2 carries no items yet, so there is nothing to ask."))}'
                "</p>"
            )
        values = field_phase.values_of(workspace, fields)
        try:
            calls = int(values.get("pretest.instrument_check.calls") or 30)
        except (TypeError, ValueError):
            calls = 30
        result = pretest.check(
            plan["questionnaire"],
            calls,
            field_phase._fixture("outcomes.json"),
            str(values.get("pretest.instrument_check.syntactic_marker") or ""),
        )
        return HTMLResponse(render.pretest_result(result, translator))

    # --- field phase -------------------------------------------------------

    @app.get("/fieldwork", response_class=HTMLResponse)
    async def fieldwork_page(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        plan = field_phase.planned(workspace, fields, translator.language)
        problem = ""
        if not workspace.completed_through("06-fieldwork"):
            problem = translator.t(
                "Finish stations 1 to 6 before preparing the field phase."
            )
        elif plan["size"] <= 0 and plan["method"] != "census":
            problem = translator.t("Set a sample size in station 4 before the field phase.")
        elif plan["questions"] == 0:
            problem = translator.t("Station 2 carries no items yet, so there is nothing to ask.")
        upload = field_phase.frame_upload_path(workspace)
        _, reconciliation = field_phase.register(workspace)
        supplemental = render.frame_panel(translator, upload.name if upload else None)
        supplemental += render.withdraw_panel(translator)
        supplemental += render.data_phase_panel(
            reconciliation,
            field_phase.seal_status(workspace),
            translator,
            translator.language,
        )
        open_count = len(field_phase.review_cases(workspace))
        if open_count:
            supplemental += (
                f'<p class="note warn"><a href="/reviews?lang={translator.language}">'
                f"{render.e(translator.t('Open review cases:'))} {open_count}</a></p>"
            )
        body = render.fieldwork_view(
            plan,
            None,
            translator,
            field_phase.exists(workspace),
            problem,
            supplemental=supplemental,
        )
        return shell(request, body, translator.t("Field phase"), "fieldwork")

    @app.post("/fieldwork/frame", response_class=HTMLResponse)
    async def fieldwork_frame(request: Request) -> Any:
        translator = translator_of(request)
        workspace = load_workspace()
        form = await request.form()
        upload = form.get("frame")
        try:
            if upload is None or isinstance(upload, str):
                raise ValueError("No file arrived")
            content = await upload.read()
            _, rows = field_phase.store_frame_upload(
                workspace, upload.filename or "", content
            )
            message, warn = (
                f"{translator.t('Frame accepted:')} {rows} {translator.t('rows.')}",
                False,
            )
        except ValueError as error:
            message, warn = translator.t(str(error)), True
        current = field_phase.frame_upload_path(workspace)
        body = render.frame_panel(
            translator, current.name if current else None, message, warn
        )
        return shell(request, body, translator.t("Field phase"), "fieldwork")

    @app.post("/fieldwork/withdraw", response_class=HTMLResponse)
    async def fieldwork_withdraw(request: Request) -> Any:
        translator = translator_of(request)
        workspace = load_workspace()
        form = await request.form()
        reference = str(form.get("external_ref", "")).strip()
        reason = str(form.get("reason", "")).strip()
        try:
            field_phase.anonymise(workspace, reference, reason)
            message, warn = (
                translator.t(
                    "Withdrawn. The number and the reference are gone; the record stays, unlinked."
                ),
                False,
            )
        except ValueError as error:
            message, warn = translator.t(str(error)), True
        body = render.withdraw_panel(translator, message, warn)
        return shell(request, body, translator.t("Field phase"), "fieldwork")

    # --- the call list and its mask -----------------------------------------

    @app.get("/calls", response_class=HTMLResponse)
    async def calls_page(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        status = str(request.query_params.get("status", "all"))
        try:
            entries = field_phase.calls(workspace, status)
        except ValueError:
            entries, status = field_phase.calls(workspace, "all"), "all"
        body = render.calls_view(entries, status, translator, translator.language)
        return shell(request, body, translator.t("Calls"), "fieldwork")

    @app.get("/calls/{sample_id}", response_class=HTMLResponse)
    async def call_page(request: Request, sample_id: int) -> Any:
        translator = translator_of(request)
        workspace = load_workspace()
        try:
            detail = field_phase.call(workspace, sample_id)
        except ValueError:
            return RedirectResponse(f"/calls?lang={translator.language}", status_code=303)
        body = render.call_mask(detail, translator, translator.language)
        return shell(request, body, translator.t("Call record"), "fieldwork")

    async def _call_mask_after(request: Request, sample_id: int, action) -> Any:
        translator = translator_of(request)
        workspace = load_workspace()
        form = await request.form()
        try:
            action(workspace, form)
            message, warn = translator.t("Recorded."), False
        except (ValueError, KeyError) as error:
            message, warn = translator.t(str(error)), True
        detail = field_phase.call(workspace, sample_id)
        body = render.call_mask(detail, translator, translator.language, message, warn)
        return shell(request, body, translator.t("Call record"), "fieldwork")

    @app.post("/calls/{sample_id}/decide", response_class=HTMLResponse)
    async def call_decide(request: Request, sample_id: int) -> Any:
        return await _call_mask_after(
            request,
            sample_id,
            lambda workspace, form: field_phase.decide_case(
                workspace,
                int(str(form.get("review_id", "0"))),
                str(form.get("decision", "")),
                str(form.get("note", "")),
            ),
        )

    @app.post("/calls/{sample_id}/flag", response_class=HTMLResponse)
    async def call_flag(request: Request, sample_id: int) -> Any:
        return await _call_mask_after(
            request,
            sample_id,
            lambda workspace, form: field_phase.flag_attempt(
                workspace,
                int(str(form.get("attempt_id", "0"))),
                str(form.get("note", "")),
            ),
        )

    @app.post("/calls/{sample_id}/correct", response_class=HTMLResponse)
    async def call_correct(request: Request, sample_id: int) -> Any:
        return await _call_mask_after(
            request,
            sample_id,
            lambda workspace, form: field_phase.correct(
                workspace,
                sample_id,
                str(form.get("question_id", "")).strip(),
                str(form.get("new_category", "")).strip(),
                str(form.get("reason", "")),
            ),
        )

    # --- the data phase: seal, exports, project zip -------------------------

    @app.post("/dataphase/seal", response_class=HTMLResponse)
    async def dataphase_seal(request: Request) -> Any:
        translator = translator_of(request)
        workspace = load_workspace()
        form = await request.form()
        try:
            field_phase.seal(workspace, str(form.get("note", "")))
            message, warn = translator.t("Sealed. Every change from here on is logged."), False
        except ValueError as error:
            message, warn = translator.t(str(error)), True
        register, reconciliation = field_phase.register(workspace)
        del register
        body = "<main>" + render.data_phase_panel(
            reconciliation,
            field_phase.seal_status(workspace),
            translator,
            translator.language,
            message,
            warn,
        ) + "</main>"
        return shell(request, body, translator.t("Data phase"), "fieldwork")

    @app.get("/export/dataset.xlsx")
    async def export_xlsx() -> Any:
        from ..export import dataset_xlsx

        workspace = load_workspace()
        if not field_phase.exists(workspace):
            return PlainTextResponse("No field phase has run yet.\n", status_code=404)
        open_count = len(field_phase.review_cases(workspace))
        if open_count:
            return PlainTextResponse(
                f"{open_count} review case(s) are still open; decide them first.\n",
                status_code=409,
            )
        connection, study = field_phase.open_database(workspace)
        try:
            payload = dataset_xlsx(connection, study)
        finally:
            connection.close()
        from fastapi import Response

        return Response(
            content=payload,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="dataset.xlsx"'},
        )

    @app.get("/export/import.sps", response_class=PlainTextResponse)
    async def export_sps() -> Any:
        from ..export import spss_syntax

        return _exported(spss_syntax, "text/plain; charset=utf-8")

    @app.get("/export/analysis.R", response_class=PlainTextResponse)
    async def export_r() -> Any:
        from ..export import r_script

        return _exported(r_script, "text/plain; charset=utf-8")

    @app.get("/stats/t-test")
    async def stats_t_test(request: Request) -> Any:
        workspace = load_workspace()
        numeric = str(request.query_params.get("numeric", "")).strip()
        group = str(request.query_params.get("group", "")).strip()
        if not numeric or not group:
            return PlainTextResponse(
                "Usage: /stats/t-test?numeric=<item>&group=<item with two categories>\n",
                status_code=400,
            )
        try:
            result = field_phase.run_t_test(workspace, numeric, group)
        except ValueError as error:
            return PlainTextResponse(f"refused: {error}\n", status_code=400)
        return JSONResponse(result)

    @app.get("/project/export.zip")
    async def project_export() -> Any:
        import io as _io
        import zipfile

        workspace = load_workspace()
        root = workspace.path
        buffer = _io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
        from fastapi import Response

        return Response(
            content=buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="researchcall-project.zip"'},
        )

    # --- conflict review ----------------------------------------------------

    @app.get("/reviews", response_class=HTMLResponse)
    async def reviews_page(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        body = render.reviews_view(field_phase.review_cases(workspace), translator)
        return shell(request, body, translator.t("Conflict review"), "fieldwork")

    @app.post("/reviews/rule", response_class=HTMLResponse)
    async def reviews_rule(request: Request) -> Any:
        translator = translator_of(request)
        workspace = load_workspace()
        form = await request.form()
        try:
            closed = field_phase.decide_open_by_rule(
                workspace, str(form.get("decision", "")), str(form.get("note", ""))
            )
            message, warn = (
                f"{closed} {translator.t('case(s) decided by rule. The report tells rule rulings apart from looked-at ones.')}",
                False,
            )
        except (ValueError, KeyError) as error:
            message, warn = translator.t(str(error)), True
        body = render.reviews_view(
            field_phase.review_cases(workspace), translator, message, warn
        )
        return shell(request, body, translator.t("Conflict review"), "fieldwork")

    @app.post("/reviews/decide", response_class=HTMLResponse)
    async def reviews_decide(request: Request) -> Any:
        translator = translator_of(request)
        workspace = load_workspace()
        form = await request.form()
        message, warn = translator.t("Decision recorded."), False
        try:
            field_phase.decide_case(
                workspace,
                int(str(form.get("review_id", "0"))),
                str(form.get("decision", "")),
                str(form.get("note", "")),
            )
        except (ValueError, KeyError) as error:
            message, warn = translator.t(str(error)), True
        body = render.reviews_view(
            field_phase.review_cases(workspace), translator, message, warn
        )
        return shell(request, body, translator.t("Conflict review"), "fieldwork")

    @app.post("/fieldwork/prepare", response_class=HTMLResponse)
    async def fieldwork_prepare(request: Request) -> HTMLResponse:
        translator = translator_of(request)
        workspace = load_workspace()
        if not workspace.completed_through("06-fieldwork"):
            return HTMLResponse(
                f'<p class="note warn">'
                f'{render.e(translator.t("Finish stations 1 to 6 before preparing the field phase."))}'
                "</p>"
            )
        try:
            field_phase.prepare(workspace, fields, language=translator.language)
        except (ValueError, OSError) as error:
            return HTMLResponse(
                f'<p class="note warn">{render.e(translator.t(str(error)))}</p>',
                status_code=200,
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
        workspace = load_workspace()
        summary = field_phase.summary(workspace)
        if summary.get("ready"):
            values = field_phase.values_of(workspace, fields)
            summary["findings_file"] = str(
                values.get("reporting.findings_file") or "findings.md"
            )
        body = render.report_view(summary, translator)
        open_count = len(field_phase.review_cases(workspace))
        if open_count:
            body = (
                f'<p class="note warn"><a href="/reviews?lang={translator.language}">'
                f"{render.e(translator.t('Open review cases:'))} {open_count} — "
                f"{render.e(translator.t('the figures below are provisional until every case is decided.'))}"
                "</a></p>"
            ) + body
        # The report is what a researcher takes away; the browser can write it
        # as a file into the folder they picked, without the host being asked.
        body += huckepack_web.receipt_script_tag(
            {
                "kind": "study-receipt",
                "app": "researchcall",
                "order_id": str(summary.get("study_key") or "study"),
                "business": str(summary.get("title") or "study"),
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "summary": json.dumps(
                    {
                        key: value
                        for key, value in summary.items()
                        if isinstance(value, (str, int, float, bool))
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "third_party_notice": (
                    "Findings rest on answers given by the people who were called."
                ),
            }
        )
        return shell(request, body, translator.t("Report"), "report")

    @app.get("/report.md", response_class=PlainTextResponse)
    async def report_markdown() -> PlainTextResponse:
        workspace = load_workspace()
        if not field_phase.exists(workspace):
            return PlainTextResponse("No field phase has run yet.\n", status_code=404)
        return PlainTextResponse(field_phase.summary(workspace)["report"])

    # --- export ------------------------------------------------------------

    def _exported(builder, media_type: str) -> Any:
        workspace = load_workspace()
        if not field_phase.exists(workspace):
            return PlainTextResponse("No field phase has run yet.\n", status_code=404)
        # Looking at a provisional report is allowed (it says so); exporting a
        # dataset over undecided conflicts is not. An export leaves the room,
        # and the caveat does not travel with a CSV.
        open_count = len(field_phase.review_cases(workspace))
        if open_count:
            return PlainTextResponse(
                f"{open_count} review case(s) are still open. Decide them under "
                f"/reviews before exporting; an exported dataset carries no "
                f"'provisional' banner.\n",
                status_code=409,
            )
        connection, study = field_phase.open_database(workspace)
        try:
            text = builder(connection, study)
        finally:
            connection.close()
        return PlainTextResponse(text, media_type=media_type)

    @app.get("/export/dataset.csv")
    async def export_dataset() -> Any:
        """One row per person, one column per item — the shape every tool reads."""
        return _exported(export.dataset_csv, "text/csv; charset=utf-8")

    @app.get("/export/free-text.csv")
    async def export_free_text() -> Any:
        return _exported(export.free_text_csv, "text/csv; charset=utf-8")

    @app.get("/export/codebook.md", response_class=PlainTextResponse)
    async def export_codebook() -> Any:
        return _exported(export.codebook, "text/markdown; charset=utf-8")

    @app.get("/export/findings.md", response_class=PlainTextResponse)
    async def export_findings() -> Any:
        """The findings note, started from the numbers and left open for the reading."""
        return _exported(export.findings, "text/markdown; charset=utf-8")

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
