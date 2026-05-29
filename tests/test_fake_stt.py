import asyncio
from deeptalk.stt.fake import FakeSttLive
from deeptalk.transcript.events import TranscriptEvent


async def test_fake_yields_events_from_fixture(tmp_path):
    fixture = tmp_path / "f.jsonl"
    fixture.write_text(
        '{"ts": 0.0, "text": "one", "is_final": true}\n'
        '{"ts": 1.0, "text": "two", "is_final": false}\n'
    )
    stt = FakeSttLive(session_id="s1", fixture_path=str(fixture))
    events = [ev async for ev in stt.stream()]
    assert len(events) == 2
    assert all(isinstance(e, TranscriptEvent) for e in events)
    assert events[0].text == "one"
    assert events[0].session_id == "s1"
    assert events[1].is_final is False


async def test_fake_is_fast_when_not_realtime(tmp_path):
    fixture = tmp_path / "f.jsonl"
    fixture.write_text(
        '{"ts": 0.0, "text": "a", "is_final": true}\n'
        '{"ts": 99.0, "text": "b", "is_final": true}\n'
    )
    stt = FakeSttLive(session_id="s1", fixture_path=str(fixture), realtime=False)
    # Large ts gap must NOT cause a real delay when realtime is off.
    events = await asyncio.wait_for(
        _collect(stt), timeout=1.0
    )
    assert [e.text for e in events] == ["a", "b"]


async def _collect(stt):
    return [ev async for ev in stt.stream()]
