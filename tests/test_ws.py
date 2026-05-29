import asyncio
import contextlib

import pytest
from fastapi.testclient import TestClient

from deeptalk.bus import EventBus
from deeptalk.server.app import create_app, stream_transcript
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore


def test_ws_sends_backlog_for_session(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(TranscriptEvent(session_id="s1", ts=0.0, text="hello", is_final=True))
    store.append(TranscriptEvent(session_id="s1", ts=1.0, text="world", is_final=True))
    app = create_app(store=store, bus=EventBus())
    client = TestClient(app)

    with client.websocket_connect("/ws/transcript?session_id=s1") as ws:
        first = ws.receive_json()
        second = ws.receive_json()

    assert first["text"] == "hello"
    assert second["text"] == "world"
    assert first["session_id"] == "s1"


def test_ws_backlog_filtered_by_session(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(TranscriptEvent(session_id="s1", ts=0.0, text="keep", is_final=True))
    store.append(TranscriptEvent(session_id="s2", ts=0.0, text="drop", is_final=True))
    app = create_app(store=store, bus=EventBus())
    client = TestClient(app)

    with client.websocket_connect("/ws/transcript?session_id=s1") as ws:
        msg = ws.receive_json()

    assert msg["text"] == "keep"
    assert len(store.all_events("s1")) == 1


def test_health_ok(tmp_path):
    app = create_app(store=TranscriptStore(str(tmp_path / "t.db")), bus=EventBus())
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_stream_forwards_live_events_for_session(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))  # empty backlog
    bus = EventBus()
    sent: list[dict] = []

    async def fake_send(payload):
        sent.append(payload)

    task = asyncio.create_task(stream_transcript(fake_send, store, bus, "s1"))
    await asyncio.sleep(0)  # let it send (empty) backlog and subscribe
    await bus.publish(TranscriptEvent(session_id="s1", ts=0.0, text="live", is_final=True))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert [m["text"] for m in sent] == ["live"]


@pytest.mark.asyncio
async def test_stream_filters_live_events_by_session(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    bus = EventBus()
    sent: list[dict] = []

    async def fake_send(payload):
        sent.append(payload)

    task = asyncio.create_task(stream_transcript(fake_send, store, bus, "s1"))
    await asyncio.sleep(0)
    await bus.publish(TranscriptEvent(session_id="s2", ts=0.0, text="other", is_final=True))
    await bus.publish(TranscriptEvent(session_id="s1", ts=1.0, text="mine", is_final=True))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert [m["text"] for m in sent] == ["mine"]


@pytest.mark.asyncio
async def test_stream_sends_backlog_before_live(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(TranscriptEvent(session_id="s1", ts=0.0, text="old", is_final=True))
    bus = EventBus()
    sent: list[dict] = []

    async def fake_send(payload):
        sent.append(payload)

    task = asyncio.create_task(stream_transcript(fake_send, store, bus, "s1"))
    await asyncio.sleep(0)
    await bus.publish(TranscriptEvent(session_id="s1", ts=1.0, text="new", is_final=True))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert [m["text"] for m in sent] == ["old", "new"]
