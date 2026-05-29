from __future__ import annotations

from deeptalk.bus import EventBus
from deeptalk.stt.base import SttLive
from deeptalk.transcript.store import TranscriptStore


async def run_ingest(stt: SttLive, store: TranscriptStore, bus: EventBus) -> None:
    """Consume the STT stream, persist each event, then fan it out on the bus."""
    async for ev in stt.stream():
        store.append(ev)
        await bus.publish(ev)
