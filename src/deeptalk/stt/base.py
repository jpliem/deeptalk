from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from deeptalk.transcript.events import TranscriptEvent


class SttLive(ABC):
    """A live speech-to-text source that yields transcript events as they arrive."""

    @abstractmethod
    def stream(self) -> AsyncIterator[TranscriptEvent]:
        """Async-iterate transcript events until the source ends."""
        raise NotImplementedError
