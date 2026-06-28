from __future__ import annotations

from deeptalk.audio.base import AudioSource
from deeptalk.config import Config
from deeptalk.stt.base import SttLive
from deeptalk.stt.fake import FakeSttLive


def build_audio_source(config: Config) -> AudioSource:
    if config.audio == "file":
        from deeptalk.audio.file_source import FileAudioSource

        if not config.audio_file:
            raise ValueError("DEEPTALK_AUDIO_FILE is required when DEEPTALK_AUDIO=file")
        source: AudioSource = FileAudioSource(config.audio_file)
    elif config.audio == "mic":
        from deeptalk.audio.mic_source import SounddeviceSource

        source = SounddeviceSource()
    else:
        raise ValueError(f"unknown audio source: {config.audio}")

    if config.recording_path:
        from deeptalk.audio.recording import RecordingAudioSource

        return RecordingAudioSource(source, config.recording_path)
    return source


def build_stt(
    config: Config,
    audio_source: AudioSource | None = None,
    realtime: bool = True,
    session_id: str | None = None,
) -> SttLive:
    sid = session_id if session_id is not None else config.session_id
    if config.stt == "fake":
        return FakeSttLive(
            session_id=sid,
            fixture_path=config.fixture_path,
            realtime=realtime,
        )
    if config.stt == "nemotron":
        # Imported here so the nemo/torch import only happens on the GPU box.
        from deeptalk.stt.nemo_recognizer import NemoCacheAwareRecognizer
        from deeptalk.stt.nemotron import NemotronSttLive

        audio = audio_source if audio_source is not None else build_audio_source(config)
        return NemotronSttLive(
            session_id=sid,
            audio_source=audio,
            # right_context=13 gives best WER (~1.1 s latency);
            # right_context=0 is lowest latency but noticeably worse quality.
            recognizer=NemoCacheAwareRecognizer(model_name=config.nemo_model, right_context=13),
            chunk_ms=160,
        )
    if config.stt == "parakeet":
        from deeptalk.stt.nemo_recognizer import NemoCacheAwareRecognizer
        from deeptalk.stt.nemotron import NemotronSttLive

        audio = audio_source if audio_source is not None else build_audio_source(config)
        return NemotronSttLive(
            session_id=sid,
            audio_source=audio,
            recognizer=NemoCacheAwareRecognizer(
                model_name=config.parakeet_model, right_context=13
            ),
            chunk_ms=160,
        )
    if config.stt == "whisper":
        from deeptalk.stt.whisper import WhisperStreamingSttLive

        audio = audio_source if audio_source is not None else build_audio_source(config)
        return WhisperStreamingSttLive(
            session_id=sid,
            audio_source=audio,
            model_size=config.whisper_model,
        )
    if config.stt == "qwen":
        from deeptalk.stt.qwen import QwenAsrHttpClient, QwenAsrSttLive

        audio = audio_source if audio_source is not None else build_audio_source(config)
        return QwenAsrSttLive(
            session_id=sid,
            audio_source=audio,
            client=QwenAsrHttpClient(config.qwen_asr_url, config.qwen_asr_model),
            chunk_ms=config.qwen_asr_chunk_ms,
        )
    raise ValueError(f"unknown stt: {config.stt}")
