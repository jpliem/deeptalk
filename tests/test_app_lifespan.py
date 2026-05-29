from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from deeptalk.bus import EventBus
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def test_create_app_runs_lifespan(tmp_path):
    started = {"value": False}

    @asynccontextmanager
    async def _lifespan(app):
        started["value"] = True
        yield

    store = TranscriptStore(str(tmp_path / "t.db"))
    app = create_app(store=store, bus=EventBus(), lifespan=_lifespan)

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
    assert started["value"] is True


def test_create_app_without_lifespan_still_works(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    app = create_app(store=store, bus=EventBus())
    client = TestClient(app)
    assert client.get("/health").status_code == 200
