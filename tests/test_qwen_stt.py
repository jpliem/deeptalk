import math
import struct
import wave

import httpx

from deeptalk.audio.file_source import FileAudioSource
from deeptalk.stt.qwen import QwenAsrHttpClient, QwenAsrSttLive, _collapse_repeats, _rms


def _tone_pcm(seconds, rate=16000, amplitude=1000):
    n = int(rate * seconds)
    return b"".join(
        struct.pack("<h", int(amplitude * math.sin(2 * math.pi * 440 * i / rate)))
        for i in range(n)
    )


def _silence_pcm(seconds, rate=16000):
    return b"\x00\x00" * int(rate * seconds)


def _write_wav(path, pcm, rate=16000):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)


class _FakeQwenClient:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.wavs = []

    async def transcribe_wav(self, wav: bytes) -> str:
        self.wavs.append(wav)
        return self.scripts.pop(0) if self.scripts else ""


def _stt(src, client, **kwargs):
    defaults = dict(
        session_id="s1",
        audio_source=src,
        client=client,
        chunk_ms=160,
        source_frame_ms=80,
    )
    defaults.update(kwargs)
    return QwenAsrSttLive(**defaults)


async def test_qwen_stt_emits_nonempty_transcripts_per_window(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, _tone_pcm(0.24))
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["hello", ""])
    events = [e async for e in _stt(src, client).stream()]

    assert [e.text for e in events] == ["hello"]
    assert events[0].session_id == "s1"
    assert events[0].ts == 0.0
    assert events[0].is_final
    assert events[0].span_id is not None
    assert len(client.wavs) == 2


async def test_qwen_stt_assembles_voiced_windows_into_one_phrase(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, _tone_pcm(0.32))
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["first", "second"])
    events = [e async for e in _stt(src, client).stream()]

    assert [e.text for e in events] == ["first second"]
    assert events[0].ts == 0.0


async def test_qwen_stt_silence_gap_finalizes_phrase(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, _tone_pcm(0.16) + _silence_pcm(0.16) + _tone_pcm(0.16))
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["one", "two"])
    events = [e async for e in _stt(src, client).stream()]

    assert [e.text for e in events] == ["one", "two"]
    assert [e.ts for e in events] == [0.0, 0.32]
    # The silent window must never reach the model.
    assert len(client.wavs) == 2


async def test_qwen_stt_skips_silent_audio_entirely(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, _silence_pcm(0.32))
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["should not appear"])
    events = [e async for e in _stt(src, client).stream()]

    assert events == []
    assert client.wavs == []


async def test_qwen_stt_drops_consecutive_duplicate_window_texts(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, _tone_pcm(0.48))
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["hello", "Hello.", "hello"])
    events = [e async for e in _stt(src, client).stream()]

    assert [e.text for e in events] == ["hello"]


async def test_qwen_stt_force_finalizes_after_max_phrase(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, _tone_pcm(0.48))
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["a", "b", "c"])
    events = [e async for e in _stt(src, client, max_phrase_ms=320).stream()]

    assert [e.text for e in events] == ["a b", "c"]


async def test_qwen_stt_wraps_pcm_windows_as_16khz_mono_wav(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, _tone_pcm(0.16))
    src = FileAudioSource(str(path), chunk_ms=80)
    client = _FakeQwenClient(["hello"])
    _ = [e async for e in _stt(src, client).stream()]

    wav_path = tmp_path / "chunk.wav"
    wav_path.write_bytes(client.wavs[0])
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000


async def _capture_multipart_body(monkeypatch, client):
    captured = {}

    def handler(request):
        captured["body"] = request.read()
        return httpx.Response(200, json={"text": "ok"})

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real_async_client(transport=transport, **kw)
    )
    text = await client.transcribe_wav(b"RIFFfake")
    assert text == "ok"
    return captured["body"]


async def test_http_client_sends_language_when_set(monkeypatch):
    client = QwenAsrHttpClient("http://sidecar/v1", "m", language="zh")
    body = await _capture_multipart_body(monkeypatch, client)
    assert b'name="language"' in body
    assert b"zh" in body


async def test_http_client_omits_language_by_default(monkeypatch):
    client = QwenAsrHttpClient("http://sidecar/v1", "m")
    body = await _capture_multipart_body(monkeypatch, client)
    assert b'name="language"' not in body


def test_rms_of_silence_is_zero_and_tone_is_loud():
    assert _rms(_silence_pcm(0.1)) == 0.0
    assert _rms(_tone_pcm(0.1)) > 200


def test_collapse_repeats_trims_token_loops():
    assert _collapse_repeats("the the the the cat") == "the the cat"
    assert (
        _collapse_repeats("thank you thank you thank you thank you")
        == "thank you thank you"
    )
    assert _collapse_repeats("a normal sentence") == "a normal sentence"
    assert _collapse_repeats("") == ""
