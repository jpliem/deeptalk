from fastapi.testclient import TestClient
from deeptalk.server.app import create_app
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore
from deeptalk.bus import EventBus


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
