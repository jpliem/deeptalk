from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from deeptalk.audio.base import AudioSource


class WebsocketAudioSource(AudioSource):
    """An audio source that yields PCM frames pushed from a WebSocket connection."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def put_frame(self, data: bytes) -> None:
        self._queue.put_nowait(data)

    def close(self) -> None:
        self._queue.put_nowait(None)

    async def frames(self) -> AsyncIterator[bytes]:
        while True:
            frame = await self._queue.get()
            if frame is None:
                break
            yield frame
