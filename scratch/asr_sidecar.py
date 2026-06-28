"""Qwen3-ASR sidecar: OpenAI-compatible /v1/audio/transcriptions endpoint.

Serves Qwen3-ASR via the official qwen-asr package.

Usage:
  .venv\Scripts\python scratch/asr_sidecar.py
  # Starts on http://127.0.0.1:8010
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile

app = FastAPI(title="Qwen3-ASR Sidecar")


@app.on_event("startup")
async def load_model() -> None:
    global model
    import torch
    from qwen_asr import Qwen3ASRModel

    print("Loading Qwen/Qwen3-ASR-0.6B on cuda:0...", flush=True)
    model = Qwen3ASRModel.from_pretrained(
        "Qwen/Qwen3-ASR-0.6B",
        dtype=torch.float16,
        device_map="cuda:0",
        attn_implementation="sdpa",
        max_inference_batch_size=1,
        max_new_tokens=256,
    )
    print("Model loaded.", flush=True)


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model_name: str = Form("Qwen/Qwen3-ASR-0.6B"),
):
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        results = model.transcribe(audio=tmp_path, language=None)
        text = results[0].text if results else ""
        return {"text": text}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8010)
