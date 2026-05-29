# DeepTalk Phase 6A — Session Wiki + Diarization (backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a session wiki (topics / decisions / action items) from the transcript + artifacts, and add speaker diarization. A `POST /finalize` builds + persists the wiki (and, if a recording exists, diarizes it into speaker-labelled transcript events); `GET /wiki` returns it. The wiki builder is fully Mac-testable with the fake provider; the VibeVoice diarizer is isolated as validate-on-hardware.

**Architecture:** `build_wiki` summarizes the transcript text + artifact titles via the router's `complete()` into a structured `Wiki`, persisted by `WikiStore` (one row per session). A `Diarizer` seam (`FakeDiarizer` for tests, `VibeVoiceDiarizer` for the GPU box) turns a recorded WAV into `DiarizedSegment`s. `RecordingAudioSource` tees live mic frames to a WAV so there's something to diarize. `POST /finalize` orchestrates: build wiki always; diarize + append `source="diarized"` transcript events when a recording + diarizer are present.

**Tech Stack:** Python 3.12, uv, FastAPI, pytest + pytest-asyncio, stdlib `wave`; VibeVoice via `transformers` (the `[gpu]` extra, validate-on-hardware).

---

## Roadmap context

Phase 6A of spec §15 phase 6. Phases 1–5 on `main`. This adds the §7 STT-Diarize (#3) and Wiki Builder (#10). The wiki UI tab is Phase 6B. GPU lease/error hardening is Phase 7; mockup agent is Phase 8.

## Validation note

Wiki builder, store, recording, finalize, fake diarizer = fully Mac-tested. The only unrun piece is `VibeVoiceDiarizer` (needs CUDA + `transformers`, validate-on-hardware) — unit-tested for import + protocol only, flagged in-code, exactly like the NeMo recognizer.

## File Structure (Phase 6A)

```
deeptalk/
  src/deeptalk/
    config.py                       # MODIFY: diarize + recording_path fields
    llm/factory.py                  # MODIFY: add "wiki" route
    llm/fake.py                     # MODIFY: extend JSON stub with wiki keys
    wiki/
      __init__.py                   # NEW
      models.py                     # NEW: Wiki
      builder.py                    # NEW: build_wiki
      store.py                      # NEW: WikiStore (SQLite, upsert per session)
    diarize/
      __init__.py                   # NEW
      models.py                     # NEW: DiarizedSegment
      base.py                       # NEW: Diarizer Protocol
      fake.py                       # NEW: FakeDiarizer
      vibevoice.py                  # NEW: VibeVoiceDiarizer (validate-on-hardware)
    audio/recording.py              # NEW: RecordingAudioSource
    server/app.py                   # MODIFY: /finalize, /wiki, deps
    server/__main__.py              # MODIFY: wiki_store, diarizer, recording wiring
  tests/
    test_wiki_builder.py            # NEW
    test_wiki_store.py              # NEW
    test_diarizer.py                # NEW
    test_recording.py               # NEW
    test_finalize_wiki.py           # NEW
```

---

### Task 1: Wiki model + builder + router route + stub

**Files:**
- Create: `src/deeptalk/wiki/__init__.py` (empty), `src/deeptalk/wiki/models.py`, `src/deeptalk/wiki/builder.py`
- Modify: `src/deeptalk/llm/factory.py`, `src/deeptalk/llm/fake.py`
- Test: `tests/test_wiki_builder.py`

- [ ] **Step 1: Create the package init**

Run: `touch src/deeptalk/wiki/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_wiki_builder.py`:

```python
from deeptalk.wiki.builder import build_wiki
from deeptalk.wiki.models import Wiki
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter


def _router(provider):
    return ModelRouter(providers={"p": provider}, routes={"wiki": ["p"]}, default=["p"])


async def test_build_wiki_from_completion():
    provider = FakeLlmProvider(
        completion='{"topics": ["db choice"], "decisions": ["use postgres"], "action_items": ["set up CI"]}'
    )
    wiki = await build_wiki(
        "s1", ["should we use postgres or sqlite"], ["search: postgres vs sqlite"], _router(provider), now=1.0
    )
    assert isinstance(wiki, Wiki)
    assert wiki.session_id == "s1"
    assert wiki.topics == ["db choice"]
    assert wiki.decisions == ["use postgres"]
    assert wiki.action_items == ["set up CI"]
    assert wiki.created_at == 1.0


async def test_build_wiki_empty_on_failure():
    class Boom:
        name = "boom"

        async def complete(self, prompt):
            raise RuntimeError("model down")

    wiki = await build_wiki("s1", ["hi"], [], _router(Boom()), now=0.0)
    assert wiki.topics == [] and wiki.decisions == [] and wiki.action_items == []


async def test_build_wiki_handles_empty_transcript():
    provider = FakeLlmProvider(completion='{"topics": [], "decisions": [], "action_items": []}')
    wiki = await build_wiki("s1", [], [], _router(provider), now=2.0)
    assert wiki.topics == []
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_wiki_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.wiki.builder'`

- [ ] **Step 4: Write the model** — `src/deeptalk/wiki/models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Wiki:
    session_id: str
    topics: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 5: Write the builder** — `src/deeptalk/wiki/builder.py`:

```python
from __future__ import annotations

from deeptalk.agents.common import parse_json
from deeptalk.llm.router import ModelRouter, run_with_fallback
from deeptalk.wiki.models import Wiki

AGENT = "wiki"

_PROMPT = (
    "You are summarizing a meeting. Transcript lines:\n{transcript}\n\n"
    "Assistant findings:\n{artifacts}\n\n"
    "Produce a concise wiki. Respond ONLY as JSON: "
    '{{"topics": ["..."], "decisions": ["..."], "action_items": ["..."]}}.'
)


async def build_wiki(
    session_id: str,
    transcript_lines: list[str],
    artifact_titles: list[str],
    router: ModelRouter,
    now: float,
) -> Wiki:
    prompt = _PROMPT.format(
        transcript="\n".join(transcript_lines) or "(none)",
        artifacts="\n".join(artifact_titles) or "(none)",
    )
    data: dict = {}
    try:
        providers = router.chain_for(AGENT)
        raw = await run_with_fallback(providers, lambda p: p.complete(prompt))
        data = parse_json(raw) or {}
    except Exception:  # noqa: BLE001 - wiki is best-effort; empty on failure
        data = {}
    return Wiki(
        session_id=session_id,
        topics=data.get("topics", []),
        decisions=data.get("decisions", []),
        action_items=data.get("action_items", []),
        created_at=now,
    )
```

- [ ] **Step 6: Add the `wiki` route** — in `src/deeptalk/llm/factory.py`, add `"wiki": chain` to the routes dict:

```python
    return ModelRouter(
        providers=providers,
        routes={"search": chain, "intent": chain, "proscons": chain, "planning": chain, "wiki": chain},
        default=chain,
    )
```

- [ ] **Step 7: Extend the fake JSON stub** — in `src/deeptalk/llm/fake.py`, add the wiki keys to `_JSON_STUB` so a default-fake wiki is populated. Change `_JSON_STUB` to:

```python
_JSON_STUB = (
    '{"is_search": false, "kind": "none", "query": "", '
    '"pros": ["fake pro"], "cons": ["fake con"], '
    '"recommendation": "fake recommendation", '
    '"steps": ["fake step one", "fake step two"], '
    '"topics": ["fake topic"], "decisions": ["fake decision"], '
    '"action_items": ["fake action item"]}'
)
```

- [ ] **Step 8: Run to verify it passes + full suite**

Run: `uv run pytest tests/test_wiki_builder.py -v && uv run pytest -q`
Expected: wiki builder 3 passed; full suite green (the stub change only adds keys — existing tests assert specific keys, unaffected).

- [ ] **Step 9: Commit**

```bash
git add src/deeptalk/wiki/__init__.py src/deeptalk/wiki/models.py src/deeptalk/wiki/builder.py src/deeptalk/llm/factory.py src/deeptalk/llm/fake.py tests/test_wiki_builder.py
git commit -m "feat: add session Wiki model and LLM wiki builder"
```

---

### Task 2: WikiStore

**Files:**
- Create: `src/deeptalk/wiki/store.py`
- Test: `tests/test_wiki_store.py`

- [ ] **Step 1: Write the failing test** — `tests/test_wiki_store.py`:

```python
from deeptalk.wiki.models import Wiki
from deeptalk.wiki.store import WikiStore


def _wiki(session="s1", topics=None):
    return Wiki(
        session_id=session,
        topics=topics if topics is not None else ["t1"],
        decisions=["d1"],
        action_items=["a1"],
        created_at=1.0,
    )


def test_save_and_get(tmp_path):
    store = WikiStore(str(tmp_path / "w.db"))
    store.save(_wiki())
    got = store.get("s1")
    assert got is not None
    assert got.topics == ["t1"]
    assert got.decisions == ["d1"]
    assert got.action_items == ["a1"]


def test_get_missing_returns_none(tmp_path):
    store = WikiStore(str(tmp_path / "w.db"))
    assert store.get("nope") is None


def test_save_replaces_existing(tmp_path):
    store = WikiStore(str(tmp_path / "w.db"))
    store.save(_wiki(topics=["old"]))
    store.save(_wiki(topics=["new"]))
    assert store.get("s1").topics == ["new"]


def test_persists_across_instances(tmp_path):
    db = str(tmp_path / "w.db")
    WikiStore(db).save(_wiki(topics=["persisted"]))
    assert WikiStore(db).get("s1").topics == ["persisted"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_wiki_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.wiki.store'`

- [ ] **Step 3: Write the store** — `src/deeptalk/wiki/store.py`:

```python
from __future__ import annotations

import json
import sqlite3

from deeptalk.wiki.models import Wiki

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki (
    session_id   TEXT PRIMARY KEY,
    topics       TEXT NOT NULL,
    decisions    TEXT NOT NULL,
    action_items TEXT NOT NULL,
    created_at   REAL NOT NULL
);
"""


class WikiStore:
    """One wiki per session; save() upserts."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save(self, wiki: Wiki) -> None:
        self._conn.execute(
            "INSERT INTO wiki (session_id, topics, decisions, action_items, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "topics=excluded.topics, decisions=excluded.decisions, "
            "action_items=excluded.action_items, created_at=excluded.created_at",
            (
                wiki.session_id,
                json.dumps(wiki.topics),
                json.dumps(wiki.decisions),
                json.dumps(wiki.action_items),
                wiki.created_at,
            ),
        )
        self._conn.commit()

    def get(self, session_id: str) -> Wiki | None:
        row = self._conn.execute(
            "SELECT session_id, topics, decisions, action_items, created_at "
            "FROM wiki WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return Wiki(
            session_id=row["session_id"],
            topics=json.loads(row["topics"]),
            decisions=json.loads(row["decisions"]),
            action_items=json.loads(row["action_items"]),
            created_at=row["created_at"],
        )

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_wiki_store.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/wiki/store.py tests/test_wiki_store.py
git commit -m "feat: add WikiStore"
```

---

### Task 3: Diarizer seam + VibeVoice adapter

**Files:**
- Create: `src/deeptalk/diarize/__init__.py` (empty), `models.py`, `base.py`, `fake.py`, `vibevoice.py`
- Test: `tests/test_diarizer.py`

- [ ] **Step 1: Create the package init**

Run: `touch src/deeptalk/diarize/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_diarizer.py`:

```python
import importlib

from deeptalk.diarize.base import Diarizer
from deeptalk.diarize.fake import FakeDiarizer
from deeptalk.diarize.models import DiarizedSegment


async def test_fake_diarizer_returns_segments():
    segs = [DiarizedSegment(speaker=0, start=0.0, end=1.0, text="hello")]
    d = FakeDiarizer(segs)
    out = await d.diarize("/any/path.wav")
    assert out == segs


def test_fake_satisfies_protocol():
    assert isinstance(FakeDiarizer([]), Diarizer)


def test_vibevoice_module_imports_without_transformers():
    mod = importlib.import_module("deeptalk.diarize.vibevoice")
    assert hasattr(mod, "VibeVoiceDiarizer")


def test_vibevoice_exposes_diarize():
    from deeptalk.diarize.vibevoice import VibeVoiceDiarizer

    assert callable(getattr(VibeVoiceDiarizer, "diarize", None))
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_diarizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.diarize.base'`

- [ ] **Step 4: Write the model** — `src/deeptalk/diarize/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiarizedSegment:
    speaker: int
    start: float
    end: float
    text: str
```

- [ ] **Step 5: Write the interface** — `src/deeptalk/diarize/base.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from deeptalk.diarize.models import DiarizedSegment


@runtime_checkable
class Diarizer(Protocol):
    async def diarize(self, audio_path: str) -> list[DiarizedSegment]:
        """Transcribe + diarize a WAV file into speaker-labelled segments."""
        ...
```

- [ ] **Step 6: Write the fake** — `src/deeptalk/diarize/fake.py`:

```python
from __future__ import annotations

from deeptalk.diarize.models import DiarizedSegment


class FakeDiarizer:
    """Returns canned segments — for dev/tests without a GPU."""

    def __init__(self, segments: list[DiarizedSegment]) -> None:
        self._segments = segments

    async def diarize(self, audio_path: str) -> list[DiarizedSegment]:
        return list(self._segments)
```

- [ ] **Step 7: Write the VibeVoice adapter** — `src/deeptalk/diarize/vibevoice.py`:

```python
from __future__ import annotations

# VALIDATE ON 3060: VibeVoice-ASR needs CUDA + transformers>=5.3.0 (the [gpu] extra)
# and is not exercised by the Mac suite. transformers is imported lazily. The model's
# JSON output shape ([{"Start","End","Speaker","Content"}]) is version-sensitive;
# adjust parsing here if a real run returns a different structure.
# Model: microsoft/VibeVoice-ASR-HF

import json
import re

from deeptalk.diarize.models import DiarizedSegment


class VibeVoiceDiarizer:
    """Batch diarization with VibeVoice-ASR (who/when/what)."""

    def __init__(self, model_name: str = "microsoft/VibeVoice-ASR-HF") -> None:
        self._model_name = model_name

    async def diarize(self, audio_path: str) -> list[DiarizedSegment]:
        import torch  # noqa: F401
        from transformers import pipeline

        asr = pipeline("automatic-speech-recognition", model=self._model_name)
        result = asr(audio_path)
        raw = result["text"] if isinstance(result, dict) else str(result)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            rows = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        return [
            DiarizedSegment(
                speaker=int(r.get("Speaker", 0)),
                start=float(r.get("Start", 0.0)),
                end=float(r.get("End", 0.0)),
                text=str(r.get("Content", "")),
            )
            for r in rows
        ]
```

- [ ] **Step 8: Run to verify it passes**

Run: `uv run pytest tests/test_diarizer.py -v`
Expected: PASS (4 passed) — `vibevoice` imports because torch/transformers are lazy.

- [ ] **Step 9: Commit**

```bash
git add src/deeptalk/diarize tests/test_diarizer.py
git commit -m "feat: add Diarizer seam, FakeDiarizer, VibeVoice adapter"
```

---

### Task 4: RecordingAudioSource

**Files:**
- Create: `src/deeptalk/audio/recording.py`
- Test: `tests/test_recording.py`

- [ ] **Step 1: Write the failing test** — `tests/test_recording.py`:

```python
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
    # the recorded WAV is readable, mono/16k/16-bit, and holds all the audio
    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2
        assert wf.getnframes() == 16000 * 0.16
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_recording.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.audio.recording'`

- [ ] **Step 3: Write it** — `src/deeptalk/audio/recording.py`:

```python
from __future__ import annotations

import wave
from collections.abc import AsyncIterator

from deeptalk.audio.base import AudioSource


class RecordingAudioSource(AudioSource):
    """Wraps an AudioSource, passing frames through while teeing them to a WAV file.

    Gives the post-session diarizer something to read.
    """

    def __init__(self, inner: AudioSource, path: str, sample_rate: int = 16000) -> None:
        self._inner = inner
        self._path = path
        self._sample_rate = sample_rate

    async def frames(self) -> AsyncIterator[bytes]:
        wf = wave.open(self._path, "wb")
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(self._sample_rate)
        try:
            async for frame in self._inner.frames():
                wf.writeframes(frame)
                yield frame
        finally:
            wf.close()
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_recording.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/audio/recording.py tests/test_recording.py
git commit -m "feat: add RecordingAudioSource (tee mic to WAV)"
```

---

### Task 5: /finalize + /wiki endpoints + wiring

**Files:**
- Modify: `src/deeptalk/config.py`, `src/deeptalk/server/app.py`, `src/deeptalk/server/__main__.py`
- Test: `tests/test_finalize_wiki.py`

- [ ] **Step 1: Extend `Config`** — add fields after `intent_detector`:

```python
    diarize: str = "off"  # "off" | "vibevoice"
    recording_path: str | None = None
```
And in `from_env`:
```python
            diarize=e.get("DEEPTALK_DIARIZE", "off"),
            recording_path=e.get("DEEPTALK_RECORDING"),
```

- [ ] **Step 2: Write the failing test** — `tests/test_finalize_wiki.py`:

```python
from fastapi.testclient import TestClient

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.diarize.fake import FakeDiarizer
from deeptalk.diarize.models import DiarizedSegment
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter
from deeptalk.server.app import create_app
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore
from deeptalk.wiki.store import WikiStore


def _deps(tmp_path, diarizer=None, recording=None):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(TranscriptEvent(session_id="s1", ts=0.0, text="should we use postgres", is_final=True))
    astore = ArtifactStore(str(tmp_path / "a.db"))
    astore.append(Artifact(id="x", session_id="s1", agent="search", status="done", title="postgres", payload={}, created_at=0.0))
    return {
        "store": store,
        "bus": EventBus(),
        "artifact_store": astore,
        "artifact_bus": EventBus(),
        "router": ModelRouter(providers={"fake": FakeLlmProvider()}, routes={"wiki": ["fake"]}, default=["fake"]),
        "wiki_store": WikiStore(str(tmp_path / "w.db")),
        "diarizer": diarizer,
        "recording_path": recording,
    }


def test_finalize_builds_and_persists_wiki(tmp_path):
    deps = _deps(tmp_path)
    app = create_app(**deps)
    client = TestClient(app)

    resp = client.post("/finalize", json={"session_id": "s1"})
    assert resp.status_code == 200

    wiki = client.get("/wiki?session_id=s1").json()
    assert "topics" in wiki and "decisions" in wiki and "action_items" in wiki
    # default fake stub populates these
    assert wiki["topics"] == ["fake topic"]


def test_wiki_404_when_absent(tmp_path):
    deps = _deps(tmp_path)
    app = create_app(**deps)
    client = TestClient(app)
    assert client.get("/wiki?session_id=never").status_code == 404


def test_finalize_diarizes_when_recording_present(tmp_path):
    rec = tmp_path / "rec.wav"
    rec.write_bytes(b"")  # presence is enough; FakeDiarizer ignores contents
    segs = [DiarizedSegment(speaker=2, start=0.0, end=1.0, text="diarized line")]
    deps = _deps(tmp_path, diarizer=FakeDiarizer(segs), recording=str(rec))
    app = create_app(**deps)
    client = TestClient(app)

    client.post("/finalize", json={"session_id": "s1"})

    # diarized segments are appended as transcript events with source="diarized"
    events = deps["store"].all_events("s1")
    diarized = [e for e in events if e.source == "diarized"]
    assert len(diarized) == 1
    assert diarized[0].speaker == 2
    assert diarized[0].text == "diarized line"
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_finalize_wiki.py -v`
Expected: FAIL — `create_app()` has no `wiki_store`/`diarizer`/`recording_path` params, no `/finalize` or `/wiki`.

- [ ] **Step 4: Update `src/deeptalk/server/app.py`**

Add imports near the top:
```python
from pathlib import Path as _Path

from deeptalk.diarize.base import Diarizer
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.wiki.store import WikiStore
```
Add a request model near `AskRequest`:
```python
class FinalizeRequest(BaseModel):
    session_id: str
```
Extend the `create_app` signature with three optional params (after `now_fn`):
```python
    wiki_store: "WikiStore | None" = None,
    diarizer: "Diarizer | None" = None,
    recording_path: str | None = None,
```
Inside `create_app`, before the UI mount / `return app`, add the two routes (only register when the wiki store is configured):
```python
    if wiki_store is not None and router is not None and artifact_store is not None:

        @app.post("/finalize")
        async def finalize(req: FinalizeRequest) -> dict[str, str]:
            from deeptalk.wiki.builder import build_wiki

            clock = now_fn or _time.time
            lines = [e.text for e in store.all_events(req.session_id) if e.is_final]
            titles = [a.title for a in artifact_store.all_artifacts(req.session_id)]
            wiki = await build_wiki(req.session_id, lines, titles, router, clock())
            wiki_store.save(wiki)

            if diarizer is not None and recording_path and _Path(recording_path).is_file():
                segments = await diarizer.diarize(recording_path)
                for seg in segments:
                    store.append(
                        TranscriptEvent(
                            session_id=req.session_id,
                            ts=seg.start,
                            text=seg.text,
                            is_final=True,
                            source="diarized",
                            speaker=seg.speaker,
                        )
                    )
            return {"status": "ok"}

        @app.get("/wiki")
        async def get_wiki(session_id: str = "default") -> dict:
            wiki = wiki_store.get(session_id)
            if wiki is None:
                raise HTTPException(status_code=404, detail="no wiki for session")
            return wiki.to_dict()
```
Keep the UI mount LAST.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_finalize_wiki.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Wire the entrypoint** — in `src/deeptalk/server/__main__.py`:

Add imports:
```python
from deeptalk.wiki.store import WikiStore
from deeptalk.audio.recording import RecordingAudioSource
```
In `main()`, after `router = build_router(config)`, add:
```python
    wiki_store = WikiStore(config.db_path)
    diarizer = None
    if config.diarize == "vibevoice":
        from deeptalk.diarize.vibevoice import VibeVoiceDiarizer

        diarizer = VibeVoiceDiarizer()
```
Pass them to `create_app(...)` (add to the existing call):
```python
        wiki_store=wiki_store,
        diarizer=diarizer,
        recording_path=config.recording_path,
```
Inside the `lifespan`, wrap the STT's audio with recording when configured. Change `stt = build_stt(config)` handling: if `config.recording_path` and `config.audio == "mic"` and `config.stt == "nemotron"`, the recording must wrap the mic source. The simplest, least-invasive approach: leave `build_stt` as-is for now (recording wrap is exercised on hardware); set `recording_path` so `/finalize` can diarize an externally-recorded file. (Full auto-record wiring is validated on the GPU box.) So no lifespan change is required for this task beyond passing `recording_path` to `create_app`.

(If you want auto-record now: that requires `build_stt` to accept a pre-built audio source — out of scope here; note it as a follow-up.)

- [ ] **Step 7: Full suite + smoke**

Run: `uv run pytest -q`
Expected: all green.

Smoke — finalize builds a wiki from the fixture session (default fake):
```bash
rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-6a.log 2>&1 &
SERVER_PID=$!
sleep 8
curl -s -X POST http://127.0.0.1:8000/finalize -H 'content-type: application/json' -d '{"session_id":"demo"}' ; echo
curl -s "http://127.0.0.1:8000/wiki?session_id=demo" ; echo
kill $SERVER_PID 2>/dev/null
```
Expected: finalize `{"status":"ok"}`; wiki JSON with topics/decisions/action_items (fake-stub values). Paste `/tmp/deeptalk-6a.log` tail on failure.

- [ ] **Step 8: Commit**

```bash
git add src/deeptalk/config.py src/deeptalk/server/app.py src/deeptalk/server/__main__.py tests/test_finalize_wiki.py
git commit -m "feat: add /finalize (wiki + diarize) and /wiki endpoints"
```

---

## On the GPU box (real diarization)

```bash
# record a meeting to a WAV (or point DEEPTALK_RECORDING at one), then:
DEEPTALK_DIARIZE=vibevoice DEEPTALK_RECORDING=/path/meeting.wav \
  DEEPTALK_SEARCH_PROVIDER=anthropic uv run python -m deeptalk.server
curl -X POST localhost:8000/finalize -d '{"session_id":"demo"}' -H 'content-type: application/json'
# diarized speaker-labelled lines are appended; the wiki summarizes the session
```
If VibeVoice's output shape differs, adjust parsing in `src/deeptalk/diarize/vibevoice.py`.

---

## Self-Review

**Spec coverage (Phase 6A):** Adds §7 Wiki Builder (#10, Tasks 1–2, 5) and STT-Diarize (#3, Tasks 3–4, wired in 5). The wiki UI tab is Phase 6B; auto-recording the live mic into the diarizer is noted as a follow-up (validated on hardware). GPU lease/error hardening is Phase 7.

**Placeholder scan:** No TBD/TODO. `VibeVoiceDiarizer` is the validate-on-hardware piece (lazy transformers, import/protocol tested), flagged in-code. The auto-record-during-live-mic wiring is explicitly deferred with a rationale, not silently skipped. Every step has exact code + commands + expected output.

**Type consistency:** `Wiki(session_id, topics, decisions, action_items, created_at)` + `to_dict` (Task 1) used by `WikiStore` (Task 2), `/wiki`, and `/finalize` (Task 5). `build_wiki(session_id, transcript_lines, artifact_titles, router, now)` (Task 1) called by `/finalize` (Task 5). `Diarizer.diarize(audio_path) -> list[DiarizedSegment]` (Task 3) implemented by `FakeDiarizer` + `VibeVoiceDiarizer`, consumed by `/finalize`. `DiarizedSegment(speaker, start, end, text)` maps onto `TranscriptEvent(source="diarized", speaker=...)` whose schema already has `source`/`speaker` columns (Phase 1). `create_app(..., wiki_store, diarizer, recording_path)` consistent between Task 5 and the entrypoint. The router gains a `"wiki"` route (Task 1) used by `build_wiki`'s `chain_for`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase6a-wiki-diarization.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
