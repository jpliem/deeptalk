import io
import math
import struct
import wave

from fastapi.testclient import TestClient

from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def _wav_bytes(seconds=0.1, rate=16000):
    n = int(rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(struct.pack("<h", int(1000 * math.sin(i / 5))) for i in range(n)))
    return buf.getvalue()


def test_upload_transcribes_into_session(tmp_path):
    cfg = Config.from_env({"DEEPTALK_STT": "fake", "DEEPTALK_SESSION_ID": "demo"})
    store = TranscriptStore(str(tmp_path / "t.db"))
    app = create_app(store=store, bus=EventBus(), config=cfg)
    client = TestClient(app)

    resp = client.post(
        "/upload?session_id=demo",
        files={"file": ("clip.wav", _wav_bytes(), "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json()["events"] >= 1
    assert len(store.all_events("demo")) >= 1


def test_upload_503_without_config(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    app = create_app(store=store, bus=EventBus())
    client = TestClient(app)
    resp = client.post("/upload", files={"file": ("c.wav", _wav_bytes(), "audio/wav")})
    assert resp.status_code == 503
