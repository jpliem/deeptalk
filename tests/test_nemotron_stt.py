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
    """Returns scripted text per chunk (index-aligned). '' means no output."""

    def __init__(self, scripts):
        self._scripts = list(scripts)
        self._i = 0

    def transcribe_chunk(self, pcm: bytes) -> str:
        out = self._scripts[self._i] if self._i < len(self._scripts) else ""
        self._i += 1
        return out


async def test_emits_events_only_for_nonempty_text(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, seconds=0.24)  # 3 chunks @ 80ms
    src = FileAudioSource(str(path), chunk_ms=80)
    rec = _FakeRecognizer(["hello", "", "world"])
    stt = NemotronSttLive(session_id="s1", audio_source=src, recognizer=rec, chunk_ms=80)

    events = [e async for e in stt.stream()]

    assert all(isinstance(e, TranscriptEvent) for e in events)
    assert [e.text for e in events] == ["hello", "world"]
    assert all(e.is_final and e.source == "live" and e.session_id == "s1" for e in events)


async def test_timestamps_track_chunk_position(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, seconds=0.24)
    src = FileAudioSource(str(path), chunk_ms=80)
    rec = _FakeRecognizer(["a", "", "c"])  # emit on chunk 0 and chunk 2
    stt = NemotronSttLive(session_id="s1", audio_source=src, recognizer=rec, chunk_ms=80)

    events = [e async for e in stt.stream()]

    assert events[0].ts == 0.0
    assert events[1].ts == 0.16  # chunk index 2 -> 2 * 0.08s
