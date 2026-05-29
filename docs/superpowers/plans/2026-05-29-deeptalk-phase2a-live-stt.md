# DeepTalk Phase 2A — Live STT Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DeepTalk transcribe real audio. Add an `AudioSource` capture layer, a `NemotronSttLive` source behind the existing `SttLive` seam, an env-driven config + factory to pick STT/audio at runtime, and a lifespan-based entrypoint — all Mac-buildable and tested, except the real NeMo model run which is validated on the RTX 3060.

**Architecture:** `AudioSource` yields 16 kHz mono PCM chunks (file source for dev/tests, sounddevice mic for the laptop). `NemotronSttLive` consumes an `AudioSource` and a `StreamingRecognizer` (injectable seam) and emits `TranscriptEvent`s — identical output contract to `FakeSttLive`, so ingest/store/bus/WebSocket are untouched. The real NeMo cache-aware recognizer is the one component not runnable on macOS; it is isolated so its surrounding logic is fully unit-tested with a fake recognizer, and the model binding is validated on the 3060.

**Tech Stack:** Python 3.12, uv, FastAPI, pytest + pytest-asyncio, stdlib `wave`, `sounddevice` + `numpy` (base deps), NeMo + torch (Linux-only `[gpu]` extra).

---

## Roadmap context

This is **Plan 2A of the Phase 2 pair** (spec §15 build order, phase 2):
- **2A (THIS PLAN):** live STT backend — config + audio capture + NemotronSttLive + factory + lifespan entrypoint.
- **2B (next):** Vite + React + TS transcript-pane UI served by FastAPI, connecting to `/ws/transcript`.

Phase 1 (transcript spine) is on `main`. This plan builds on it.

## Hardware-validation note (read first)

Every task here is built and unit-tested on macOS **except Task 6** (`NemoCacheAwareRecognizer`), which requires CUDA + the `[gpu]` extra and only runs on the RTX 3060. Its code is a documented best-effort against the NeMo cache-aware streaming API and is explicitly marked **VALIDATE ON 3060**. Tests for Task 6 are limited to import/lazy-load/protocol-conformance — the real decode is validated when the user runs it on the laptop. This is a deliberate, scoped exception to "exact tested code," forced by hardware availability — not a placeholder.

## File Structure (Phase 2A)

```
deeptalk/
  pyproject.toml                     # MODIFY: add base deps (sounddevice, numpy) + [gpu] extra
  src/deeptalk/
    config.py                        # NEW: Config + from_env
    transcript/events.py             # MODIFY: source -> Literal["live","diarized"]
    audio/
      __init__.py                    # NEW (empty)
      base.py                        # NEW: AudioSource ABC
      file_source.py                 # NEW: FileAudioSource (WAV -> PCM chunks)
      mic_source.py                  # NEW: SounddeviceSource (mic -> PCM chunks)
    stt/
      recognizer.py                  # NEW: StreamingRecognizer Protocol
      nemotron.py                    # NEW: NemotronSttLive (orchestration)
      nemo_recognizer.py             # NEW: NemoCacheAwareRecognizer (VALIDATE ON 3060)
      factory.py                     # NEW: build_audio_source / build_stt
    server/
      app.py                         # MODIFY: create_app accepts optional lifespan
      __main__.py                    # MODIFY: Config + factory + lifespan (replaces on_event)
  tests/
    test_config.py                   # NEW
    test_audio_file_source.py        # NEW
    test_mic_source.py               # NEW
    test_nemotron_stt.py             # NEW
    test_nemo_recognizer.py          # NEW
    test_stt_factory.py              # NEW
    test_app_lifespan.py             # NEW
    test_events.py                   # MODIFY: add Literal assertion (optional)
```

---

### Task 1: Make `source` a Literal type (Phase-1 followup)

**Files:**
- Modify: `src/deeptalk/transcript/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Add a failing test** — append to `tests/test_events.py`:

```python
def test_event_source_accepts_diarized():
    ev = TranscriptEvent(session_id="s1", ts=0.0, text="x", is_final=True, source="diarized")
    assert ev.source == "diarized"


def test_event_source_type_is_literal():
    import typing
    from deeptalk.transcript.events import TranscriptEvent as TE
    hints = typing.get_type_hints(TE, include_extras=True)
    # source should be a Literal of exactly live/diarized
    assert typing.get_args(hints["source"]) == ("live", "diarized")
```

- [ ] **Step 2: Run to verify the literal test fails**

Run: `uv run pytest tests/test_events.py::test_event_source_type_is_literal -v`
Expected: FAIL (source is currently `str`, so `get_args` is empty `()`).

- [ ] **Step 3: Change the type** — in `src/deeptalk/transcript/events.py`:

Change the import line `from typing import Any` to:
```python
from typing import Any, Literal
```
Change the field line `    source: str = "live"  # "live" | "diarized"` to:
```python
    source: Literal["live", "diarized"] = "live"
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_events.py -v`
Expected: PASS (all events tests, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/transcript/events.py tests/test_events.py
git commit -m "refactor: type TranscriptEvent.source as Literal"
```

---

### Task 2: Config + from_env

**Files:**
- Create: `src/deeptalk/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test** — `tests/test_config.py`:

```python
from deeptalk.config import Config


def test_defaults_when_env_empty():
    c = Config.from_env({})
    assert c.stt == "fake"
    assert c.audio == "file"
    assert c.session_id == "demo"
    assert c.db_path == "deeptalk-demo.db"
    assert c.audio_file is None
    assert c.host == "127.0.0.1"
    assert c.port == 8000
    assert c.fixture_path.endswith("fixtures/sample_meeting.jsonl")


def test_reads_overrides_from_env():
    c = Config.from_env({
        "DEEPTALK_STT": "nemotron",
        "DEEPTALK_AUDIO": "mic",
        "DEEPTALK_SESSION_ID": "meeting1",
        "DEEPTALK_DB": "/tmp/x.db",
        "DEEPTALK_AUDIO_FILE": "/tmp/a.wav",
        "DEEPTALK_HOST": "0.0.0.0",
        "DEEPTALK_PORT": "9000",
    })
    assert c.stt == "nemotron"
    assert c.audio == "mic"
    assert c.session_id == "meeting1"
    assert c.db_path == "/tmp/x.db"
    assert c.audio_file == "/tmp/a.wav"
    assert c.host == "0.0.0.0"
    assert c.port == 9000


def test_config_is_frozen():
    import dataclasses, pytest
    c = Config.from_env({})
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.stt = "nemotron"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.config'`

- [ ] **Step 3: Write implementation** — `src/deeptalk/config.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_FIXTURE = str(
    Path(__file__).resolve().parents[2] / "fixtures" / "sample_meeting.jsonl"
)


@dataclass(frozen=True)
class Config:
    """Runtime configuration, sourced from environment variables."""

    stt: str = "fake"  # "fake" | "nemotron"
    audio: str = "file"  # "file" | "mic"
    session_id: str = "demo"
    db_path: str = "deeptalk-demo.db"
    fixture_path: str = _DEFAULT_FIXTURE
    audio_file: str | None = None
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        e = os.environ if env is None else env
        return cls(
            stt=e.get("DEEPTALK_STT", "fake"),
            audio=e.get("DEEPTALK_AUDIO", "file"),
            session_id=e.get("DEEPTALK_SESSION_ID", "demo"),
            db_path=e.get("DEEPTALK_DB", "deeptalk-demo.db"),
            fixture_path=e.get("DEEPTALK_FIXTURE", _DEFAULT_FIXTURE),
            audio_file=e.get("DEEPTALK_AUDIO_FILE"),
            host=e.get("DEEPTALK_HOST", "127.0.0.1"),
            port=int(e.get("DEEPTALK_PORT", "8000")),
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/config.py tests/test_config.py
git commit -m "feat: add env-driven Config"
```

---

### Task 3: AudioSource interface + FileAudioSource

**Files:**
- Create: `src/deeptalk/audio/__init__.py` (empty)
- Create: `src/deeptalk/audio/base.py`
- Create: `src/deeptalk/audio/file_source.py`
- Test: `tests/test_audio_file_source.py`

- [ ] **Step 1: Create the empty package init**

Run: `touch src/deeptalk/audio/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_audio_file_source.py`:

```python
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
            # interleave the same sample twice for stereo
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
    # 80ms @ 16k mono 16-bit = 1280 samples * 2 bytes
    assert len(chunks[0]) == 2560
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
    src = FileAudioSource(str(path))  # default expects 16000
    with pytest.raises(ValueError):
        [c async for c in src.frames()]
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_audio_file_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.audio.file_source'`

- [ ] **Step 4: Write the base interface** — `src/deeptalk/audio/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class AudioSource(ABC):
    """Yields 16 kHz mono 16-bit PCM byte chunks until the source ends."""

    @abstractmethod
    async def frames(self) -> AsyncIterator[bytes]:
        ...
```

- [ ] **Step 5: Write FileAudioSource** — `src/deeptalk/audio/file_source.py`:

```python
from __future__ import annotations

import wave
from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource


class FileAudioSource(AudioSource):
    """Reads a 16 kHz mono 16-bit WAV file and yields fixed-size PCM chunks.

    For dev and tests on machines without a usable microphone.
    """

    def __init__(self, path: str, chunk_ms: int = 80, sample_rate: int = 16000) -> None:
        self._path = path
        self._chunk_ms = chunk_ms
        self._sample_rate = sample_rate

    async def frames(self) -> AsyncIterator[bytes]:
        with wave.open(self._path, "rb") as wf:
            if wf.getnchannels() != 1:
                raise ValueError("audio must be mono")
            if wf.getframerate() != self._sample_rate:
                raise ValueError(f"audio must be {self._sample_rate} Hz")
            if wf.getsampwidth() != 2:
                raise ValueError("audio must be 16-bit PCM")
            frames_per_chunk = int(self._sample_rate * self._chunk_ms / 1000)
            while True:
                data = wf.readframes(frames_per_chunk)
                if not data:
                    break
                yield data
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/test_audio_file_source.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add src/deeptalk/audio/__init__.py src/deeptalk/audio/base.py src/deeptalk/audio/file_source.py tests/test_audio_file_source.py
git commit -m "feat: add AudioSource interface and FileAudioSource"
```

---

### Task 4: SounddeviceSource (microphone)

**Files:**
- Create: `src/deeptalk/audio/mic_source.py`
- Test: `tests/test_mic_source.py`
- Modify: `pyproject.toml` (add `sounddevice`, `numpy` to base deps)

`sounddevice` is imported lazily inside `frames()` so the module imports cleanly on
machines without PortAudio set up, and so tests never open a real device.

- [ ] **Step 1: Add base dependencies**

Run:
```bash
uv add sounddevice numpy
```
Then verify `pyproject.toml` `[project].dependencies` now contains `sounddevice` and `numpy` (in addition to fastapi, uvicorn[standard], websockets). Run `uv sync`.

- [ ] **Step 2: Write the failing test** — `tests/test_mic_source.py`:

```python
from deeptalk.audio.base import AudioSource
from deeptalk.audio.mic_source import SounddeviceSource


def test_is_audiosource_and_constructs_without_opening_device():
    # Constructing must NOT import sounddevice or open the mic.
    src = SounddeviceSource(chunk_ms=80, sample_rate=16000)
    assert isinstance(src, AudioSource)
    assert src.sample_rate == 16000
    assert src.chunk_ms == 80
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_mic_source.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.audio.mic_source'`

- [ ] **Step 4: Write SounddeviceSource** — `src/deeptalk/audio/mic_source.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource


class SounddeviceSource(AudioSource):
    """Captures the default microphone as 16 kHz mono 16-bit PCM chunks.

    sounddevice is imported lazily so this module loads on machines without
    PortAudio, and so tests never open an audio device.
    """

    def __init__(self, chunk_ms: int = 80, sample_rate: int = 16000) -> None:
        self.chunk_ms = chunk_ms
        self.sample_rate = sample_rate
        self._blocksize = int(sample_rate * chunk_ms / 1000)

    async def frames(self) -> AsyncIterator[bytes]:
        import sounddevice as sd

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes] = asyncio.Queue()

        def _callback(indata, frames, time_info, status) -> None:  # noqa: ANN001
            loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

        stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self._blocksize,
            channels=1,
            dtype="int16",
            callback=_callback,
        )
        with stream:
            while True:
                yield await queue.get()
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_mic_source.py -v`
Expected: PASS (1 passed). Confirms construction does not import sounddevice / open a device.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/deeptalk/audio/mic_source.py tests/test_mic_source.py
git commit -m "feat: add SounddeviceSource microphone capture"
```

---

### Task 5: StreamingRecognizer seam + NemotronSttLive orchestration

**Files:**
- Create: `src/deeptalk/stt/recognizer.py`
- Create: `src/deeptalk/stt/nemotron.py`
- Test: `tests/test_nemotron_stt.py`

`NemotronSttLive` contains all the testable orchestration (frame loop → recognizer →
events → timing). The model itself is injected as a `StreamingRecognizer`, so this is
fully tested on the Mac with a fake recognizer.

- [ ] **Step 1: Write the failing test** — `tests/test_nemotron_stt.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_nemotron_stt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.stt.nemotron'`

- [ ] **Step 3: Write the recognizer protocol** — `src/deeptalk/stt/recognizer.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StreamingRecognizer(Protocol):
    """Decodes successive PCM chunks into incremental text.

    Implementations maintain their own streaming state across calls.
    """

    def transcribe_chunk(self, pcm: bytes) -> str:
        """Return newly decoded text for this chunk ('' if none)."""
        ...
```

- [ ] **Step 4: Write NemotronSttLive** — `src/deeptalk/stt/nemotron.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource
from deeptalk.stt.base import SttLive
from deeptalk.stt.recognizer import StreamingRecognizer
from deeptalk.transcript.events import TranscriptEvent


class NemotronSttLive(SttLive):
    """Streams TranscriptEvents from an AudioSource via a StreamingRecognizer.

    All orchestration (frame loop, event construction, timing) lives here and is
    testable with a fake recognizer. The real model is injected as `recognizer`.
    """

    def __init__(
        self,
        session_id: str,
        audio_source: AudioSource,
        recognizer: StreamingRecognizer,
        chunk_ms: int = 80,
    ) -> None:
        self._session_id = session_id
        self._audio = audio_source
        self._recognizer = recognizer
        self._chunk_ms = chunk_ms

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        elapsed = 0.0
        async for frame in self._audio.frames():
            text = self._recognizer.transcribe_chunk(frame)
            if text:
                yield TranscriptEvent(
                    session_id=self._session_id,
                    ts=round(elapsed, 3),
                    text=text,
                    is_final=True,
                    source="live",
                )
            elapsed += self._chunk_ms / 1000.0
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_nemotron_stt.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/deeptalk/stt/recognizer.py src/deeptalk/stt/nemotron.py tests/test_nemotron_stt.py
git commit -m "feat: add StreamingRecognizer seam and NemotronSttLive orchestration"
```

---

### Task 6: NemoCacheAwareRecognizer (VALIDATE ON 3060)

**Files:**
- Create: `src/deeptalk/stt/nemo_recognizer.py`
- Test: `tests/test_nemo_recognizer.py`

**HARDWARE NOTE:** This is the only component not runnable on macOS. NeMo + torch are
imported lazily inside `__init__` (gated behind the `[gpu]` extra, Linux-only). The
decode logic targets NeMo's documented cache-aware streaming API
(`get_initial_cache_state` + `conformer_stream_step`) but is **version-sensitive and
must be validated/adjusted on the 3060**. Mac tests cover only: the module imports
without nemo/torch installed, the class exposes `transcribe_chunk`, and it satisfies
the `StreamingRecognizer` protocol shape.

- [ ] **Step 1: Write the failing test** — `tests/test_nemo_recognizer.py`:

```python
import importlib


def test_module_imports_without_nemo_or_torch():
    # Importing the module must not require torch/nemo (they are imported lazily).
    mod = importlib.import_module("deeptalk.stt.nemo_recognizer")
    assert hasattr(mod, "NemoCacheAwareRecognizer")


def test_class_exposes_transcribe_chunk():
    from deeptalk.stt.nemo_recognizer import NemoCacheAwareRecognizer

    assert callable(getattr(NemoCacheAwareRecognizer, "transcribe_chunk", None))
    assert callable(getattr(NemoCacheAwareRecognizer, "reset", None))
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_nemo_recognizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.stt.nemo_recognizer'`

- [ ] **Step 3: Write the adapter** — `src/deeptalk/stt/nemo_recognizer.py`:

```python
from __future__ import annotations

# VALIDATE ON 3060: This recognizer requires CUDA + the `[gpu]` extra
# (torch, nemo_toolkit[asr]) and cannot run on the macOS dev box. The NeMo
# cache-aware streaming API is version-sensitive; if a call signature differs on
# the installed NeMo, adjust here. Reference:
#   tutorials/asr/Online_ASR_Microphone_Demo_Cache_Aware_Streaming.ipynb
#   examples/asr/asr_cache_aware_streaming/speech_to_text_cache_aware_streaming_infer.py

# Maps desired right-context (frames) -> att_context_size. Larger = more accurate,
# higher latency. 13 -> ~1.12s chunk (best WER); 0 -> ~0.08s (lowest latency).
_ATT_CONTEXT = {0: [70, 0], 1: [70, 1], 6: [70, 6], 13: [70, 13]}


class NemoCacheAwareRecognizer:
    """Real nemotron-speech-streaming recognizer using NeMo cache-aware streaming."""

    def __init__(
        self,
        model_name: str = "nvidia/nemotron-speech-streaming-en-0.6b",
        right_context: int = 13,
        sample_rate: int = 16000,
    ) -> None:
        import numpy as np
        import torch
        import nemo.collections.asr as nemo_asr

        self._np = np
        self._torch = torch
        self._sample_rate = sample_rate

        self._model = nemo_asr.models.ASRModel.from_pretrained(model_name)
        self._model.eval()
        self._model.encoder.setup_streaming_params(
            att_context_size=_ATT_CONTEXT[right_context]
        )
        self.reset()

    def reset(self) -> None:
        (
            self._cache_last_channel,
            self._cache_last_time,
            self._cache_last_channel_len,
        ) = self._model.encoder.get_initial_cache_state(batch_size=1)
        self._prev_hyp = None

    def transcribe_chunk(self, pcm: bytes) -> str:
        audio = self._np.frombuffer(pcm, dtype=self._np.int16)
        signal = self._torch.tensor(
            audio.astype(self._np.float32) / 32768.0
        ).unsqueeze(0)
        signal_len = self._torch.tensor([signal.shape[1]])

        with self._torch.no_grad():
            (
                transcribed,
                self._cache_last_channel,
                self._cache_last_time,
                self._cache_last_channel_len,
                self._prev_hyp,
            ) = self._model.conformer_stream_step(
                processed_signal=signal,
                processed_signal_length=signal_len,
                cache_last_channel=self._cache_last_channel,
                cache_last_time=self._cache_last_time,
                cache_last_channel_len=self._cache_last_channel_len,
                keep_all_outputs=True,
                previous_hypotheses=self._prev_hyp,
                return_transcription=True,
            )
        if not transcribed:
            return ""
        first = transcribed[0]
        return first if isinstance(first, str) else getattr(first, "text", "")
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_nemo_recognizer.py -v`
Expected: PASS (2 passed) — the module imports without torch/nemo because they are
imported lazily inside `__init__`.

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/stt/nemo_recognizer.py tests/test_nemo_recognizer.py
git commit -m "feat: add NeMo cache-aware recognizer (validate on GPU)"
```

---

### Task 7: STT/audio factory

**Files:**
- Create: `src/deeptalk/stt/factory.py`
- Test: `tests/test_stt_factory.py`

- [ ] **Step 1: Write the failing test** — `tests/test_stt_factory.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_stt_factory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.stt.factory'`

- [ ] **Step 3: Write the factory** — `src/deeptalk/stt/factory.py`:

```python
from __future__ import annotations

from deeptalk.audio.base import AudioSource
from deeptalk.config import Config
from deeptalk.stt.base import SttLive
from deeptalk.stt.fake import FakeSttLive


def build_audio_source(config: Config) -> AudioSource:
    if config.audio == "file":
        from deeptalk.audio.file_source import FileAudioSource

        if not config.audio_file:
            raise ValueError("DEEPTALK_AUDIO_FILE is required when DEEPTALK_AUDIO=file")
        return FileAudioSource(config.audio_file)
    if config.audio == "mic":
        from deeptalk.audio.mic_source import SounddeviceSource

        return SounddeviceSource()
    raise ValueError(f"unknown audio source: {config.audio}")


def build_stt(config: Config) -> SttLive:
    if config.stt == "fake":
        return FakeSttLive(
            session_id=config.session_id,
            fixture_path=config.fixture_path,
            realtime=True,
        )
    if config.stt == "nemotron":
        # Imported here so the nemo/torch import only happens on the GPU box.
        from deeptalk.stt.nemo_recognizer import NemoCacheAwareRecognizer
        from deeptalk.stt.nemotron import NemotronSttLive

        audio = build_audio_source(config)
        return NemotronSttLive(
            session_id=config.session_id,
            audio_source=audio,
            recognizer=NemoCacheAwareRecognizer(),
        )
    raise ValueError(f"unknown stt: {config.stt}")
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_stt_factory.py -v`
Expected: PASS (5 passed). The `nemotron` branch is exercised on the 3060 (it needs
NeMo); on the Mac only the `fake`/`file`/error paths are tested.

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/stt/factory.py tests/test_stt_factory.py
git commit -m "feat: add STT and audio-source factory"
```

---

### Task 8: GPU extra + lifespan entrypoint wiring

**Files:**
- Modify: `pyproject.toml` (add `[project.optional-dependencies] gpu`)
- Modify: `src/deeptalk/server/app.py` (accept optional `lifespan`)
- Modify: `src/deeptalk/server/__main__.py` (Config + factory + lifespan)
- Test: `tests/test_app_lifespan.py`

- [ ] **Step 1: Add the GPU optional-dependency group to `pyproject.toml`**

Add this block to `pyproject.toml` (after the `[project]` table, before `[dependency-groups]`):

```toml
[project.optional-dependencies]
gpu = [
    "torch ; sys_platform == 'linux'",
    "nemo_toolkit[asr] ; sys_platform == 'linux'",
]
```

Then run `uv sync` (on macOS the markers exclude torch/nemo, so this is a no-op
install — confirm it does NOT try to install torch). Expected: sync succeeds, no
torch/nemo pulled on Mac.

- [ ] **Step 2: Write the failing test** — `tests/test_app_lifespan.py`:

```python
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from deeptalk.bus import EventBus
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def test_create_app_runs_lifespan(tmp_path):
    started = {"value": False}

    @asynccontextmanager
    async def _lifespan(app):
        started["value"] = True
        yield

    store = TranscriptStore(str(tmp_path / "t.db"))
    app = create_app(store=store, bus=EventBus(), lifespan=_lifespan)

    # Entering the TestClient context triggers the lifespan.
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
    assert started["value"] is True


def test_create_app_without_lifespan_still_works(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    app = create_app(store=store, bus=EventBus())
    client = TestClient(app)
    assert client.get("/health").status_code == 200
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_app_lifespan.py -v`
Expected: FAIL — `create_app()` does not yet accept a `lifespan` argument
(`TypeError: create_app() got an unexpected keyword argument 'lifespan'`).

- [ ] **Step 4: Update `create_app`** — in `src/deeptalk/server/app.py`:

Change the imports at the top to add `Callable`/`Any` typing and keep existing ones:
```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from deeptalk.bus import EventBus
from deeptalk.transcript.store import TranscriptStore
```
Change the `create_app` signature line:
```python
def create_app(store: TranscriptStore, bus: EventBus) -> FastAPI:
```
to:
```python
def create_app(
    store: TranscriptStore,
    bus: EventBus,
    lifespan: Callable[[FastAPI], Any] | None = None,
) -> FastAPI:
```
and change the body line `    app = FastAPI(title="DeepTalk")` to:
```python
    app = FastAPI(title="DeepTalk", lifespan=lifespan)
```
Leave the rest of the file (the `stream_transcript` helper, `/health`, and the
WebSocket route) unchanged. (The `Awaitable`/`Any` imports may already exist from
Phase 1's `stream_transcript`; do not duplicate them.)

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_app_lifespan.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Rewrite the entrypoint** — replace `src/deeptalk/server/__main__.py` entirely with:

```python
from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

import uvicorn

from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.ingest import run_ingest
from deeptalk.server.app import create_app
from deeptalk.stt.factory import build_stt
from deeptalk.transcript.store import TranscriptStore


def main() -> None:
    config = Config.from_env()
    store = TranscriptStore(config.db_path)
    bus = EventBus()

    @asynccontextmanager
    async def lifespan(app):
        stt = build_stt(config)
        task = asyncio.create_task(run_ingest(stt, store, bus))
        app.state.ingest_task = task
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = create_app(store=store, bus=bus, lifespan=lifespan)
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest -q`
Expected: all green (Phase 1's 22 + the new Phase 2A tests).

- [ ] **Step 8: Manual smoke (fake STT path still works end-to-end)**

```bash
uv run python -m deeptalk.server > /tmp/deeptalk-2a.log 2>&1 &
SERVER_PID=$!
sleep 6
curl -s http://127.0.0.1:8000/health
uv run python -c "from deeptalk.transcript.store import TranscriptStore; print([e.text for e in TranscriptStore('deeptalk-demo.db').all_events('demo')])"
kill $SERVER_PID 2>/dev/null
```
Expected: `{"status":"ok"}` and the 3 fixture lines. If anything fails, paste the tail
of `/tmp/deeptalk-2a.log`.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock src/deeptalk/server/app.py src/deeptalk/server/__main__.py tests/test_app_lifespan.py
git commit -m "feat: lifespan entrypoint wired to Config and STT factory; add gpu extra"
```

---

## On the RTX 3060 (post-merge hardware validation)

Not part of the Mac build, but the acceptance for the NeMo path:

```bash
git pull
uv sync --extra gpu                      # installs torch + nemo (Linux/CUDA)
# transcribe a WAV file through the real model:
DEEPTALK_STT=nemotron DEEPTALK_AUDIO=file DEEPTALK_AUDIO_FILE=/path/to/16k_mono.wav \
  uv run python -m deeptalk.server
# or live mic:
DEEPTALK_STT=nemotron DEEPTALK_AUDIO=mic uv run python -m deeptalk.server
# open http://127.0.0.1:8000/health and watch the transcript via the WebSocket
```
If `conformer_stream_step` / `get_initial_cache_state` signatures differ on the
installed NeMo version, adjust `src/deeptalk/stt/nemo_recognizer.py` (Task 6) — that
is the expected validation point.

---

## Self-Review

**Spec coverage (Phase 2A subset):** Implements spec §6 Audio Capture (Tasks 3-4),
the real STT-Live tier via the §5 nemotron model behind the §7 `SttLive` seam (Tasks
5-6), runtime selection (Tasks 2, 7), and addresses Phase-1 review follow-ups
(Literal `source` Task 1; lifespan replacing deprecated `on_event` Task 8). VibeVoice
diarization, orchestrator, router, agents, wiki remain later phases — not gaps. The
UI is Plan 2B.

**Placeholder scan:** No TBD/TODO. The single deliberate exception is Task 6's NeMo
binding, explicitly scoped as hardware-validated with a documented reference and a
real best-effort implementation — its Mac tests (import/lazy-load/protocol) are real
and complete. Every other step has exact code + commands + expected output.

**Type consistency:** `StreamingRecognizer.transcribe_chunk(pcm: bytes) -> str` is
defined in Task 5 and used identically by `_FakeRecognizer` (Task 5 test) and
`NemoCacheAwareRecognizer` (Task 6). `AudioSource.frames() -> AsyncIterator[bytes]`
(Task 3) is implemented by `FileAudioSource` (Task 3) and `SounddeviceSource` (Task 4)
and consumed by `NemotronSttLive` (Task 5). `Config` fields (Task 2) are read by the
factory (Task 7) and entrypoint (Task 8) with matching names (`stt`, `audio`,
`audio_file`, `session_id`, `fixture_path`, `db_path`, `host`, `port`).
`build_stt(config)` / `build_audio_source(config)` signatures match between Task 7 and
Task 8. `create_app(store, bus, lifespan=None)` is consistent between Task 8's change
and its use in the entrypoint and tests.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase2a-live-stt.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
