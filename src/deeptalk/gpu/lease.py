from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class GpuLease:
    """Single-slot async lease. Serializes GPU-heavy sections so only one runs at a
    time on a memory-constrained card (prevents co-loading models into OOM)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def hold(self) -> AsyncIterator[None]:
        async with self._lock:
            yield
