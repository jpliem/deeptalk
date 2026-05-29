from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    """In-process fan-out. Each subscriber gets its own queue."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Any]] = []

    def subscribe(self) -> asyncio.Queue[Any]:
        q: asyncio.Queue[Any] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Any]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, item: Any) -> None:
        for q in list(self._subscribers):
            await q.put(item)
