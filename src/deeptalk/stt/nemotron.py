from __future__ import annotations

import asyncio
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
        current_phrase = ""
        last_text_ts = None
        start_ts = None
        
        # Pause threshold in seconds (e.g. 1.2 seconds of silence finishes a phrase)
        pause_threshold = 1.2

        try:
            async for frame in self._audio.frames():
                text = await asyncio.to_thread(self._recognizer.transcribe_chunk, frame)
                if text:
                    text = text.strip()
                    if text and text != current_phrase:
                        if not current_phrase:
                            start_ts = elapsed
                        current_phrase = text
                        last_text_ts = elapsed
                
                # Check for silence/pause to finalize the current phrase
                if current_phrase and last_text_ts is not None:
                    silence_duration = elapsed - last_text_ts
                    if silence_duration >= pause_threshold:
                        yield TranscriptEvent(
                            session_id=self._session_id,
                            ts=round(start_ts or 0.0, 3),
                            text=current_phrase,
                            is_final=True,
                            source="live",
                        )
                        # Reset the cache-aware recognizer to start a fresh new phrase
                        if hasattr(self._recognizer, "reset"):
                            self._recognizer.reset()
                        current_phrase = ""
                        last_text_ts = None
                        start_ts = None

                elapsed += self._chunk_ms / 1000.0
        finally:
            # Yield any remaining text when the audio source closes
            if current_phrase:
                yield TranscriptEvent(
                    session_id=self._session_id,
                    ts=round(start_ts or 0.0, 3),
                    text=current_phrase,
                    is_final=True,
                    source="live",
                )
                if hasattr(self._recognizer, "reset"):
                    self._recognizer.reset()
