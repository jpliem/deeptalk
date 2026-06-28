from __future__ import annotations

import asyncio


class CostTracker:
    """Per-session cap on agent invocations. max_calls < 0 means unlimited."""

    def __init__(self, max_calls: int) -> None:
        self._max = max_calls
        self._counts: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def allow(self, session_id: str) -> bool:
        """Return True (and count it) if under the cap; False if the cap is reached."""
        if self._max < 0:
            return True
        async with self._lock:
            used = self._counts.get(session_id, 0)
            if used >= self._max:
                return False
            self._counts[session_id] = used + 1
        return True

    def spent(self, session_id: str) -> int:
        return self._counts.get(session_id, 0)
