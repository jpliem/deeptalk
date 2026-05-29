from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from deeptalk.bus import EventBus
from deeptalk.intent.base import IntentDetector
from deeptalk.intent.models import Intent


class Orchestrator:
    """Detects intent on a line, dedups by topic, fires the agent (bounded)."""

    def __init__(
        self,
        detector: IntentDetector,
        fire: Callable[[Intent], Awaitable[None]],
        max_concurrent: int = 3,
    ) -> None:
        self._detector = detector
        self._fire = fire
        self._seen: set[str] = set()
        self._sem = asyncio.Semaphore(max_concurrent)

    async def handle(self, text: str) -> Intent | None:
        intent = await self._detector.detect(text)
        if intent is None or intent.topic in self._seen:
            return None
        self._seen.add(intent.topic)
        async with self._sem:
            await self._fire(intent)
        return intent


async def run_orchestrator(bus: EventBus, orchestrator: Orchestrator, session_id: str) -> None:
    """Consume the transcript bus; handle each final line for this session."""
    q = bus.subscribe()
    try:
        while True:
            ev = await q.get()
            if ev.session_id == session_id and getattr(ev, "is_final", False):
                asyncio.create_task(orchestrator.handle(ev.text))
    finally:
        bus.unsubscribe(q)
