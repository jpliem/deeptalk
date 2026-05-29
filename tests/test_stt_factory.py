import pytest

from deeptalk.config import Config
from deeptalk.audio.file_source import FileAudioSource
from deeptalk.stt.fake import FakeSttLive
from deeptalk.stt.factory import build_audio_source, build_stt


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


def test_build_stt_unknown():
    cfg = Config.from_env({"DEEPTALK_STT": "bogus"})
    with pytest.raises(ValueError):
        build_stt(cfg)
