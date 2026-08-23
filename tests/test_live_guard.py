"""The one thing the public Lambda dry-run demo must never do.

``demo/lambda_entry.py`` deploys with no ``CALLE_API_KEY`` configured, which
already makes ``LiveCallClient.from_environment()`` fail its own api-key
check. This suite proves the second, independent lock: with ``DEMO_MODE=1``
set, ``LiveCallClient`` refuses to be constructed at all -- before the
api-key check, before anything else -- so a future change that starts
passing a real key through would still be refused here.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from researchcall.calls import LiveCallBlocked, LiveCallClient


def test_demo_mode_blocks_even_with_a_real_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    with pytest.raises(LiveCallBlocked):
        LiveCallClient(api_key="a-real-looking-key", base_url="https://api.heycall-e.com")


def test_demo_mode_blocks_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setenv("CALLE_API_KEY", "a-real-looking-key")
    with pytest.raises(LiveCallBlocked):
        LiveCallClient.from_environment()


def test_demo_mode_never_touches_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "1")
    calls = {"count": 0}

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        calls["count"] += 1
        raise AssertionError("urlopen must never be reached while DEMO_MODE=1")

    monkeypatch.setattr(urllib.request, "urlopen", _fail_if_called)
    with pytest.raises(LiveCallBlocked):
        LiveCallClient(api_key="a-real-looking-key", base_url="https://api.heycall-e.com")
    assert calls["count"] == 0


def test_without_demo_mode_the_api_key_check_still_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive control: the guard is DEMO_MODE-specific, not a blanket block."""
    monkeypatch.delenv("DEMO_MODE", raising=False)
    with pytest.raises(ValueError, match="CALLE_API_KEY"):
        LiveCallClient(api_key="", base_url="https://api.heycall-e.com")


def test_without_demo_mode_a_real_key_builds_a_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Positive control: DEMO_MODE=1 is what changes the outcome, nothing else."""
    monkeypatch.delenv("DEMO_MODE", raising=False)
    client = LiveCallClient(api_key="a-real-looking-key", base_url="https://api.heycall-e.com")
    assert client.api_key == "a-real-looking-key"
