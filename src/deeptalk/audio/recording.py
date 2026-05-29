from __future__ import annotations

import wave
from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource


class RecordingAudioSource(AudioSource):
    """Wraps an AudioSource, passing frames through while teeing them to a WAV file.

    Gives the post-session diarizer something to read.
    """

    def __init__(self, inner: AudioSource, path: str, sample_rate: int = 16000) -> None:
        self._inner = inner
        self._path = path
        self._sample_rate = sample_rate

    async def frames(self) -> AsyncIterator[bytes]:
        wf = wave.open(self._path, "wb")
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(self._sample_rate)
        try:
            async for frame in self._inner.frames():
                wf.writeframes(frame)
                yield frame
        finally:
            wf.close()
