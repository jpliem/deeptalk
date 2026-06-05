from __future__ import annotations

import asyncio
import logging
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
        max_detect_concurrent: int = 5,
    ) -> None:
        self._detector = detector
        self._fire = fire
        self._seen: set[str] = set()
        self._sem = asyncio.Semaphore(max_concurrent)
        self._detect_sem = asyncio.Semaphore(max_detect_concurrent)

    async def handle(self, text: str) -> Intent | None:
        async with self._detect_sem:
            intent = await self._detector.detect(text)
        if intent is None or intent.topic in self._seen:
            return None
        self._seen.add(intent.topic)
        async with self._sem:
            await self._fire(intent)
        return intent


_log = logging.getLogger("deeptalk.orchestrator")


async def run_orchestrator(bus: EventBus, orchestrator: Orchestrator, session_id: str) -> None:
    """Consume the transcript bus; handle each final line for this session."""
    q = bus.subscribe()
    tasks: set[asyncio.Task] = set()

    def _on_done(task: asyncio.Task) -> None:
        tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            _log.warning("orchestrator handle failed: %r", task.exception())

    try:
        while True:
            ev = await q.get()
            if ev.session_id == session_id and getattr(ev, "is_final", False):
                task = asyncio.create_task(orchestrator.handle(ev.text))
                tasks.add(task)
                task.add_done_callback(_on_done)
    finally:
        bus.unsubscribe(q)
        for task in tasks:
            task.cancel()
