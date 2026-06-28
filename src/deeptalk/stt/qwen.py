from __future__ import annotations

import io
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from deeptalk.audio.base import AudioSource
from deeptalk.stt.base import SttLive
from deeptalk.transcript.events import TranscriptEvent


class QwenAsrClient(Protocol):
    async def transcribe_wav(self, wav: bytes) -> str:
        ...


@dataclass(frozen=True)
class QwenAsrHttpClient:
    """Client for a Qwen3-ASR sidecar exposing OpenAI-compatible transcription."""

    url: str
    model: str
    timeout: float = 30.0

    async def transcribe_wav(self, wav: bytes) -> str:
        import httpx

        files = {"file": ("chunk.wav", wav, "audio/wav")}
        data = {"model": self.model}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, data=data, files=files)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict):
            text = payload.get("text", "")
            if isinstance(text, str):
                return text.strip()
        return ""


class QwenAsrSttLive(SttLive):
    """Streams TranscriptEvents by sending PCM windows to a Qwen3-ASR sidecar.

    The AudioSource contract is 16 kHz mono 16-bit PCM. Qwen's HTTP endpoint expects
    audio files, so each small PCM window is wrapped as an in-memory WAV.
    """

    def __init__(
        self,
        session_id: str,
        audio_source: AudioSource,
        client: QwenAsrClient,
        chunk_ms: int = 2000,
        source_frame_ms: int = 80,
        sample_rate: int = 16000,
    ) -> None:
        if chunk_ms <= 0:
            raise ValueError("chunk_ms must be positive")
        self._session_id = session_id
        self._audio = audio_source
        self._client = client
        self._chunk_ms = chunk_ms
        self._source_frame_ms = source_frame_ms
        self._sample_rate = sample_rate
        self._target_bytes = int(sample_rate * 2 * chunk_ms / 1000)

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        elapsed = 0.0
        window = bytearray()
        window_start = 0.0

        async for frame in self._audio.frames():
            if not window:
                window_start = elapsed
            window.extend(frame)
            if len(window) >= self._target_bytes:
                async for ev in self._emit_window(bytes(window), window_start):
                    yield ev
                window.clear()
            elapsed += self._source_frame_ms / 1000.0

        if window:
            async for ev in self._emit_window(bytes(window), window_start):
                yield ev

    async def _emit_window(self, pcm: bytes, ts: float) -> AsyncIterator[TranscriptEvent]:
        text = await self._client.transcribe_wav(_pcm_to_wav(pcm, self._sample_rate))
        if text:
            yield TranscriptEvent(
                session_id=self._session_id,
                ts=round(ts, 3),
                text=text,
                is_final=True,
                source="live",
            )


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
