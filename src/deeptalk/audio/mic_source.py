from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource


class SounddeviceSource(AudioSource):
    """Captures the default microphone as 16 kHz mono 16-bit PCM chunks.

    sounddevice is imported lazily so this module loads on machines without
    PortAudio, and so tests never open an audio device.
    """

    def __init__(self, chunk_ms: int = 80, sample_rate: int = 16000) -> None:
        self.chunk_ms = chunk_ms
        self.sample_rate = sample_rate
        self._blocksize = int(sample_rate * chunk_ms / 1000)

    async def frames(self) -> AsyncIterator[bytes]:
        import sounddevice as sd

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes] = asyncio.Queue()

        def _callback(indata, frames, time_info, status) -> None:  # noqa: ANN001
            loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

        stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self._blocksize,
            channels=1,
            dtype="int16",
            callback=_callback,
        )
        with stream:
            while True:
                yield await queue.get()
