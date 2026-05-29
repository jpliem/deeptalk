from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StreamingRecognizer(Protocol):
    """Decodes successive PCM chunks into incremental text.

    Implementations maintain their own streaming state across calls.
    """

    def transcribe_chunk(self, pcm: bytes) -> str:
        """Return newly decoded text for this chunk ('' if none)."""
        ...
