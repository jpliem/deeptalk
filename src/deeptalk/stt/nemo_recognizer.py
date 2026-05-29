from __future__ import annotations

# VALIDATE ON 3060: This recognizer requires CUDA + the `[gpu]` extra
# (torch, nemo_toolkit[asr]) and cannot run on the macOS dev box. The NeMo
# cache-aware streaming API is version-sensitive; if a call signature differs on
# the installed NeMo, adjust here. Reference:
#   tutorials/asr/Online_ASR_Microphone_Demo_Cache_Aware_Streaming.ipynb
#   examples/asr/asr_cache_aware_streaming/speech_to_text_cache_aware_streaming_infer.py

# Maps desired right-context (frames) -> att_context_size. Larger = more accurate,
# higher latency. 13 -> ~1.12s chunk (best WER); 0 -> ~0.08s (lowest latency).
_ATT_CONTEXT = {0: [70, 0], 1: [70, 1], 6: [70, 6], 13: [70, 13]}


class NemoCacheAwareRecognizer:
    """Real nemotron-speech-streaming recognizer using NeMo cache-aware streaming."""

    def __init__(
        self,
        model_name: str = "nvidia/nemotron-speech-streaming-en-0.6b",
        right_context: int = 13,
        sample_rate: int = 16000,
    ) -> None:
        import numpy as np
        import torch
        import nemo.collections.asr as nemo_asr

        self._np = np
        self._torch = torch
        self._sample_rate = sample_rate

        self._model = nemo_asr.models.ASRModel.from_pretrained(model_name)
        self._model.eval()
        self._model.encoder.setup_streaming_params(
            att_context_size=_ATT_CONTEXT[right_context]
        )
        self.reset()

    def reset(self) -> None:
        (
            self._cache_last_channel,
            self._cache_last_time,
            self._cache_last_channel_len,
        ) = self._model.encoder.get_initial_cache_state(batch_size=1)
        self._prev_hyp = None

    def transcribe_chunk(self, pcm: bytes) -> str:
        audio = self._np.frombuffer(pcm, dtype=self._np.int16)
        signal = self._torch.tensor(
            audio.astype(self._np.float32) / 32768.0
        ).unsqueeze(0)
        signal_len = self._torch.tensor([signal.shape[1]])

        with self._torch.no_grad():
            (
                transcribed,
                self._cache_last_channel,
                self._cache_last_time,
                self._cache_last_channel_len,
                self._prev_hyp,
            ) = self._model.conformer_stream_step(
                processed_signal=signal,
                processed_signal_length=signal_len,
                cache_last_channel=self._cache_last_channel,
                cache_last_time=self._cache_last_time,
                cache_last_channel_len=self._cache_last_channel_len,
                keep_all_outputs=True,
                previous_hypotheses=self._prev_hyp,
                return_transcription=True,
            )
        if not transcribed:
            return ""
        first = transcribed[0]
        return first if isinstance(first, str) else getattr(first, "text", "")
