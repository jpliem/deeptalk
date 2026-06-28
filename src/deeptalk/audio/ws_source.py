from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource


class WebSocketAudioSource(AudioSource):
    """An AudioSource that receives PCM frames pushed from a WebSocket.

    Call ``push(data)`` for each binary message, and ``close()`` when the
    WebSocket disconnects.  ``frames()`` yields the pushed bytes in order
    and stops when the source is closed.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    def push(self, data: bytes) -> None:
        self._queue.put_nowait(data)

    def close(self) -> None:
        self._queue.put_nowait(None)

    async def frames(self) -> AsyncIterator[bytes]:
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                return
            yield chunk
