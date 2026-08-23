"""AWS Lambda Function URL entry point for the public researchcall dry-run demo.

Mangum wraps the same FastAPI app `researchcall.web.app.create_app()` builds
for local use (`python -m researchcall.web.app` / `researchcall-web`); this
module only decides *where that app's state lives* on a Lambda's read-only
filesystem and seeds it once at cold start so a visitor sees a filled-in
example study rather than eight empty stations.

What this deployment must never do
-----------------------------------
Place a real call. Two independent things make that structurally impossible,
and losing either one alone still leaves the other standing:

1. `infra/deploy_demo_lambda.py::_demo_environment()` sets exactly
   `{"DEMO_MODE": "1"}` as this function's entire environment -- no
   `CALLE_API_KEY`, no `CALLE_BASE_URL`. `researchcall.calls.LiveCallClient`
   reads its key from the environment (`from_environment()`), so there is
   simply no credential here for it to spend.
2. `LiveCallClient.__init__` checks `os.environ.get("DEMO_MODE") == "1"`
   before its own api-key check and refuses unconditionally (raises
   `LiveCallBlocked`) if it is set. Proven in `tests/test_live_guard.py`
   ("demo mode"), including a test that patches `urllib.request.urlopen` to
   fail the test if it is ever called.

A third fact, weaker than the two above but worth stating plainly: the web
application this module wraps has *no route* that ever constructs a
`LiveCallClient` in the first place -- `create_app()`'s own FastAPI
description says so ("Dry run only -- this interface cannot place a call"),
and the only place `LiveCallClient` is built in this whole codebase is
`cli.py`'s `run-day --live` command, which this Lambda never runs. Guard (2)
exists anyway, so that stays true even after some future change to the web
app forgets it.

The `DEMO_MODE` leak lesson (do not repeat it here)
-----------------------------------------------------
An earlier version of the equivalent module in the `ringedingeding` sibling
project set `DEMO_MODE` itself via `os.environ.setdefault(...)`. Under
pytest, module-scope environment mutations survive past the importing test
file for the rest of the collection, and leaked `DEMO_MODE=1` into unrelated
tests that build a live client with a real-looking key and expect it to
succeed. This module deliberately never touches `DEMO_MODE` at all: the real
Lambda gets it from its deploy-time environment configuration (see (1)
above), and `tests/test_lambda_entry.py` sets it only for the duration of one
test function via a scoped, restoring `pytest` fixture.

What a judge sees on a cold start
-----------------------------------
`researchcall/web/test_mode.py` already ships a first-class, reviewed fixture
tour: a fictional local-bus-service study, in English or German, that opens
every one of the eight stations at once, marked with its own on-page banner
("Test mode -- example data, not a real study ... network disabled, fixture
transport, no real calls"). That tour is normally one click away
(`/test-mode/toggle`). `_seed_if_empty` below turns it on once, at cold
start, on the English table -- so the click a visitor would make anyway is
already done for them, on the exact code path the workbench itself uses.

Ephemeral by design
--------------------
The workspace lives under `tempfile.gettempdir()` (Lambda's only writable
path), which is wiped whenever AWS recycles the execution environment. There
is no persistent store here, and there is not meant to be one -- see
`infra/README.md`.
"""

from __future__ import annotations

import pathlib
import tempfile
from typing import Any

from mangum import Mangum

from researchcall.web import test_mode
from researchcall.web.app import create_app
from researchcall.web.workspace import Workspace

DEMO_WORKSPACE_NAME = "researchcall-demo-workspace"
DEMO_FIXTURE_LANGUAGE = "en"


def _workspace_dir() -> pathlib.Path:
    return pathlib.Path(tempfile.gettempdir()) / DEMO_WORKSPACE_NAME


def _pipeline_root() -> pathlib.Path:
    """`pipeline/`, packaged as a sibling of `demo/` and `researchcall/` at the
    zip root -- see `infra/deploy_demo_lambda.py::cmd_package`.

    Passed explicitly rather than left to `researchcall.forms.PIPELINE_ROOT`'s
    own default (`Path(__file__).resolve().parents[2] / "pipeline"`), because
    that default assumes this repo's `src/researchcall/forms.py` nesting
    depth, which the flat Lambda zip layout does not reproduce.
    """
    return pathlib.Path(__file__).resolve().parent.parent / "pipeline"


def _seed_if_empty(workspace_dir: pathlib.Path, fields: list[Any]) -> None:
    """Turn on the workbench's own test mode for a fresh cold start.

    A no-op if the workspace already has test mode on (a warm Lambda
    execution environment serving a second request, or an earlier request
    that already seeded this same `/tmp`). Broad `except Exception` on
    purpose: a seeding failure must never take the homepage down with it --
    a visitor who lands on an unseeded, empty workbench can still turn test
    mode on themselves with the page's own button.
    """
    try:
        workspace = Workspace.load(workspace_dir)
        if workspace.test_mode:
            return
        workspace.enable_test_mode(
            test_mode.example_values(fields, DEMO_FIXTURE_LANGUAGE),
            DEMO_FIXTURE_LANGUAGE,
        )
        workspace.save()
    except Exception:
        pass


def _build_demo_app(workspace_dir: pathlib.Path | None = None):
    """Build the same app `create_app()` always builds, seeded once.

    `workspace_dir` is a parameter (not an environment variable) precisely so
    `tests/test_lambda_entry.py` can point this at an isolated `tmp_path`
    without any process-wide state to leak or restore.
    """
    directory = workspace_dir or _workspace_dir()
    app = create_app(workspace_dir=directory, forms_root=_pipeline_root())
    _seed_if_empty(directory, app.state.fields)
    return app


handler = Mangum(_build_demo_app(), lifespan="off")
