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
        return FileAudioSource(config.audio_file)
    if config.audio == "mic":
        from deeptalk.audio.mic_source import SounddeviceSource

        return SounddeviceSource()
    raise ValueError(f"unknown audio source: {config.audio}")


def build_stt(config: Config) -> SttLive:
    if config.stt == "fake":
        return FakeSttLive(
            session_id=config.session_id,
            fixture_path=config.fixture_path,
            realtime=True,
        )
    if config.stt == "nemotron":
        # Imported here so the nemo/torch import only happens on the GPU box.
        from deeptalk.stt.nemo_recognizer import NemoCacheAwareRecognizer
        from deeptalk.stt.nemotron import NemotronSttLive

        audio = build_audio_source(config)
        return NemotronSttLive(
            session_id=config.session_id,
            audio_source=audio,
            recognizer=NemoCacheAwareRecognizer(),
        )
    raise ValueError(f"unknown stt: {config.stt}")
