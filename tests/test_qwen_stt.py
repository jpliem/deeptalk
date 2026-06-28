import math
import struct
import wave

from deeptalk.audio.file_source import FileAudioSource
from deeptalk.stt.qwen import QwenAsrSttLive


def _write_wav(path, seconds, rate=16000):
    n = int(rate * seconds)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(
            b"".join(
                struct.pack("<h", int(1000 * math.sin(2 * math.pi * 440 * i / rate)))
                for i in range(n)
            )
        )


class _FakeQwenClient:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.wavs = []

    async def transcribe_wav(self, wav: bytes) -> str:
        self.wavs.append(wav)
        return self.scripts.pop(0) if self.scripts else ""


async def test_qwen_stt_emits_nonempty_transcripts_per_window(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, seconds=0.24)
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["hello", ""])
    stt = QwenAsrSttLive(
        session_id="s1",
        audio_source=src,
        client=client,
        chunk_ms=160,
        source_frame_ms=80,
    )

    events = [e async for e in stt.stream()]

    assert [e.text for e in events] == ["hello"]
    assert events[0].session_id == "s1"
    assert events[0].ts == 0.0
    assert events[0].is_final
    assert len(client.wavs) == 2


async def test_qwen_stt_timestamps_follow_window_start(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, seconds=0.32)
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["first", "second"])
    stt = QwenAsrSttLive(
        session_id="s1",
        audio_source=src,
        client=client,
        chunk_ms=160,
        source_frame_ms=80,
    )

    events = [e async for e in stt.stream()]

    assert [e.ts for e in events] == [0.0, 0.16]


async def test_qwen_stt_wraps_pcm_windows_as_16khz_mono_wav(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, seconds=0.16)
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["hello"])
    stt = QwenAsrSttLive(
        session_id="s1",
        audio_source=src,
        client=client,
        chunk_ms=160,
        source_frame_ms=80,
    )

    _ = [e async for e in stt.stream()]

    wav_path = tmp_path / "chunk.wav"
    wav_path.write_bytes(client.wavs[0])
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
