from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class AudioSource(ABC):
    """Yields 16 kHz mono 16-bit PCM byte chunks until the source ends."""

    @abstractmethod
    async def frames(self) -> AsyncIterator[bytes]:
        ...
