from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from deeptalk.stt.base import SttLive
from deeptalk.transcript.events import TranscriptEvent


class WhisperSttLive(SttLive):
    """Transcribes a local WAV file using Hugging Face transformers pipeline on CPU."""

    def __init__(self, session_id: str, audio_file_path: str) -> None:
        self._session_id = session_id
        self._audio_file_path = audio_file_path

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        import torch
        from transformers import pipeline

        device = "cuda" if torch.cuda.is_available() else "cpu"
        # Use GPU pipeline to transcribe the file if available
        p = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-tiny",
            device=device,
        )
        # Using return_timestamps=True returns a dict like {'text': '...', 'chunks': [{'timestamp': (start, end), 'text': '...'}]}
        res = p(
            self._audio_file_path,
            return_timestamps=True,
            generate_kwargs={"no_repeat_ngram_size": 2},
        )
        chunks = res.get("chunks", [])
        if not chunks and res.get("text"):
            # Fallback if no chunks but we have some text
            chunks = [{"timestamp": (0.0, 1.0), "text": res["text"]}]

        for chunk in chunks:
            text = chunk.get("text", "").strip()
            if not text:
                continue
            ts = 0.0
            timestamp = chunk.get("timestamp")
            if timestamp and isinstance(timestamp, (list, tuple)) and len(timestamp) > 0:
                if timestamp[0] is not None:
                    ts = float(timestamp[0])
            yield TranscriptEvent(
                session_id=self._session_id,
                ts=ts,
                text=text,
                is_final=True,
                source="live",
                span_id=str(uuid.uuid4()),
            )
