from __future__ import annotations

# VALIDATE ON 3060: VibeVoice-ASR needs CUDA + transformers>=5.3.0 (the [gpu] extra)
# and is not exercised by the Mac suite. transformers is imported lazily. The model's
# JSON output shape ([{"Start","End","Speaker","Content"}]) is version-sensitive;
# adjust parsing here if a real run returns a different structure.
# Model: microsoft/VibeVoice-ASR-HF

import json
import re

from deeptalk.diarize.models import DiarizedSegment


class VibeVoiceDiarizer:
    """Batch diarization with VibeVoice-ASR (who/when/what)."""

    def __init__(self, model_name: str = "microsoft/VibeVoice-ASR-HF") -> None:
        self._model_name = model_name

    async def diarize(self, audio_path: str) -> list[DiarizedSegment]:
        import torch  # noqa: F401
        from transformers import pipeline

        asr = pipeline("automatic-speech-recognition", model=self._model_name)
        result = asr(audio_path)
        raw = result["text"] if isinstance(result, dict) else str(result)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            rows = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        return [
            DiarizedSegment(
                speaker=int(r.get("Speaker", 0)),
                start=float(r.get("Start", 0.0)),
                end=float(r.get("End", 0.0)),
                text=str(r.get("Content", "")),
            )
            for r in rows
        ]
