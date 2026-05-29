from deeptalk.wiki.models import Wiki
from deeptalk.wiki.store import WikiStore


def _wiki(session="s1", topics=None):
    return Wiki(
        session_id=session,
        topics=topics if topics is not None else ["t1"],
        decisions=["d1"],
        action_items=["a1"],
        created_at=1.0,
    )


def test_save_and_get(tmp_path):
    store = WikiStore(str(tmp_path / "w.db"))
    store.save(_wiki())
    got = store.get("s1")
    assert got is not None
    assert got.topics == ["t1"]
    assert got.decisions == ["d1"]
    assert got.action_items == ["a1"]


def test_get_missing_returns_none(tmp_path):
    store = WikiStore(str(tmp_path / "w.db"))
    assert store.get("nope") is None


def test_save_replaces_existing(tmp_path):
    store = WikiStore(str(tmp_path / "w.db"))
    store.save(_wiki(topics=["old"]))
    store.save(_wiki(topics=["new"]))
    assert store.get("s1").topics == ["new"]


def test_persists_across_instances(tmp_path):
    db = str(tmp_path / "w.db")
    WikiStore(db).save(_wiki(topics=["persisted"]))
    assert WikiStore(db).get("s1").topics == ["persisted"]
