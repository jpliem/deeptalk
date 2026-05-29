from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore


def _ev(text, ts, session="s1", is_final=True):
    return TranscriptEvent(session_id=session, ts=ts, text=text, is_final=is_final)


def test_append_returns_increasing_seq(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    seq1 = store.append(_ev("a", 0.0))
    seq2 = store.append(_ev("b", 1.0))
    assert seq2 > seq1


def test_all_events_returns_in_insertion_order(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(_ev("first", 0.0))
    store.append(_ev("second", 1.0))
    events = store.all_events("s1")
    assert [e.text for e in events] == ["first", "second"]
    assert all(isinstance(e, TranscriptEvent) for e in events)


def test_all_events_filters_by_session(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(_ev("keep", 0.0, session="s1"))
    store.append(_ev("drop", 0.0, session="s2"))
    assert [e.text for e in store.all_events("s1")] == ["keep"]


def test_round_trip_preserves_all_fields(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    ev = TranscriptEvent(
        session_id="s1", ts=2.5, text="hi", is_final=False,
        source="diarized", speaker=2, span_id="sp9",
    )
    store.append(ev)
    assert store.all_events("s1")[0] == ev


def test_data_persists_across_instances(tmp_path):
    db = str(tmp_path / "t.db")
    TranscriptStore(db).append(_ev("persisted", 0.0))
    assert [e.text for e in TranscriptStore(db).all_events("s1")] == ["persisted"]
