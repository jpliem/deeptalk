import time

from fastapi.testclient import TestClient

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def _deps(tmp_path):
    return {
        "store": TranscriptStore(str(tmp_path / "t.db")),
        "bus": EventBus(),
        "artifact_store": ArtifactStore(str(tmp_path / "a.db")),
        "artifact_bus": EventBus(),
        "router": ModelRouter(
            providers={"fake": FakeLlmProvider()},
            routes={"search": ["fake"]},
            default=["fake"],
        ),
    }


def _artifact(session="s1", id="a1"):
    return Artifact(
        id=id, session_id=session, agent="search", status="done",
        title="q", payload={"answer": "a", "citations": []}, created_at=time.time(),
    )


def test_artifacts_ws_sends_backlog(tmp_path):
    deps = _deps(tmp_path)
    deps["artifact_store"].append(_artifact(id="a1"))
    deps["artifact_store"].append(_artifact(id="a2"))
    app = create_app(**deps)
    client = TestClient(app)

    with client.websocket_connect("/ws/artifacts?session_id=s1") as ws:
        first = ws.receive_json()
        second = ws.receive_json()

    assert first["id"] == "a1"
    assert second["id"] == "a2"
    assert first["agent"] == "search"


def test_artifacts_ws_filters_by_session(tmp_path):
    deps = _deps(tmp_path)
    deps["artifact_store"].append(_artifact(session="s1", id="keep"))
    deps["artifact_store"].append(_artifact(session="s2", id="drop"))
    app = create_app(**deps)
    client = TestClient(app)

    with client.websocket_connect("/ws/artifacts?session_id=s1") as ws:
        msg = ws.receive_json()

    assert msg["id"] == "keep"
