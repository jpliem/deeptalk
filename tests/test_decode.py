import math
import shutil
import struct
import wave

import pytest

from deeptalk.audio.decode import _ffmpeg_cmd, decode_to_wav


def _write_wav(path, seconds=0.1, rate=16000, channels=1):
    n = int(rate * seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(struct.pack("<h", int(1000 * math.sin(i / 5))) for i in range(n * channels)))


def test_ffmpeg_cmd_builds_16k_mono():
    cmd = _ffmpeg_cmd("in.mp3", "out.wav", rate=16000)
    assert cmd[0] == "ffmpeg"
    assert "in.mp3" in cmd and "out.wav" in cmd
    assert "16000" in cmd
    assert "1" in cmd


def test_decode_passthrough_for_conformant_wav(tmp_path):
    src = tmp_path / "ok.wav"
    _write_wav(src, rate=16000, channels=1)
    assert decode_to_wav(str(src)) == str(src)


def test_decode_nonconformant_requires_ffmpeg(tmp_path):
    src = tmp_path / "stereo.wav"
    _write_wav(src, rate=44100, channels=2)
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    out = decode_to_wav(str(src))
    assert out != str(src)
    with wave.open(out, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
