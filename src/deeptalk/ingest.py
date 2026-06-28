from __future__ import annotations

import logging

from deeptalk.bus import EventBus
from deeptalk.stt.base import SttLive
from deeptalk.transcript.store import TranscriptStore

log = logging.getLogger(__name__)


async def run_ingest(stt: SttLive, store: TranscriptStore, bus: EventBus) -> None:
    """Consume the STT stream, persist each event, then fan it out on the bus.

    Errors from the STT engine, DB, or bus are logged and the loop continues —
    a single bad event or transient failure does not kill the pipeline.
    """
    async for ev in stt.stream():
        try:
            store.append(ev)
            await bus.publish(ev)
        except Exception:
            log.exception("ingest: failed to persist or publish event, skipping")
