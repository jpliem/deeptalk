from fastapi.testclient import TestClient

from deeptalk.bus import EventBus
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def _store(tmp_path):
    return TranscriptStore(str(tmp_path / "t.db"))


def test_serves_ui_index_when_dir_given(tmp_path):
    ui = tmp_path / "dist"
    ui.mkdir()
    (ui / "index.html").write_text("<h1>DeepTalk UI</h1>")
    app = create_app(store=_store(tmp_path), bus=EventBus(), ui_dir=str(ui))
    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert "DeepTalk UI" in root.text


def test_api_routes_not_shadowed_by_ui_mount(tmp_path):
    ui = tmp_path / "dist"
    ui.mkdir()
    (ui / "index.html").write_text("<h1>UI</h1>")
    app = create_app(store=_store(tmp_path), bus=EventBus(), ui_dir=str(ui))
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}


def test_no_ui_when_dir_missing(tmp_path):
    app = create_app(store=_store(tmp_path), bus=EventBus(), ui_dir=str(tmp_path / "nope"))
    client = TestClient(app)

    assert client.get("/").status_code == 404
    assert client.get("/health").status_code == 200
