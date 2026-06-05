import math
import struct
import wave

from deeptalk.audio.file_source import FileAudioSource
from deeptalk.stt.nemotron import NemotronSttLive
from deeptalk.transcript.events import TranscriptEvent


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


class _FakeRecognizer:
    """Simulates a cumulative recognizer. resets when reset() is called."""

    def __init__(self, scripts):
        self._scripts = list(scripts)
        self._i = 0

    def transcribe_chunk(self, pcm: bytes) -> str:
        out = self._scripts[self._i] if self._i < len(self._scripts) else ""
        self._i += 1
        return out

    def reset(self) -> None:
        pass


async def test_accumulates_and_emits_at_end(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, seconds=0.24)  # 3 chunks @ 80ms
    src = FileAudioSource(str(path), chunk_ms=80)
    # The recognizer returns cumulative text per chunk
    rec = _FakeRecognizer(["hello", "hello", "hello world"])
    stt = NemotronSttLive(session_id="s1", audio_source=src, recognizer=rec, chunk_ms=80)

    events = [e async for e in stt.stream()]

    assert len(events) == 1
    assert events[0].text == "hello world"
    assert events[0].ts == 0.0
    assert events[0].is_final
    assert events[0].source == "live"


async def test_segmentation_by_silence(tmp_path):
    # Create 2.0 seconds of audio (25 chunks @ 80ms)
    path = tmp_path / "b.wav"
    _write_wav(path, seconds=2.0)
    src = FileAudioSource(str(path), chunk_ms=80)

    # We will simulate:
    # t=0.0: "hello"
    # t=0.08: "hello world"
    # t=0.16 to t=1.44 (1.28 seconds of silence/empty return) -> should trigger pause flush!
    # t=1.52: "how"
    # t=1.60: "how are"
    # t=1.68: "how are you"
    # then silence till end
    scripts = [""] * 25
    scripts[0] = "hello"
    scripts[1] = "hello world"
    
    # After reset, cumulative text starts fresh:
    scripts[19] = "how"
    scripts[20] = "how are"
    scripts[21] = "how are you"

    rec = _FakeRecognizer(scripts)
    # NemotronSttLive with chunk_ms=80
    stt = NemotronSttLive(session_id="s1", audio_source=src, recognizer=rec, chunk_ms=80)

    events = [e async for e in stt.stream()]

    assert len(events) == 2
    assert events[0].text == "hello world"
    assert events[0].ts == 0.0
    
    assert events[1].text == "how are you"
    # "how" started at index 19 -> 19 * 0.08s = 1.52s
    assert events[1].ts == 1.52
