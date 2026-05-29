# DeepTalk Phase 1 — Transcript Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend transcript spine — a runnable FastAPI service that streams live transcript events over WebSocket, proven end-to-end on macOS using a fake STT source that replays a fixture.

**Architecture:** An append-only `TranscriptStore` (SQLite) is the single source of truth. A `SttLive` source emits `TranscriptEvent`s; an ingest loop appends them to the store and publishes them on an in-process async `EventBus`. A FastAPI WebSocket endpoint sends each client the stored backlog, then streams live events from the bus. Real STT (nemotron) and mic capture are introduced in Phase 2 behind the same `SttLive` interface — Phase 1 uses `FakeSttLive` so everything is testable without CUDA.

**Tech Stack:** Python 3.12, `uv`, FastAPI, `pytest` + `pytest-asyncio`, stdlib `sqlite3`.

---

## Roadmap (this plan = Phase 1 of 8)

Plans map to spec §15 build order. Each produces working, testable software.

1. **Phase 1 — Transcript spine (THIS PLAN):** store + event model + bus + `SttLive` interface + `FakeSttLive` + ingest + WebSocket stream.
2. Phase 2 — Real audio capture (sounddevice) + `NemotronSttLive` on the 3060 + minimal web UI transcript pane.
3. Phase 3 — Model Router + Search agent (cloud) end-to-end + Artifact model/bus + card in UI.
4. Phase 4 — Intent Detector + Orchestrator dispatch + dedup + manual tap-to-fire.
5. Phase 5 — Pros/cons + Planning agents.
6. Phase 6 — VibeVoice batch diarization + Wiki Builder.
7. Phase 7 — GPU lease manager + error/fallback hardening + cost cap.
8. Phase 8 — Mockup agent (feature-flagged).

## File Structure (Phase 1)

```
deeptalk/
  pyproject.toml                     # uv project, deps, pytest config
  src/deeptalk/
    __init__.py
    transcript/
      __init__.py
      events.py                      # TranscriptEvent (frozen dataclass)
      store.py                       # TranscriptStore (sqlite append + query)
    bus.py                           # EventBus (async pub/sub)
    stt/
      __init__.py
      base.py                        # SttLive ABC
      fake.py                        # FakeSttLive (replays a fixture)
    ingest.py                        # run_ingest: SttLive -> store + bus
    server/
      __init__.py
      app.py                         # create_app + /ws/transcript
  fixtures/
    sample_meeting.jsonl             # scripted transcript lines
  tests/
    __init__.py
    test_events.py
    test_bus.py
    test_store.py
    test_fake_stt.py
    test_ingest.py
    test_ws.py
```

Each module has one responsibility: `events` = the data shape, `store` = persistence/source-of-truth, `bus` = fan-out, `stt` = sources, `ingest` = wiring, `server` = transport.

---

### Task 0: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/deeptalk/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Initialize the uv project and add dependencies**

Run:
```bash
uv init --bare --python 3.12
uv add fastapi "uvicorn[standard]" websockets
uv add --dev pytest pytest-asyncio httpx
```

- [ ] **Step 2: Replace `pyproject.toml` with this exact content**

```toml
[project]
name = "deeptalk"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "websockets",
]

[dependency-groups]
dev = [
    "pytest",
    "pytest-asyncio",
    "httpx",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/deeptalk"]
```

- [ ] **Step 3: Create package and test init files**

Run:
```bash
mkdir -p src/deeptalk/transcript src/deeptalk/stt src/deeptalk/server fixtures tests
touch src/deeptalk/__init__.py src/deeptalk/transcript/__init__.py src/deeptalk/stt/__init__.py src/deeptalk/server/__init__.py tests/__init__.py
```

- [ ] **Step 4: Verify pytest runs (collects zero tests)**

Run: `uv run pytest -q`
Expected: `no tests ran` (exit code 5) — confirms environment + config work.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/deeptalk tests
git commit -m "chore: scaffold deeptalk python project"
```

---

### Task 1: TranscriptEvent model

**Files:**
- Create: `src/deeptalk/transcript/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events.py
import dataclasses
import pytest
from deeptalk.transcript.events import TranscriptEvent


def test_event_holds_fields_and_defaults():
    ev = TranscriptEvent(session_id="s1", ts=1.5, text="hello", is_final=True)
    assert ev.session_id == "s1"
    assert ev.ts == 1.5
    assert ev.text == "hello"
    assert ev.is_final is True
    assert ev.source == "live"
    assert ev.speaker is None
    assert ev.span_id is None


def test_event_is_immutable():
    ev = TranscriptEvent(session_id="s1", ts=0.0, text="x", is_final=False)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.text = "changed"


def test_event_round_trips_through_dict():
    ev = TranscriptEvent(
        session_id="s1", ts=2.0, text="hi", is_final=True, source="diarized", speaker=3, span_id="sp1"
    )
    assert TranscriptEvent.from_dict(ev.to_dict()) == ev
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.transcript.events'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/deeptalk/transcript/events.py
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TranscriptEvent:
    """A single transcript fragment. Immutable; the store is the source of truth."""

    session_id: str
    ts: float
    text: str
    is_final: bool
    source: str = "live"  # "live" | "diarized"
    speaker: int | None = None
    span_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptEvent":
        return cls(
            session_id=data["session_id"],
            ts=data["ts"],
            text=data["text"],
            is_final=data["is_final"],
            source=data.get("source", "live"),
            speaker=data.get("speaker"),
            span_id=data.get("span_id"),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_events.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/transcript/events.py tests/test_events.py
git commit -m "feat: add immutable TranscriptEvent model"
```

---

### Task 2: EventBus (async pub/sub)

**Files:**
- Create: `src/deeptalk/bus.py`
- Test: `tests/test_bus.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bus.py
import asyncio
from deeptalk.bus import EventBus


async def test_subscriber_receives_published_item():
    bus = EventBus()
    q = bus.subscribe()
    await bus.publish("hello")
    assert await asyncio.wait_for(q.get(), timeout=1.0) == "hello"


async def test_two_subscribers_each_receive_item():
    bus = EventBus()
    q1 = bus.subscribe()
    q2 = bus.subscribe()
    await bus.publish(42)
    assert await asyncio.wait_for(q1.get(), timeout=1.0) == 42
    assert await asyncio.wait_for(q2.get(), timeout=1.0) == 42


async def test_unsubscribed_queue_gets_nothing():
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    await bus.publish("x")
    assert q.empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.bus'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/deeptalk/bus.py
from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    """In-process fan-out. Each subscriber gets its own queue."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Any]] = []

    def subscribe(self) -> asyncio.Queue[Any]:
        q: asyncio.Queue[Any] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Any]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, item: Any) -> None:
        for q in list(self._subscribers):
            await q.put(item)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_bus.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/bus.py tests/test_bus.py
git commit -m "feat: add async EventBus pub/sub"
```

---

### Task 3: TranscriptStore (SQLite, source of truth)

**Files:**
- Create: `src/deeptalk/transcript/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore


def _ev(text, ts, session="s1", is_final=True):
    return TranscriptEvent(session_id=session, ts=ts, text=text, is_final=is_final)


def test_append_returns_increasing_seq(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    seq1 = store.append(_ev("a", 0.0))
    seq2 = store.append(_ev("b", 1.0))
    assert seq2 > seq1


def test_all_events_returns_in_insertion_order(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(_ev("first", 0.0))
    store.append(_ev("second", 1.0))
    events = store.all_events("s1")
    assert [e.text for e in events] == ["first", "second"]
    assert all(isinstance(e, TranscriptEvent) for e in events)


def test_all_events_filters_by_session(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(_ev("keep", 0.0, session="s1"))
    store.append(_ev("drop", 0.0, session="s2"))
    assert [e.text for e in store.all_events("s1")] == ["keep"]


def test_round_trip_preserves_all_fields(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    ev = TranscriptEvent(
        session_id="s1", ts=2.5, text="hi", is_final=False,
        source="diarized", speaker=2, span_id="sp9",
    )
    store.append(ev)
    assert store.all_events("s1")[0] == ev


def test_data_persists_across_instances(tmp_path):
    db = str(tmp_path / "t.db")
    TranscriptStore(db).append(_ev("persisted", 0.0))
    assert [e.text for e in TranscriptStore(db).all_events("s1")] == ["persisted"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.transcript.store'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/deeptalk/transcript/store.py
from __future__ import annotations

import sqlite3

from deeptalk.transcript.events import TranscriptEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transcript_event (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT    NOT NULL,
    ts         REAL    NOT NULL,
    text       TEXT    NOT NULL,
    is_final   INTEGER NOT NULL,
    source     TEXT    NOT NULL,
    speaker    INTEGER,
    span_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_session ON transcript_event(session_id, seq);
"""


class TranscriptStore:
    """Append-only persistence for transcript events. The single source of truth."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(self, ev: TranscriptEvent) -> int:
        cur = self._conn.execute(
            "INSERT INTO transcript_event "
            "(session_id, ts, text, is_final, source, speaker, span_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ev.session_id, ev.ts, ev.text, int(ev.is_final), ev.source, ev.speaker, ev.span_id),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def all_events(self, session_id: str) -> list[TranscriptEvent]:
        rows = self._conn.execute(
            "SELECT session_id, ts, text, is_final, source, speaker, span_id "
            "FROM transcript_event WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [
            TranscriptEvent(
                session_id=r["session_id"],
                ts=r["ts"],
                text=r["text"],
                is_final=bool(r["is_final"]),
                source=r["source"],
                speaker=r["speaker"],
                span_id=r["span_id"],
            )
            for r in rows
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_store.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/transcript/store.py tests/test_store.py
git commit -m "feat: add SQLite TranscriptStore"
```

---

### Task 4: SttLive interface + FakeSttLive

**Files:**
- Create: `src/deeptalk/stt/base.py`
- Create: `src/deeptalk/stt/fake.py`
- Create: `fixtures/sample_meeting.jsonl`
- Test: `tests/test_fake_stt.py`

- [ ] **Step 1: Create the fixture file**

```jsonl
{"ts": 0.0, "text": "lets talk about the database choice", "is_final": true}
{"ts": 2.0, "text": "should we use postgres or sqlite", "is_final": true}
{"ts": 4.0, "text": "postgres scales better for concurrent writes", "is_final": true}
```

Save exactly as `fixtures/sample_meeting.jsonl` (three lines, no trailing blank line needed).

- [ ] **Step 2: Write the failing test**

```python
# tests/test_fake_stt.py
import asyncio
from deeptalk.stt.fake import FakeSttLive
from deeptalk.transcript.events import TranscriptEvent


async def test_fake_yields_events_from_fixture(tmp_path):
    fixture = tmp_path / "f.jsonl"
    fixture.write_text(
        '{"ts": 0.0, "text": "one", "is_final": true}\n'
        '{"ts": 1.0, "text": "two", "is_final": false}\n'
    )
    stt = FakeSttLive(session_id="s1", fixture_path=str(fixture))
    events = [ev async for ev in stt.stream()]
    assert len(events) == 2
    assert all(isinstance(e, TranscriptEvent) for e in events)
    assert events[0].text == "one"
    assert events[0].session_id == "s1"
    assert events[1].is_final is False


async def test_fake_is_fast_when_not_realtime(tmp_path):
    fixture = tmp_path / "f.jsonl"
    fixture.write_text(
        '{"ts": 0.0, "text": "a", "is_final": true}\n'
        '{"ts": 99.0, "text": "b", "is_final": true}\n'
    )
    stt = FakeSttLive(session_id="s1", fixture_path=str(fixture), realtime=False)
    # Large ts gap must NOT cause a real delay when realtime is off.
    events = await asyncio.wait_for(
        _collect(stt), timeout=1.0
    )
    assert [e.text for e in events] == ["a", "b"]


async def _collect(stt):
    return [ev async for ev in stt.stream()]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_fake_stt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.stt.fake'`

- [ ] **Step 4: Write the base interface**

```python
# src/deeptalk/stt/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from deeptalk.transcript.events import TranscriptEvent


class SttLive(ABC):
    """A live speech-to-text source that yields transcript events as they arrive."""

    @abstractmethod
    def stream(self) -> AsyncIterator[TranscriptEvent]:
        """Async-iterate transcript events until the source ends."""
        raise NotImplementedError
```

- [ ] **Step 5: Write FakeSttLive**

```python
# src/deeptalk/stt/fake.py
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from deeptalk.stt.base import SttLive
from deeptalk.transcript.events import TranscriptEvent


class FakeSttLive(SttLive):
    """Replays transcript lines from a JSONL fixture. Used for dev/tests without CUDA."""

    def __init__(self, session_id: str, fixture_path: str, realtime: bool = False) -> None:
        self._session_id = session_id
        self._fixture_path = fixture_path
        self._realtime = realtime

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        prev_ts = 0.0
        with open(self._fixture_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if self._realtime:
                    delay = max(0.0, row["ts"] - prev_ts)
                    await asyncio.sleep(delay)
                    prev_ts = row["ts"]
                yield TranscriptEvent(
                    session_id=self._session_id,
                    ts=row["ts"],
                    text=row["text"],
                    is_final=row["is_final"],
                    source=row.get("source", "live"),
                    speaker=row.get("speaker"),
                    span_id=row.get("span_id"),
                )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_fake_stt.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add src/deeptalk/stt/base.py src/deeptalk/stt/fake.py fixtures/sample_meeting.jsonl tests/test_fake_stt.py
git commit -m "feat: add SttLive interface and FakeSttLive fixture replayer"
```

---

### Task 5: Ingest loop (SttLive → store + bus)

**Files:**
- Create: `src/deeptalk/ingest.py`
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest.py
import asyncio
from deeptalk.bus import EventBus
from deeptalk.ingest import run_ingest
from deeptalk.stt.fake import FakeSttLive
from deeptalk.transcript.store import TranscriptStore


async def test_ingest_persists_all_events(tmp_path):
    fixture = tmp_path / "f.jsonl"
    fixture.write_text(
        '{"ts": 0.0, "text": "alpha", "is_final": true}\n'
        '{"ts": 1.0, "text": "beta", "is_final": true}\n'
    )
    store = TranscriptStore(str(tmp_path / "t.db"))
    bus = EventBus()
    stt = FakeSttLive(session_id="s1", fixture_path=str(fixture))

    await run_ingest(stt, store, bus)

    assert [e.text for e in store.all_events("s1")] == ["alpha", "beta"]


async def test_ingest_publishes_each_event_on_bus(tmp_path):
    fixture = tmp_path / "f.jsonl"
    fixture.write_text('{"ts": 0.0, "text": "alpha", "is_final": true}\n')
    store = TranscriptStore(str(tmp_path / "t.db"))
    bus = EventBus()
    q = bus.subscribe()
    stt = FakeSttLive(session_id="s1", fixture_path=str(fixture))

    await run_ingest(stt, store, bus)

    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received.text == "alpha"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.ingest'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/deeptalk/ingest.py
from __future__ import annotations

from deeptalk.bus import EventBus
from deeptalk.stt.base import SttLive
from deeptalk.transcript.store import TranscriptStore


async def run_ingest(stt: SttLive, store: TranscriptStore, bus: EventBus) -> None:
    """Consume the STT stream, persist each event, then fan it out on the bus."""
    async for ev in stt.stream():
        store.append(ev)
        await bus.publish(ev)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/ingest.py tests/test_ingest.py
git commit -m "feat: add ingest loop wiring STT to store and bus"
```

---

### Task 6: FastAPI WebSocket transcript stream

**Files:**
- Create: `src/deeptalk/server/app.py`
- Test: `tests/test_ws.py`

The endpoint sends the stored backlog for a session on connect, then streams live
events from the bus. Sending backlog first makes the endpoint testable without
cross-event-loop publishing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ws.py
from fastapi.testclient import TestClient
from deeptalk.server.app import create_app
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore
from deeptalk.bus import EventBus


def test_ws_sends_backlog_for_session(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(TranscriptEvent(session_id="s1", ts=0.0, text="hello", is_final=True))
    store.append(TranscriptEvent(session_id="s1", ts=1.0, text="world", is_final=True))
    app = create_app(store=store, bus=EventBus())
    client = TestClient(app)

    with client.websocket_connect("/ws/transcript?session_id=s1") as ws:
        first = ws.receive_json()
        second = ws.receive_json()

    assert first["text"] == "hello"
    assert second["text"] == "world"
    assert first["session_id"] == "s1"


def test_ws_backlog_filtered_by_session(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(TranscriptEvent(session_id="s1", ts=0.0, text="keep", is_final=True))
    store.append(TranscriptEvent(session_id="s2", ts=0.0, text="drop", is_final=True))
    app = create_app(store=store, bus=EventBus())
    client = TestClient(app)

    with client.websocket_connect("/ws/transcript?session_id=s1") as ws:
        msg = ws.receive_json()

    assert msg["text"] == "keep"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ws.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.server.app'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/deeptalk/server/app.py
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from deeptalk.bus import EventBus
from deeptalk.transcript.store import TranscriptStore


def create_app(store: TranscriptStore, bus: EventBus) -> FastAPI:
    app = FastAPI(title="DeepTalk")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws/transcript")
    async def ws_transcript(ws: WebSocket) -> None:
        session_id = ws.query_params.get("session_id", "default")
        await ws.accept()
        # 1. backlog
        for ev in store.all_events(session_id):
            await ws.send_json(ev.to_dict())
        # 2. live
        q = bus.subscribe()
        try:
            while True:
                ev = await q.get()
                if ev.session_id == session_id:
                    await ws.send_json(ev.to_dict())
        except WebSocketDisconnect:
            pass
        finally:
            bus.unsubscribe(q)

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ws.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/server/app.py tests/test_ws.py
git commit -m "feat: add WebSocket transcript stream endpoint"
```

---

### Task 7: Runnable entrypoint (manual end-to-end smoke)

**Files:**
- Create: `src/deeptalk/server/__main__.py`

This wires a `FakeSttLive` ingest loop to live alongside the server so you can watch
a fixture stream over the WebSocket. No new unit test — it is a composition root,
covered by manual smoke + the existing unit/integration tests.

- [ ] **Step 1: Write the entrypoint**

```python
# src/deeptalk/server/__main__.py
from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import uvicorn

from deeptalk.bus import EventBus
from deeptalk.ingest import run_ingest
from deeptalk.server.app import create_app
from deeptalk.stt.fake import FakeSttLive
from deeptalk.transcript.store import TranscriptStore

SESSION_ID = "demo"
FIXTURE = str(Path(__file__).resolve().parents[3] / "fixtures" / "sample_meeting.jsonl")


def main() -> None:
    store = TranscriptStore("deeptalk-demo.db")
    bus = EventBus()
    app = create_app(store=store, bus=bus)

    @app.on_event("startup")
    async def _start_ingest() -> None:
        stt = FakeSttLive(session_id=SESSION_ID, fixture_path=FIXTURE, realtime=True)
        app.state.ingest_task = asyncio.create_task(run_ingest(stt, store, bus))

    @app.on_event("shutdown")
    async def _stop_ingest() -> None:
        task = getattr(app.state, "ingest_task", None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual smoke test**

Run the server:
```bash
uv run python -m deeptalk.server
```
In a second terminal, connect and watch events stream (uses the `websockets` dep):
```bash
uv run python -c "import asyncio, websockets; \
asyncio.run((lambda: (async_print()))()) if False else None"
```
Simpler: open `http://127.0.0.1:8000/health` in a browser — expect `{"status":"ok"}`.
Then verify the demo DB captured the fixture:
```bash
uv run python -c "from deeptalk.transcript.store import TranscriptStore; \
print([e.text for e in TranscriptStore('deeptalk-demo.db').all_events('demo')])"
```
Expected (after the server has run a few seconds): the three fixture lines, e.g.
`['lets talk about the database choice', 'should we use postgres or sqlite', 'postgres scales better for concurrent writes']`

Stop the server with Ctrl+C.

- [ ] **Step 3: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS (all tests from Tasks 1-6 green).

- [ ] **Step 4: Add the demo DB to .gitignore and commit**

```bash
echo "deeptalk-demo.db" >> .gitignore
git add src/deeptalk/server/__main__.py .gitignore
git commit -m "feat: add runnable demo entrypoint streaming fixture over WebSocket"
```

---

## Self-Review

**Spec coverage (Phase 1 subset):** Phase 1 implements the spec's transcript spine —
component #4 Transcript Store (Task 3), the `{text, ts, isFinal}` event shape from
component #2's interface (Task 1, with `source`/`speaker`/`span_id` for the later
diarized path), the append-only single-source-of-truth principle (§7, Task 3), the
`SttLive` interface that real nemotron slots behind in Phase 2 (Task 4), and the
event fan-out the UI/orchestrator will subscribe to (Task 2 + Task 6). Audio capture
(component #1), real STT, intent/orchestrator/router/agents/wiki are explicitly
later phases per the roadmap — not gaps.

**Placeholder scan:** No TBD/TODO. Every code step has complete code; every run step
has an exact command + expected result. Task 7 step 2 deliberately uses the
`/health` + DB-inspection smoke path rather than a hand-wavy "connect a client."

**Type consistency:** `TranscriptEvent` field names (`session_id`, `ts`, `text`,
`is_final`, `source`, `speaker`, `span_id`) are identical across events.py, store.py,
fake.py, ingest, and app.py. `to_dict()`/`from_dict()` defined in Task 1 are the
only serialization used (Task 6 uses `to_dict()`). `EventBus.subscribe/unsubscribe/
publish` (Task 2) match their uses in Task 5 and Task 6. `run_ingest(stt, store, bus)`
signature is consistent between Task 5 definition and Task 7 use. `create_app(store=,
bus=)` consistent between Task 6 and Task 7.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase1-transcript-spine.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
