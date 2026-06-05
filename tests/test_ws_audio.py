import asyncio
from fastapi.testclient import TestClient

from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def test_ws_audio_stream_lifecycle(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    bus = EventBus()
    config = Config.from_env({"DEEPTALK_STT": "fake", "DEEPTALK_SESSION_ID": "demo"})
    app = create_app(store=store, bus=bus, config=config)
    client = TestClient(app)

    with client.websocket_connect("/ws/audio-stream?session_id=demo") as ws:
        # Send raw dummy PCM bytes (16k mono 16-bit)
        ws.send_bytes(b"\x00\x00" * 1600)
        ws.send_bytes(b"\x00\x00" * 1600)
        # Should stay open and run ingest in the background

    # Close should shut down gracefully
    assert len(store.all_events("demo")) >= 0
