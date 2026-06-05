from __future__ import annotations

import logging

# VALIDATE ON 3060: This recognizer requires CUDA + the `[gpu]` extra
# (torch, nemo_toolkit[asr]) and cannot run on the macOS dev box. The NeMo
# cache-aware streaming API is version-sensitive; if a call signature differs on
# the installed NeMo, adjust here. Reference:
#   tutorials/asr/Online_ASR_Microphone_Demo_Cache_Aware_Streaming.ipynb
#   examples/asr/asr_cache_aware_streaming/speech_to_text_cache_aware_streaming_infer.py

# Maps desired right-context (frames) -> att_context_size. Larger = more accurate,
# higher latency. 13 -> ~1.12s chunk (best WER); 0 -> ~0.08s (lowest latency).
_ATT_CONTEXT = {0: [70, 0], 1: [70, 1], 6: [70, 6], 13: [70, 13]}
_MODEL_CACHE = {}

log = logging.getLogger(__name__)


def _hypothesis_to_text(hyp, model) -> str:
    """Extract decoded text from a NeMo Hypothesis object.

    The `.text` field is Optional and may be None even after decoding —
    in that case we fall back to decoding `y_sequence` through the tokenizer.
    """
    if hyp is None:
        return ""
    # Fast path: text already decoded
    if getattr(hyp, "text", None):
        return hyp.text
    # Slow path: decode token ids through the model tokenizer
    y_seq = getattr(hyp, "y_sequence", None)
    if y_seq is None:
        return ""
    try:
        import torch
        if isinstance(y_seq, torch.Tensor):
            ids = y_seq.tolist()
        else:
            ids = list(y_seq)
        # Filter out blank tokens (id 0 for most RNNT models)
        ids = [i for i in ids if i > 0]
        text = model.tokenizer.ids_to_text(ids)
        return text or ""
    except Exception as e:
        log.warning("[nemo] failed to decode y_sequence: %s", e)
        return ""


class NemoCacheAwareRecognizer:
    """Real nemotron-speech-streaming recognizer using NeMo cache-aware streaming."""

    def __init__(
        self,
        model_name: str = "nvidia/nemotron-speech-streaming-en-0.6b",
        right_context: int = 0,
        sample_rate: int = 16000,
    ) -> None:
        import numpy as np
        import torch
        import nemo.collections.asr as nemo_asr

        self._np = np
        self._torch = torch
        self._sample_rate = sample_rate
        
        import os
        env_device = os.environ.get("DEEPTALK_DEVICE")
        if env_device:
            self._device = env_device
        else:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"

        cache_key = (model_name, self._device)
        if cache_key in _MODEL_CACHE:
            self._model = _MODEL_CACHE[cache_key]
            log.info("[nemo] reusing cached model %s on %s", model_name, self._device)
        else:
            log.info("[nemo] loading model %s onto %s ...", model_name, self._device)
            self._model = nemo_asr.models.ASRModel.from_pretrained(model_name)
            self._model = self._model.to(self._device)
            self._model.eval()
            _MODEL_CACHE[cache_key] = self._model
            log.info("[nemo] model loaded OK")

        log.info(
            "[nemo] setting up streaming params: right_context=%d -> att_context_size=%s",
            right_context, _ATT_CONTEXT[right_context],
        )
        self._model.encoder.setup_streaming_params(
            att_context_size=_ATT_CONTEXT[right_context]
        )
        self.reset()

    def reset(self) -> None:
        (
            cache_last_channel,
            cache_last_time,
            cache_last_channel_len,
        ) = self._model.encoder.get_initial_cache_state(batch_size=1)

        self._cache_last_channel = cache_last_channel.to(self._device) if cache_last_channel is not None else None
        self._cache_last_time = cache_last_time.to(self._device) if cache_last_time is not None else None
        self._cache_last_channel_len = cache_last_channel_len.to(self._device) if cache_last_channel_len is not None else None
        self._prev_hyp = None
        self._prev_text = ""
        self._buffer = b""
        log.debug("[nemo] cache reset")

    def transcribe_chunk(self, pcm: bytes) -> str:
        self._buffer += pcm
        if len(self._buffer) < 15360:  # ~480ms minimum
            return ""

        chunk_to_process = self._buffer
        self._buffer = b""
        chunk_ms = len(chunk_to_process) / (self._sample_rate * 2) * 1000
        log.info("[nemo] running inference on %.0f ms of audio (%d bytes)", chunk_ms, len(chunk_to_process))

        audio = self._np.frombuffer(chunk_to_process, dtype=self._np.int16)
        signal = self._torch.tensor(
            audio.astype(self._np.float32) / 32768.0
        ).unsqueeze(0).to(self._device)
        signal_len = self._torch.tensor([signal.shape[1]]).to(self._device)

        with self._torch.no_grad():
            processed_signal, processed_signal_length = self._model.preprocessor(
                input_signal=signal, length=signal_len
            )
            (
                _,
                transcribed,
                self._cache_last_channel,
                self._cache_last_time,
                self._cache_last_channel_len,
                self._prev_hyp,
            ) = self._model.conformer_stream_step(
                processed_signal=processed_signal,
                processed_signal_length=processed_signal_length,
                cache_last_channel=self._cache_last_channel,
                cache_last_time=self._cache_last_time,
                cache_last_channel_len=self._cache_last_channel_len,
                keep_all_outputs=True,
                previous_hypotheses=self._prev_hyp,
                return_transcription=True,
            )

        log.info("[nemo] raw transcribed type=%s value=%r", type(transcribed), transcribed)

        if not transcribed:
            log.info("[nemo] transcribed is empty")
            return ""

        # For RNNT models, transcribed is a list of Hypothesis objects (one per batch item).
        # best_hyp (index 5) is also a list of Hypothesis — same objects.
        # We use the first (and only, batch=1) hypothesis.
        first_hyp = transcribed[0]
        log.info("[nemo] first_hyp type=%s text=%r y_sequence type=%s",
                 type(first_hyp),
                 getattr(first_hyp, "text", "N/A"),
                 type(getattr(first_hyp, "y_sequence", None)))

        full_text = _hypothesis_to_text(first_hyp, self._model)
        log.info("[nemo] full_text=%r", full_text)

        if not full_text:
            return ""

        return full_text.strip()
