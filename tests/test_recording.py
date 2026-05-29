import wave

from deeptalk.audio.file_source import FileAudioSource
from deeptalk.audio.recording import RecordingAudioSource


def _write_wav(path, seconds=0.16, rate=16000):
    import math
    import struct

    n = int(rate * seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(
            b"".join(struct.pack("<h", int(1000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(n))
        )


async def test_recording_passes_frames_through_and_writes_wav(tmp_path):
    src_wav = tmp_path / "in.wav"
    _write_wav(src_wav, seconds=0.16)  # 2 chunks @ 80ms
    out_wav = tmp_path / "rec.wav"

    rec = RecordingAudioSource(FileAudioSource(str(src_wav), chunk_ms=80), str(out_wav))
    chunks = [c async for c in rec.frames()]

    assert len(chunks) == 2
    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2
        assert wf.getnframes() == int(16000 * 0.16)
