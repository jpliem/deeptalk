from __future__ import annotations

from typing import Protocol, runtime_checkable

from deeptalk.diarize.models import DiarizedSegment


@runtime_checkable
class Diarizer(Protocol):
    async def diarize(self, audio_path: str) -> list[DiarizedSegment]:
        """Transcribe + diarize a WAV file into speaker-labelled segments."""
        ...
