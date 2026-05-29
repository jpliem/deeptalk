import dataclasses
import pytest
from deeptalk.transcript.events import TranscriptEvent


def test_event_holds_fields_and_defaults():
    ev = TranscriptEvent(session_id="s1", ts=1.5, text="hello", is_final=True)
    assert ev.session_id == "s1"
    assert ev.ts == 1.5
    assert ev.text == "hello"
    assert ev.is_final is True
    assert ev.source == "live"
    assert ev.speaker is None
    assert ev.span_id is None


def test_event_is_immutable():
    ev = TranscriptEvent(session_id="s1", ts=0.0, text="x", is_final=False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.text = "changed"


def test_event_round_trips_through_dict():
    ev = TranscriptEvent(
        session_id="s1", ts=2.0, text="hi", is_final=True, source="diarized", speaker=3, span_id="sp1"
    )
    assert TranscriptEvent.from_dict(ev.to_dict()) == ev
