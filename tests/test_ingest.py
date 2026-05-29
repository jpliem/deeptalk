import asyncio
from deeptalk.bus import EventBus
from deeptalk.ingest import run_ingest
from deeptalk.stt.fake import FakeSttLive
from deeptalk.transcript.store import TranscriptStore


async def test_ingest_persists_all_events(tmp_path):
    fixture = tmp_path / "f.jsonl"
    fixture.write_text(
        '{"ts": 0.0, "text": "alpha", "is_final": true}\n'
        '{"ts": 1.0, "text": "beta", "is_final": true}\n'
    )
    store = TranscriptStore(str(tmp_path / "t.db"))
    bus = EventBus()
    stt = FakeSttLive(session_id="s1", fixture_path=str(fixture))

    await run_ingest(stt, store, bus)

    assert [e.text for e in store.all_events("s1")] == ["alpha", "beta"]


async def test_ingest_publishes_each_event_on_bus(tmp_path):
    fixture = tmp_path / "f.jsonl"
    fixture.write_text('{"ts": 0.0, "text": "alpha", "is_final": true}\n')
    store = TranscriptStore(str(tmp_path / "t.db"))
    bus = EventBus()
    q = bus.subscribe()
    stt = FakeSttLive(session_id="s1", fixture_path=str(fixture))

    await run_ingest(stt, store, bus)

    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received.text == "alpha"
