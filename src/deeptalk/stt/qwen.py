from __future__ import annotations

import array
import asyncio
import io
import logging
import math
import re
import uuid
import wave
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)

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
    language: str | None = None

    async def transcribe_wav(self, wav: bytes) -> str:
        import httpx

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                files = {"file": ("chunk.wav", wav, "audio/wav")}
                data = {"model": self.model}
                if self.language:
                    data["language"] = self.language
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(self.url, data=data, files=files)
                resp.raise_for_status()
                payload = resp.json()
                if isinstance(payload, dict):
                    text = payload.get("text", "")
                    if isinstance(text, str):
                        return text.strip()
                return ""
            except Exception as e:
                last_error = e
                log.warning("qwen request failed (attempt %d/3): %s", attempt + 1, e)
                await asyncio.sleep(1.0 * (attempt + 1))
        raise last_error  # type: ignore[misc]


def _rms(pcm: bytes) -> float:
    """Root-mean-square of 16-bit mono PCM; 0 for empty input."""
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


def _collapse_repeats(text: str, max_run: int = 2) -> str:
    """Collapse hallucinated token loops: runs of the same 1-4 word n-gram
    repeated more than `max_run` times are trimmed to `max_run` occurrences."""
    tokens = text.split()
    for n in range(4, 0, -1):
        out: list[str] = []
        i = 0
        while i < len(tokens):
            gram = tokens[i : i + n]
            if len(gram) < n:
                out.extend(tokens[i:])
                break
            count = 1
            j = i + n
            while tokens[j : j + n] == gram:
                count += 1
                j += n
            if count > 1:
                out.extend(gram * min(count, max_run))
                i = j
            else:
                out.append(tokens[i])
                i += 1
        tokens = out
    return " ".join(tokens)


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


class QwenAsrSttLive(SttLive):
    """Streams TranscriptEvents by sending PCM windows to a Qwen3-ASR sidecar.

    The AudioSource contract is 16 kHz mono 16-bit PCM. Qwen's HTTP endpoint expects
    audio files, so each small PCM window is wrapped as an in-memory WAV.

    Hardening for live speech:
    - windows whose RMS falls below `rms_threshold` are treated as silence and
      never sent to the model (kills hallucination on breath/noise),
    - voiced window texts are buffered into a phrase and emitted as ONE final
      event when a silent window arrives (silence-gap finalization), matching
      the Whisper streaming behavior, so agents react to whole sentences,
    - consecutive duplicate window texts are dropped and token loops collapsed,
    - a phrase is force-finalized after `max_phrase_ms` of speech so a long
      monologue cannot buffer unboundedly.
    """

    def __init__(
        self,
        session_id: str,
        audio_source: AudioSource,
        client: QwenAsrClient,
        chunk_ms: int = 2000,
        source_frame_ms: int = 80,
        sample_rate: int = 16000,
        rms_threshold: float = 200.0,
        max_phrase_ms: int = 15000,
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
        self._rms_threshold = rms_threshold
        self._max_windows = max(1, math.ceil(max_phrase_ms / chunk_ms))

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        elapsed = 0.0
        window = bytearray()
        window_start = 0.0
        phrase: list[str] = []
        phrase_start = 0.0
        phrase_windows = 0

        def _finalize() -> TranscriptEvent | None:
            nonlocal phrase_windows
            if not phrase:
                return None
            ev = TranscriptEvent(
                session_id=self._session_id,
                ts=round(phrase_start, 3),
                text=" ".join(phrase),
                is_final=True,
                source="live",
                span_id=str(uuid.uuid4()),
            )
            phrase.clear()
            phrase_windows = 0
            return ev

        async def _ingest_window(pcm: bytes, ts: float) -> bool:
            """Transcribe a voiced window into the phrase buffer.

            Returns False when the window is silence (caller finalizes)."""
            nonlocal phrase_start, phrase_windows
            if _rms(pcm) < self._rms_threshold:
                return False
            text = _collapse_repeats(await self._transcribe(pcm, ts))
            if text and (not phrase or _norm(text) != _norm(phrase[-1])):
                if not phrase:
                    phrase_start = ts
                phrase.append(text)
            if phrase:
                phrase_windows += 1
            return True

        async for frame in self._audio.frames():
            if not window:
                window_start = elapsed
            window.extend(frame)
            elapsed += self._source_frame_ms / 1000.0
            if len(window) < self._target_bytes:
                continue
            pcm = bytes(window)
            window.clear()

            voiced = await _ingest_window(pcm, window_start)
            if not voiced or phrase_windows >= self._max_windows:
                ev = _finalize()
                if ev is not None:
                    yield ev

        if window:
            await _ingest_window(bytes(window), window_start)
        ev = _finalize()
        if ev is not None:
            yield ev

    async def _transcribe(self, pcm: bytes, ts: float) -> str:
        try:
            return await self._client.transcribe_wav(_pcm_to_wav(pcm, self._sample_rate))
        except Exception:
            log.exception("qwen: transcription failed for window at %.1fs, skipping", ts)
            return ""


def _pcm_to_wav(pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
