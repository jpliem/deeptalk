import pytest

from deeptalk.artifacts.models import Artifact, Citation
from deeptalk.artifacts.store import ArtifactStore


def _artifact(session="s1", id="a1", status="done"):
    return Artifact(
        id=id,
        session_id=session,
        agent="search",
        status=status,
        title="what is X",
        payload={"answer": "X is Y", "citations": [{"title": "T", "url": "https://e.com"}]},
        created_at=123.0,
    )


def test_citation_and_artifact_to_dict():
    c = Citation(title="T", url="https://e.com")
    assert c.title == "T" and c.url == "https://e.com"
    d = _artifact().to_dict()
    assert d["agent"] == "search"
    assert d["payload"]["answer"] == "X is Y"
    assert d["latency_ms"] is None and d["error"] is None


def test_artifact_is_immutable():
    import dataclasses
    a = _artifact()
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.status = "error"


def test_store_append_and_all_in_order(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    store.append(_artifact(id="a1"))
    store.append(_artifact(id="a2"))
    arts = store.all_artifacts("s1")
    assert [a.id for a in arts] == ["a1", "a2"]
    assert all(isinstance(a, Artifact) for a in arts)


def test_store_filters_by_session(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    store.append(_artifact(session="s1", id="keep"))
    store.append(_artifact(session="s2", id="drop"))
    assert [a.id for a in store.all_artifacts("s1")] == ["keep"]


def test_store_round_trips_payload(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    store.append(_artifact())
    got = store.all_artifacts("s1")[0]
    assert got.payload == {"answer": "X is Y", "citations": [{"title": "T", "url": "https://e.com"}]}
    assert got.created_at == 123.0


def test_store_persists_across_instances(tmp_path):
    db = str(tmp_path / "a.db")
    ArtifactStore(db).append(_artifact(id="p1"))
    assert [a.id for a in ArtifactStore(db).all_artifacts("s1")] == ["p1"]
