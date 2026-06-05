from __future__ import annotations

import wave
from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource


class FileAudioSource(AudioSource):
    """Reads a 16 kHz mono 16-bit WAV file and yields fixed-size PCM chunks.

    For dev and tests on machines without a usable microphone.
    """

    def __init__(
        self,
        path: str,
        chunk_ms: int = 80,
        sample_rate: int = 16000,
        realtime: bool = False,
    ) -> None:
        self._path = path
        self._chunk_ms = chunk_ms
        self._sample_rate = sample_rate
        self._realtime = realtime

    async def frames(self) -> AsyncIterator[bytes]:
        import asyncio

        with wave.open(self._path, "rb") as wf:
            if wf.getnchannels() != 1:
                raise ValueError("audio must be mono")
            if wf.getframerate() != self._sample_rate:
                raise ValueError(f"audio must be {self._sample_rate} Hz")
            if wf.getsampwidth() != 2:
                raise ValueError("audio must be 16-bit PCM")
            frames_per_chunk = int(self._sample_rate * self._chunk_ms / 1000)
            while True:
                if self._realtime:
                    await asyncio.sleep(self._chunk_ms / 1000.0)
                data = wf.readframes(frames_per_chunk)
                if not data:
                    break
                yield data
