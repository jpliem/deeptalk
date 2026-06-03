from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from deeptalk.stt.base import SttLive
from deeptalk.transcript.events import TranscriptEvent


class WhisperSttLive(SttLive):
    """Transcribes a local WAV file with faster-whisper (CTranslate2).

    Far faster and more accurate than the transformers `whisper-tiny` path: runs
    int8 on CPU (dev box) and float16 on CUDA (GPU box), with built-in VAD to drop
    silence. Model size is configurable; `base` is a good CPU default, `large-v3`
    is best on a GPU.
    """

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
        from faster_whisper import WhisperModel

        try:
            import torch

            has_cuda = torch.cuda.is_available()
        except Exception:
            has_cuda = False

        device = "cuda" if has_cuda else "cpu"
        compute_type = "float16" if has_cuda else "int8"

        model = WhisperModel(self._model_size, device=device, compute_type=compute_type)
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
