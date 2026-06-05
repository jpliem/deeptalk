from __future__ import annotations

import asyncio
import uuid
import logging
import os
from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource
from deeptalk.stt.base import SttLive
from deeptalk.transcript.events import TranscriptEvent

log = logging.getLogger(__name__)


def _load_whisper_model(model_size: str):
    """Loads faster-whisper model, automatically falling back to CPU if CUDA DLLs are missing."""
    from faster_whisper import WhisperModel
    import torch
    import numpy as np

    env_device = os.environ.get("DEEPTALK_DEVICE")
    if env_device == "cpu":
        log.info("[whisper] forcing CPU device via DEEPTALK_DEVICE")
        return WhisperModel(model_size, device="cpu", compute_type="int8")

    try:
        has_cuda = torch.cuda.is_available()
    except Exception:
        has_cuda = False

    if has_cuda:
        try:
            log.info("[whisper] attempting CUDA load for model %s ...", model_size)
            model = WhisperModel(model_size, device="cuda", compute_type="float16")
            
            # Force DLL verification by running a dummy transcription
            log.info("[whisper] verifying CUDA libraries by transcribing dummy input...")
            dummy_input = np.zeros(1600, dtype=np.float32) # 100ms of silence
            list(model.transcribe(dummy_input, beam_size=1)[0])
            
            log.info("[whisper] CUDA model verified successfully")
            return model
        except Exception as e:
            log.warning(
                "[whisper] CUDA model load or verification failed (%s). "
                "Falling back to CPU with int8 quantization.",
                e
            )

    log.info("[whisper] loading model %s on CPU (int8) ...", model_size)
    return WhisperModel(model_size, device="cpu", compute_type="int8")


class WhisperSttLive(SttLive):
    """Transcribes a local WAV file with faster-whisper (CTranslate2) in one go."""

    def __init__(
        self,
        session_id: str,
        audio_file_path: str,
        model_size: str = "base",
    ) -> None:
        self._session_id = session_id
        self._audio_file_path = audio_file_path
        self._model_size = model_size

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        model = _load_whisper_model(self._model_size)
        segments, _info = model.transcribe(
            self._audio_file_path,
            vad_filter=True,
            beam_size=5,
        )

        for seg in segments:
            text = (seg.text or "").strip()
            if not text:
                continue
            yield TranscriptEvent(
                session_id=self._session_id,
                ts=round(float(seg.start or 0.0), 3),
                text=text,
                is_final=True,
                source="live",
                span_id=str(uuid.uuid4()),
            )


class WhisperStreamingSttLive(SttLive):
    """Transcribes real-time audio streams (mic or websockets) chunk-by-chunk using faster-whisper.

    Accumulates incoming PCM frames in a buffer and transcribes the entire buffer periodically.
    When silence is detected for a period, the current phrase is finalized and the buffer reset.
    """

    def __init__(
        self,
        session_id: str,
        audio_source: AudioSource,
        model_size: str = "base",
        sample_rate: int = 16000,
    ) -> None:
        self._session_id = session_id
        self._audio = audio_source
        self._model_size = model_size
        self._sample_rate = sample_rate

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        import numpy as np

        model = _load_whisper_model(self._model_size)
        log.info("[whisper-stream] model loaded successfully")

        audio_buffer = bytearray()
        last_transcribed_len = 0
        elapsed = 0.0
        current_phrase = ""
        last_text_ts = None
        start_ts = None
        pause_threshold = 1.2

        try:
            async for frame in self._audio.frames():
                audio_buffer.extend(frame)
                frame_duration = len(frame) / (self._sample_rate * 2)
                elapsed += frame_duration

                # Transcribe if we have accumulated at least 480ms of new audio
                if len(audio_buffer) >= 15360 and (len(audio_buffer) - last_transcribed_len) >= 15360:
                    pcm_data = np.frombuffer(bytes(audio_buffer), dtype=np.int16)
                    audio_float32 = pcm_data.astype(np.float32) / 32768.0

                    def transcribe_fn():
                        segments, _ = model.transcribe(audio_float32, beam_size=3)
                        return " ".join([seg.text for seg in segments]).strip()

                    text = await asyncio.to_thread(transcribe_fn)
                    last_transcribed_len = len(audio_buffer)
                    if text and text != current_phrase:
                        if not current_phrase:
                            start_ts = elapsed - (len(audio_buffer) / (self._sample_rate * 2))
                        current_phrase = text
                        last_text_ts = elapsed

                # Silence detection to finalize the phrase
                if current_phrase and last_text_ts is not None:
                    silence_duration = elapsed - last_text_ts
                    if silence_duration >= pause_threshold:
                        yield TranscriptEvent(
                            session_id=self._session_id,
                            ts=round(start_ts or 0.0, 3),
                            text=current_phrase,
                            is_final=True,
                            source="live",
                            span_id=str(uuid.uuid4()),
                        )
                        current_phrase = ""
                        last_text_ts = None
                        start_ts = None
                        audio_buffer.clear()
                        last_transcribed_len = 0

        finally:
            if current_phrase:
                yield TranscriptEvent(
                    session_id=self._session_id,
                    ts=round(start_ts or 0.0, 3),
                    text=current_phrase,
                    is_final=True,
                    source="live",
                    span_id=str(uuid.uuid4()),
                )
