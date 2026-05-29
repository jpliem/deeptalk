import asyncio

from deeptalk.intent.heuristic import HeuristicIntentDetector
from deeptalk.intent.models import Intent
from deeptalk.orchestrator import Orchestrator, run_orchestrator
from deeptalk.bus import EventBus
from deeptalk.transcript.events import TranscriptEvent


class _RecordingDetector:
    def __init__(self, intent):
        self._intent = intent

    async def detect(self, text):
        return self._intent


async def test_handle_fires_on_intent(tmp_path):
    fired = []
    intent = Intent(kind="search", query="q", topic="q")

    async def fire(i):
        fired.append(i.query)

    orch = Orchestrator(_RecordingDetector(intent), fire=fire)
    result = await orch.handle("anything")
    assert result is intent
    assert fired == ["q"]


async def test_handle_dedups_by_topic():
    fired = []
    intent = Intent(kind="search", query="postgres or sqlite", topic="postgres or sqlite")

    async def fire(i):
        fired.append(i.query)

    orch = Orchestrator(_RecordingDetector(intent), fire=fire)
    await orch.handle("line one")
    second = await orch.handle("line two")  # same topic
    assert second is None
    assert fired == ["postgres or sqlite"]


async def test_handle_skips_when_no_intent():
    fired = []

    async def fire(i):
        fired.append(i)

    orch = Orchestrator(_RecordingDetector(None), fire=fire)
    assert await orch.handle("just chatting") is None
    assert fired == []


async def test_run_orchestrator_fires_on_final_transcript_line():
    bus = EventBus()
    fired = []
    intent = Intent(kind="search", query="q", topic="q")

    async def fire(i):
        fired.append(i.query)

    orch = Orchestrator(_RecordingDetector(intent), fire=fire)
    task = asyncio.create_task(run_orchestrator(bus, orch, "s1"))
    await asyncio.sleep(0)
    await bus.publish(TranscriptEvent(session_id="s1", ts=0.0, text="should we X?", is_final=True))
    await asyncio.sleep(0.05)
    task.cancel()
    import contextlib
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert fired == ["q"]


async def test_run_orchestrator_ignores_non_final_and_other_sessions():
    bus = EventBus()
    fired = []
    intent = Intent(kind="search", query="q", topic="q")

    async def fire(i):
        fired.append(i.query)

    orch = Orchestrator(_RecordingDetector(intent), fire=fire)
    task = asyncio.create_task(run_orchestrator(bus, orch, "s1"))
    await asyncio.sleep(0)
    await bus.publish(TranscriptEvent(session_id="s1", ts=0.0, text="x", is_final=False))
    await bus.publish(TranscriptEvent(session_id="s2", ts=0.0, text="x?", is_final=True))
    await asyncio.sleep(0.05)
    task.cancel()
    import contextlib
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert fired == []
