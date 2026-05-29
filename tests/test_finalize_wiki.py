from fastapi.testclient import TestClient

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.diarize.fake import FakeDiarizer
from deeptalk.diarize.models import DiarizedSegment
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter
from deeptalk.server.app import create_app
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore
from deeptalk.wiki.store import WikiStore


def _deps(tmp_path, diarizer=None, recording=None):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(TranscriptEvent(session_id="s1", ts=0.0, text="should we use postgres", is_final=True))
    astore = ArtifactStore(str(tmp_path / "a.db"))
    astore.append(Artifact(id="x", session_id="s1", agent="search", status="done", title="postgres", payload={}, created_at=0.0))
    return {
        "store": store,
        "bus": EventBus(),
        "artifact_store": astore,
        "artifact_bus": EventBus(),
        "router": ModelRouter(providers={"fake": FakeLlmProvider()}, routes={"wiki": ["fake"]}, default=["fake"]),
        "wiki_store": WikiStore(str(tmp_path / "w.db")),
        "diarizer": diarizer,
        "recording_path": recording,
    }


def test_finalize_builds_and_persists_wiki(tmp_path):
    deps = _deps(tmp_path)
    app = create_app(**deps)
    client = TestClient(app)

    resp = client.post("/finalize", json={"session_id": "s1"})
    assert resp.status_code == 200

    wiki = client.get("/wiki?session_id=s1").json()
    assert "topics" in wiki and "decisions" in wiki and "action_items" in wiki
    assert wiki["topics"] == ["fake topic"]


def test_wiki_404_when_absent(tmp_path):
    deps = _deps(tmp_path)
    app = create_app(**deps)
    client = TestClient(app)
    assert client.get("/wiki?session_id=never").status_code == 404


def test_finalize_diarizes_when_recording_present(tmp_path):
    rec = tmp_path / "rec.wav"
    rec.write_bytes(b"")  # presence is enough; FakeDiarizer ignores contents
    segs = [DiarizedSegment(speaker=2, start=0.0, end=1.0, text="diarized line")]
    deps = _deps(tmp_path, diarizer=FakeDiarizer(segs), recording=str(rec))
    app = create_app(**deps)
    client = TestClient(app)

    client.post("/finalize", json={"session_id": "s1"})

    events = deps["store"].all_events("s1")
    diarized = [e for e in events if e.source == "diarized"]
    assert len(diarized) == 1
    assert diarized[0].speaker == 2
    assert diarized[0].text == "diarized line"
