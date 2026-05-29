from __future__ import annotations

from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource
from deeptalk.stt.base import SttLive
from deeptalk.stt.recognizer import StreamingRecognizer
from deeptalk.transcript.events import TranscriptEvent


class NemotronSttLive(SttLive):
    """Streams TranscriptEvents from an AudioSource via a StreamingRecognizer.

    All orchestration (frame loop, event construction, timing) lives here and is
    testable with a fake recognizer. The real model is injected as `recognizer`.
    """

    def __init__(
        self,
        session_id: str,
        audio_source: AudioSource,
        recognizer: StreamingRecognizer,
        chunk_ms: int = 80,
    ) -> None:
        self._session_id = session_id
        self._audio = audio_source
        self._recognizer = recognizer
        self._chunk_ms = chunk_ms

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        elapsed = 0.0
        async for frame in self._audio.frames():
            text = self._recognizer.transcribe_chunk(frame)
            if text:
                yield TranscriptEvent(
                    session_id=self._session_id,
                    ts=round(elapsed, 3),
                    text=text,
                    is_final=True,
                    source="live",
                )
            elapsed += self._chunk_ms / 1000.0
