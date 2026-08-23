"""End-to-end check of `demo/lambda_entry.py` against a synthetic Function URL
event -- the same shape AWS Lambda actually sends, so a change that breaks
the adapter (not just the app underneath it) is caught here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi", reason="requires the `web`/`lambda` extra")
pytest.importorskip("mangum", reason="requires the `lambda` extra")


def function_url_event(path: str, method: str = "GET") -> dict[str, Any]:
    """A minimal Lambda Function URL event, payload format 2.0.

    ``path`` may carry a ``?query`` suffix, split out here into
    ``rawQueryString`` -- payload format 2.0 never repeats it inside
    ``rawPath``, and Starlette's routing depends on that split.
    """
    from urllib.parse import parse_qsl, urlsplit

    split = urlsplit(path)
    query_params = dict(parse_qsl(split.query))
    return {
        "version": "2.0",
        "rawPath": split.path,
        "rawQueryString": split.query,
        "queryStringParameters": query_params or None,
        "headers": {"host": "demo.lambda-url.eu-central-1.on.aws"},
        "requestContext": {
            "http": {"method": method, "path": split.path, "sourceIp": "203.0.113.1"},
            "domainName": "demo.lambda-url.eu-central-1.on.aws",
        },
        "isBase64Encoded": False,
    }


class _FakeLambdaContext:
    function_name = "calle-demo-researchcall"
    memory_limit_in_mb = 256
    invoked_function_arn = "arn:aws:lambda:eu-central-1:0:function:calle-demo-researchcall"
    aws_request_id = "test-request-id"


@pytest.fixture
def handler(tmp_path: Path):
    """A fresh handler, seeded into an isolated `tmp_path` per test.

    Not the module-scope `demo.lambda_entry.handler` -- that one seeds into
    the real `tempfile.gettempdir()`, which several test functions here
    would then share and step on each other's `workspace.json`.
    """
    from mangum import Mangum

    from demo.lambda_entry import _build_demo_app as build

    app = build(workspace_dir=tmp_path)
    return Mangum(app, lifespan="off")


def _body(response: dict[str, Any]) -> str:
    return str(response.get("body", ""))


def test_index_shows_the_test_mode_banner(handler) -> None:
    response = handler(function_url_event("/"), _FakeLambdaContext())
    assert response["statusCode"] == 200
    assert "Test mode" in _body(response)
    assert "no real calls" in _body(response)


def test_first_station_shows_the_seeded_example_question(handler) -> None:
    response = handler(function_url_event("/station/01-research-question?lang=en"), _FakeLambdaContext())
    assert response["statusCode"] == 200
    assert "How does the frequency of local bus service" in _body(response)


def test_a_repeat_cold_start_does_not_double_seed(tmp_path: Path) -> None:
    """`_seed_if_empty` is a no-op once test mode is already on."""
    from demo.lambda_entry import _build_demo_app as build
    from researchcall.web.workspace import Workspace

    build(workspace_dir=tmp_path)
    first = Workspace.load(tmp_path)
    assert first.test_mode is True
    build(workspace_dir=tmp_path)
    second = Workspace.load(tmp_path)
    assert second.test_mode is True
    assert second.test_values == first.test_values


def test_unknown_path_is_a_404_not_a_crash(handler) -> None:
    response = handler(function_url_event("/definitely-not-a-route"), _FakeLambdaContext())
    assert response["statusCode"] == 404


def test_building_the_app_never_sets_demo_mode_itself(tmp_path: Path) -> None:
    """The leak lesson from the ringedingeding sibling: this module must never
    touch `DEMO_MODE` -- the real Lambda gets it from its deploy-time
    environment (`infra/deploy_demo_lambda.py::_demo_environment`), not from
    this module, and `LiveCallClient`'s guard (`tests/test_live_guard.py`)
    is the thing that must actually be responsible for the refusal.
    """
    from demo.lambda_entry import _build_demo_app as build

    assert "DEMO_MODE" not in os.environ
    build(workspace_dir=tmp_path)
    assert "DEMO_MODE" not in os.environ
