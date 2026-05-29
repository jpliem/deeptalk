import math
import struct
import wave

import pytest

from deeptalk.audio.file_source import FileAudioSource


def _write_wav(path, seconds, rate=16000, channels=1, sampwidth=2):
    n = int(rate * seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(rate)
        frame = b"".join(
            struct.pack("<h", int(1000 * math.sin(2 * math.pi * 440 * i / rate)))
            for i in range(n)
        )
        if channels == 2:
            frame = b"".join(
                struct.pack("<hh", s, s)
                for s in struct.unpack("<%dh" % n, frame)
            )
        wf.writeframes(frame)


async def test_yields_fixed_size_chunks(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, seconds=0.24)  # 0.24s @ 16k = 3 chunks of 80ms
    src = FileAudioSource(str(path), chunk_ms=80)
    chunks = [c async for c in src.frames()]
    assert len(chunks) == 3
    assert len(chunks[0]) == 2560  # 1280 samples * 2 bytes
    assert len(chunks[1]) == 2560


async def test_rejects_non_mono(tmp_path):
    path = tmp_path / "stereo.wav"
    _write_wav(path, seconds=0.1, channels=2)
    src = FileAudioSource(str(path))
    with pytest.raises(ValueError):
        [c async for c in src.frames()]


async def test_rejects_wrong_sample_rate(tmp_path):
    path = tmp_path / "slow.wav"
    _write_wav(path, seconds=0.1, rate=8000)
    src = FileAudioSource(str(path))
    with pytest.raises(ValueError):
        [c async for c in src.frames()]
