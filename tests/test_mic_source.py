from deeptalk.audio.base import AudioSource
from deeptalk.audio.mic_source import SounddeviceSource


def test_is_audiosource_and_constructs_without_opening_device():
    src = SounddeviceSource(chunk_ms=80, sample_rate=16000)
    assert isinstance(src, AudioSource)
    assert src.sample_rate == 16000
    assert src.chunk_ms == 80
