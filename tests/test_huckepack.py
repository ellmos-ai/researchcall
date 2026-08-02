"""The huckepack modes: what is promised, verified.

ResearchCall keeps two things, not one: the study database *and* the workbench
file with the answers to the eight stations. A pattern that relocated only the
database would leave the second half on the host's disk and in no backup — so
the workbench file is tested here as carefully as the database.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# The package lives under src/ and the suite runs without an install — the same
# two lines every other test module here uses.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytest.importorskip("fastapi", reason="the web interface is an optional extra")

from fastapi.testclient import TestClient  # noqa: E402

from researchcall import huckepack_key, huckepack_storage, server_mode  # noqa: E402
from researchcall.database import connect, initialize  # noqa: E402
from researchcall.huckepack_storage import SESSIONS, SnapshotError  # noqa: E402
from researchcall.huckepack_web import SESSION_HEADER  # noqa: E402
from researchcall.server_mode import ServerMode, ServerModeError  # noqa: E402
from researchcall.web.app import create_app  # noqa: E402
from researchcall.web.workspace import Workspace  # noqa: E402

TOKEN = "AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
OTHER_TOKEN = "BBBBBBBBBBBBBBBBBBBBBBBBBBBB"
VISITOR_KEY = "sk-visitor-9999-abcdefgh"


@pytest.fixture(autouse=True)
def clean_slate(monkeypatch):
    monkeypatch.delenv(server_mode.ENV_VAR, raising=False)
    server_mode.reset_mode_cache()
    SESSIONS.clear()
    yield
    SESSIONS.clear()
    server_mode.reset_mode_cache()


def use_mode(monkeypatch, mode: str) -> None:
    monkeypatch.setenv(server_mode.ENV_VAR, mode)
    server_mode.reset_mode_cache()


# ---------------------------------------------------------------- the mode

def test_unset_means_local():
    assert server_mode.current_mode() is ServerMode.LOCAL


@pytest.mark.parametrize(
    "name,browser,key_field",
    [
        ("local", False, False),
        ("huckepack-gift", True, False),
        ("huckepack-only-host", True, True),
        ("pay-membership", False, False),
    ],
)
def test_every_mode_decides_storage_and_key(monkeypatch, name, browser, key_field):
    use_mode(monkeypatch, name)
    mode = server_mode.current_mode()
    assert mode.stores_in_browser is browser
    assert mode.key_from_browser is key_field


def test_an_unknown_mode_is_refused_by_name():
    with pytest.raises(ServerModeError) as error:
        server_mode.parse_mode("huckepack-someday")
    assert "huckepack-someday" in str(error.value)


# ------------------------------------------------------------- the storage

def test_local_mode_writes_the_file_as_before(monkeypatch, tmp_path):
    use_mode(monkeypatch, "local")
    path = tmp_path / "study.db"
    initialize(path)
    assert path.exists()


@pytest.mark.parametrize("mode", ["huckepack-gift", "huckepack-only-host"])
def test_a_huckepack_mode_never_creates_the_database_file(monkeypatch, tmp_path, mode):
    use_mode(monkeypatch, mode)
    path = tmp_path / "study.db"
    reset = huckepack_storage.bind_session(TOKEN)
    try:
        initialize(path)
        connection = connect(path)
        connection.execute(
            "INSERT INTO study (study_key, title, questionnaire_json, created_at) "
            "VALUES ('s1', 'Fieldwork', '{}', '2026-08-02')"
        )
        connection.commit()
        titles = [
            row[0] for row in SESSIONS.connection(TOKEN).execute("SELECT title FROM study")
        ]
    finally:
        huckepack_storage.unbind_session(reset)

    assert titles == ["Fieldwork"]
    assert not path.exists()


def test_two_sessions_do_not_see_each_other(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-gift")
    for token, title in ((TOKEN, "First"), (OTHER_TOKEN, "Second")):
        reset = huckepack_storage.bind_session(token)
        try:
            initialize(tmp_path / "study.db")
            connection = connect(tmp_path / "study.db")
            connection.execute(
                "INSERT INTO study (study_key, title, questionnaire_json, created_at) "
                "VALUES (?, ?, '{}', '2026-08-02')",
                (token[:4], title),
            )
            connection.commit()
        finally:
            huckepack_storage.unbind_session(reset)

    def titles(token):
        return [row[0] for row in SESSIONS.connection(token).execute("SELECT title FROM study")]

    assert titles(TOKEN) == ["First"]
    assert titles(OTHER_TOKEN) == ["Second"]


def test_a_snapshot_that_is_not_a_database_is_refused():
    with pytest.raises(SnapshotError):
        SESSIONS.load(TOKEN, b"a text file, not a database")


# --------------------------------------------------- the workbench file

def test_the_workbench_file_stays_off_the_host_disk(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-gift")
    reset = huckepack_storage.bind_session(TOKEN)
    try:
        workspace = Workspace.load(tmp_path / "workspace")
        workspace.values["research_question"] = "Does it hold?"
        workspace.save()

        again = Workspace.load(tmp_path / "workspace")
    finally:
        huckepack_storage.unbind_session(reset)

    assert again.values["research_question"] == "Does it hold?"
    assert not (tmp_path / "workspace").exists(), "not even the directory should appear"


def test_the_workbench_file_travels_inside_the_snapshot(monkeypatch, tmp_path):
    """A backup that restores the database but not the answers is not a backup."""
    use_mode(monkeypatch, "huckepack-only-host")
    reset = huckepack_storage.bind_session(TOKEN)
    try:
        workspace = Workspace.load(tmp_path / "workspace")
        workspace.values["research_question"] = "Does it travel?"
        workspace.save()
        blob = huckepack_storage.snapshot_for_current_session()
    finally:
        huckepack_storage.unbind_session(reset)

    SESSIONS.load(OTHER_TOKEN, blob)
    reset = huckepack_storage.bind_session(OTHER_TOKEN)
    try:
        restored = Workspace.load(tmp_path / "workspace")
    finally:
        huckepack_storage.unbind_session(reset)
    assert restored.values["research_question"] == "Does it travel?"


def test_local_mode_still_writes_the_workbench_file(monkeypatch, tmp_path):
    use_mode(monkeypatch, "local")
    workspace = Workspace.load(tmp_path / "workspace")
    workspace.values["research_question"] = "On disk?"
    workspace.save()
    assert (tmp_path / "workspace" / "workspace.json").exists()


# ------------------------------------------------------------------ the key

def test_a_key_is_only_ever_shown_masked():
    assert huckepack_key.mask_key(VISITOR_KEY) == "••••efgh"
    assert VISITOR_KEY not in huckepack_key.describe_key(VISITOR_KEY)


def test_local_and_gift_leave_the_environment_in_charge(monkeypatch):
    for name in ("local", "huckepack-gift"):
        use_mode(monkeypatch, name)
        assert huckepack_key.credential_override() is None


def test_only_host_takes_the_visitors_key_and_never_the_hosts(monkeypatch):
    use_mode(monkeypatch, "huckepack-only-host")
    monkeypatch.setenv("CALLE_API_KEY", "host-key-that-must-not-be-spent")
    with pytest.raises(huckepack_key.UserKeyError):
        huckepack_key.credential_override()

    reset = huckepack_key.bind_request_key(VISITOR_KEY)
    try:
        from researchcall.calls import LiveCallClient

        client = LiveCallClient.from_environment()
        assert client.api_key == VISITOR_KEY
    finally:
        huckepack_key.unbind_request_key(reset)


# ------------------------------------------------------------------ the web

def test_the_browser_is_told_what_kind_of_installation_this_is(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-only-host")
    with TestClient(create_app(tmp_path / "workspace")) as client:
        payload = client.get("/huckepack/mode").json()
    assert payload["mode"] == "huckepack-only-host"
    assert payload["storage"] == "browser"
    assert payload["key_field"] is True


def test_a_snapshot_can_be_handed_in_and_taken_back(monkeypatch, tmp_path):
    use_mode(monkeypatch, "huckepack-gift")
    seed = sqlite3.connect(":memory:")
    seed.execute("CREATE TABLE study (title TEXT)")
    seed.execute("INSERT INTO study VALUES ('Fieldwork')")
    seed.commit()

    with TestClient(create_app(tmp_path / "workspace")) as client:
        assert client.put(
            "/huckepack/session", content=seed.serialize(), headers={SESSION_HEADER: TOKEN}
        ).status_code == 200
        fetched = client.get("/huckepack/session", headers={SESSION_HEADER: TOKEN})

    back = sqlite3.connect(":memory:")
    back.deserialize(fetched.content)
    assert back.execute("SELECT title FROM study").fetchall() == [("Fieldwork",)]


def test_local_mode_has_no_browser_snapshot(monkeypatch, tmp_path):
    use_mode(monkeypatch, "local")
    with TestClient(create_app(tmp_path / "workspace")) as client:
        response = client.get("/huckepack/session", headers={SESSION_HEADER: TOKEN})
    assert response.status_code == 409


def test_the_stub_mode_says_so_instead_of_serving_pages(monkeypatch, tmp_path):
    use_mode(monkeypatch, "pay-membership")
    with TestClient(create_app(tmp_path / "workspace")) as client:
        assert client.get("/").status_code == 503
        assert client.get("/huckepack/mode").json()["implemented"] is False


def test_the_browser_half_is_shipped_and_never_prints_the_key():
    from pathlib import Path

    script = (
        Path(__file__).resolve().parents[1]
        / "src" / "researchcall" / "web" / "static" / "huckepack.js"
    ).read_text(encoding="utf-8")
    for needed in ("receiptFilename", "maskKey", "looksLikeSqlite", "showDirectoryPicker"):
        assert needed in script
    assert "console." not in script
    assert "researchcall_" in script
