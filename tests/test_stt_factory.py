import pytest

from deeptalk.config import Config
from deeptalk.audio.file_source import FileAudioSource
from deeptalk.stt.fake import FakeSttLive
from deeptalk.stt.factory import build_audio_source, build_stt
from deeptalk.stt.qwen import QwenAsrSttLive


def test_build_audio_source_file(tmp_path):
    cfg = Config.from_env({"DEEPTALK_AUDIO": "file", "DEEPTALK_AUDIO_FILE": str(tmp_path / "a.wav")})
    src = build_audio_source(cfg)
    assert isinstance(src, FileAudioSource)


def test_build_audio_source_file_requires_path():
    cfg = Config.from_env({"DEEPTALK_AUDIO": "file"})  # no DEEPTALK_AUDIO_FILE
    with pytest.raises(ValueError):
        build_audio_source(cfg)


def test_build_audio_source_unknown():
    cfg = Config.from_env({"DEEPTALK_AUDIO": "bogus"})
    with pytest.raises(ValueError):
        build_audio_source(cfg)


def test_build_stt_fake():
    cfg = Config.from_env({"DEEPTALK_STT": "fake"})
    stt = build_stt(cfg)
    assert isinstance(stt, FakeSttLive)


def test_build_stt_qwen(tmp_path):
    cfg = Config.from_env({
        "DEEPTALK_STT": "qwen",
        "DEEPTALK_AUDIO": "file",
        "DEEPTALK_AUDIO_FILE": str(tmp_path / "a.wav"),
    })
    stt = build_stt(cfg)
    assert isinstance(stt, QwenAsrSttLive)


def test_build_stt_unknown():
    cfg = Config.from_env({"DEEPTALK_STT": "bogus"})
    with pytest.raises(ValueError):
        build_stt(cfg)


@pytest.mark.skip(reason="requires GPU + HuggingFace auth to download gated model")
def test_build_stt_parakeet(tmp_path):
    from deeptalk.stt.nemotron import NemotronSttLive
    cfg = Config.from_env({
        "DEEPTALK_STT": "parakeet",
        "DEEPTALK_AUDIO": "file",
        "DEEPTALK_AUDIO_FILE": str(tmp_path / "a.wav"),
    })
    stt = build_stt(cfg)
    assert isinstance(stt, NemotronSttLive)


def test_build_stt_whisper(tmp_path):
    from deeptalk.stt.whisper import WhisperStreamingSttLive
    cfg = Config.from_env({
        "DEEPTALK_STT": "whisper",
        "DEEPTALK_AUDIO": "file",
        "DEEPTALK_AUDIO_FILE": str(tmp_path / "a.wav"),
    })
    stt = build_stt(cfg)
    assert isinstance(stt, WhisperStreamingSttLive)


from deeptalk.audio.recording import RecordingAudioSource


def test_build_audio_source_wraps_with_recording_when_set(tmp_path):
    cfg = Config.from_env({
        "DEEPTALK_AUDIO": "file",
        "DEEPTALK_AUDIO_FILE": str(tmp_path / "a.wav"),
        "DEEPTALK_RECORDING": str(tmp_path / "rec.wav"),
    })
    src = build_audio_source(cfg)
    assert isinstance(src, RecordingAudioSource)


def test_build_audio_source_no_recording_by_default(tmp_path):
    cfg = Config.from_env({"DEEPTALK_AUDIO": "file", "DEEPTALK_AUDIO_FILE": str(tmp_path / "a.wav")})
    src = build_audio_source(cfg)
    assert isinstance(src, FileAudioSource)
    assert not isinstance(src, RecordingAudioSource)
