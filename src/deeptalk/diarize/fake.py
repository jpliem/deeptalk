from __future__ import annotations

from deeptalk.diarize.models import DiarizedSegment


class FakeDiarizer:
    """Returns canned segments — for dev/tests without a GPU."""

    def __init__(self, segments: list[DiarizedSegment]) -> None:
        self._segments = segments

    async def diarize(self, audio_path: str) -> list[DiarizedSegment]:
        return list(self._segments)
