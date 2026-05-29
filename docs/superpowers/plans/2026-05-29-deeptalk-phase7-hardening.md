# DeepTalk Phase 7 — GPU Lease + Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DeepTalk robust on a constrained box: a **GPU lease** that serializes GPU-heavy sections (so diarization can't OOM by co-loading), a per-session **cost cap** on agent calls, **agent timeouts** so a stuck provider produces an error card instead of hanging, and **orchestrator task-error retention** so background failures are logged, not swallowed.

**Architecture:** `GpuLease` is a single-slot async lock; the diarization call in `/finalize` holds it. `CostTracker` caps agent calls per session; the dispatch `make_fire` guards on it and emits a "budget exceeded" system artifact when over. `run_completion_agent` and `run_search` wrap their provider call in `asyncio.timeout`, converting a hang into an error artifact. `run_orchestrator` retains its fire tasks and logs exceptions via a done-callback. All Mac-testable.

**Tech Stack:** Python 3.12 (`asyncio.timeout`), uv, FastAPI, pytest + pytest-asyncio.

---

## Roadmap context

Phase 7 of spec §15 (error/fallback + GPU scheduling from §9/§10). Phases 1–6 on `main`. Phase 8 (mockup agent) is the last phase. This phase adds no new user features — it hardens what exists.

## File Structure (Phase 7)

```
deeptalk/
  src/deeptalk/
    gpu/__init__.py                 # NEW
    gpu/lease.py                    # NEW: GpuLease
    cost/__init__.py                # NEW
    cost/tracker.py                 # NEW: CostTracker
    agents/common.py                # MODIFY: timeout
    agents/search.py                # MODIFY: timeout
    orchestrator.py                 # MODIFY: retain tasks + log errors
    server/dispatch.py              # MODIFY: cost guard + timeout in make_fire
    server/app.py                   # MODIFY: gpu_lease around diarization
    server/__main__.py              # MODIFY: build tracker/lease, pass through
    config.py                       # MODIFY: max_agent_calls, agent_timeout
  tests/
    test_gpu_lease.py               # NEW
    test_cost_tracker.py            # NEW
    test_agent_timeout.py           # NEW
    test_orchestrator.py            # MODIFY: add error-retention test
    test_dispatch.py                # MODIFY: add budget-cap test
```

---

### Task 1: GpuLease

**Files:**
- Create: `src/deeptalk/gpu/__init__.py` (empty), `src/deeptalk/gpu/lease.py`
- Test: `tests/test_gpu_lease.py`

- [ ] **Step 1: Create the package init**

Run: `touch src/deeptalk/gpu/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_gpu_lease.py`:

```python
import asyncio

from deeptalk.gpu.lease import GpuLease


async def test_lease_serializes_holders():
    lease = GpuLease()
    active = 0
    max_seen = 0

    async def worker():
        nonlocal active, max_seen
        async with lease.hold():
            active += 1
            max_seen = max(max_seen, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(worker() for _ in range(5)))
    assert max_seen == 1  # never two holders at once


async def test_lease_releases_on_exception():
    lease = GpuLease()
    with __import__("pytest").raises(RuntimeError):
        async with lease.hold():
            raise RuntimeError("boom")
    # lease is free again
    async with lease.hold():
        pass
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_gpu_lease.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.gpu.lease'`

- [ ] **Step 4: Write it** — `src/deeptalk/gpu/lease.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class GpuLease:
    """Single-slot async lease. Serializes GPU-heavy sections so only one runs at a
    time on a memory-constrained card (prevents co-loading models into OOM)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def hold(self) -> AsyncIterator[None]:
        async with self._lock:
            yield
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_gpu_lease.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add src/deeptalk/gpu/__init__.py src/deeptalk/gpu/lease.py tests/test_gpu_lease.py
git commit -m "feat: add GpuLease (serialize GPU-heavy sections)"
```

---

### Task 2: CostTracker

**Files:**
- Create: `src/deeptalk/cost/__init__.py` (empty), `src/deeptalk/cost/tracker.py`
- Test: `tests/test_cost_tracker.py`

- [ ] **Step 1: Create the package init**

Run: `touch src/deeptalk/cost/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_cost_tracker.py`:

```python
from deeptalk.cost.tracker import CostTracker


def test_allows_until_cap_then_denies():
    t = CostTracker(max_calls=2)
    assert t.allow("s1") is True
    assert t.allow("s1") is True
    assert t.allow("s1") is False  # cap hit
    assert t.spent("s1") == 2


def test_unlimited_when_negative():
    t = CostTracker(max_calls=-1)
    for _ in range(100):
        assert t.allow("s1") is True


def test_sessions_are_independent():
    t = CostTracker(max_calls=1)
    assert t.allow("s1") is True
    assert t.allow("s2") is True
    assert t.allow("s1") is False
    assert t.allow("s2") is False
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_cost_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.cost.tracker'`

- [ ] **Step 4: Write it** — `src/deeptalk/cost/tracker.py`:

```python
from __future__ import annotations


class CostTracker:
    """Per-session cap on agent invocations. max_calls < 0 means unlimited."""

    def __init__(self, max_calls: int) -> None:
        self._max = max_calls
        self._counts: dict[str, int] = {}

    def allow(self, session_id: str) -> bool:
        """Return True (and count it) if under the cap; False if the cap is reached."""
        if self._max < 0:
            return True
        used = self._counts.get(session_id, 0)
        if used >= self._max:
            return False
        self._counts[session_id] = used + 1
        return True

    def spent(self, session_id: str) -> int:
        return self._counts.get(session_id, 0)
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_cost_tracker.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/deeptalk/cost/__init__.py src/deeptalk/cost/tracker.py tests/test_cost_tracker.py
git commit -m "feat: add per-session CostTracker"
```

---

### Task 3: Agent timeouts

**Files:**
- Modify: `src/deeptalk/agents/common.py`, `src/deeptalk/agents/search.py`
- Test: `tests/test_agent_timeout.py`

- [ ] **Step 1: Write the failing test** — `tests/test_agent_timeout.py`:

```python
import asyncio

from deeptalk.agents.proscons import run_proscons
from deeptalk.agents.search import run_search
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter


class _SlowProvider:
    name = "slow"

    async def complete(self, prompt):
        await asyncio.sleep(1.0)
        return "{}"

    async def search_answer(self, query):
        await asyncio.sleep(1.0)
        raise AssertionError("should have timed out")


def _router(agent):
    return ModelRouter(providers={"slow": _SlowProvider()}, routes={agent: ["slow"]}, default=["slow"])


async def test_completion_agent_times_out(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_proscons("q", "s1", _router("proscons"), store, bus, now=0.0, timeout=0.05)
    assert art.status == "error"
    assert "timed out" in art.error.lower()


async def test_search_agent_times_out(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_search("q", "s1", _router("search"), store, bus, now=0.0, timeout=0.05)
    assert art.status == "error"
    assert "timed out" in art.error.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_agent_timeout.py -v`
Expected: FAIL — `run_proscons`/`run_search` don't accept a `timeout` kwarg.

- [ ] **Step 3: Add timeout to `run_completion_agent`** — in `src/deeptalk/agents/common.py`:

Change the signature to add `timeout: float = 30.0` (keyword-only, after `build_payload`):
```python
async def run_completion_agent(
    *,
    agent: str,
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
    prompt: str,
    build_payload: Callable[[dict[str, Any]], dict[str, Any]],
    timeout: float = 30.0,
) -> Artifact:
```
Wrap the provider call in a timeout and handle `TimeoutError` distinctly. Replace the `try: ... except Exception as error:` block with:
```python
    try:
        async with asyncio.timeout(timeout):
            providers = router.chain_for(agent)
            raw = await run_with_fallback(providers, lambda p: p.complete(prompt))
        data = parse_json(raw)
        if data is None:
            raise ValueError("could not parse model output")
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=agent,
            status="done",
            title=query,
            payload=build_payload(data),
            created_at=now,
        )
    except TimeoutError:
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=agent,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=f"agent timed out after {timeout}s",
        )
    except Exception as error:  # noqa: BLE001 - surfaced as an error card
        cause = error.__cause__ or error
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=agent,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=str(cause),
        )
    store.append(artifact)
    await bus.publish(artifact)
    return artifact
```
Add `import asyncio` at the top of the file (keep existing imports). Note `data = parse_json(raw)` moved OUTSIDE the timeout block (parsing is cheap; only the network call is bounded) — `raw` is assigned inside the `async with`, used after; that's fine since the block completes before we read it.

- [ ] **Step 4: Thread `timeout` through the completion agents** — in `src/deeptalk/agents/proscons.py` and `src/deeptalk/agents/planning.py`, add `timeout: float = 30.0` to each `run_*` signature and pass it through to `run_completion_agent(..., timeout=timeout)`.

`proscons.py` — change the function signature + the call:
```python
async def run_proscons(
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
    timeout: float = 30.0,
) -> Artifact:
    return await run_completion_agent(
        agent=AGENT,
        query=query,
        session_id=session_id,
        router=router,
        store=store,
        bus=bus,
        now=now,
        prompt=_PROMPT.format(query=query),
        build_payload=_payload,
        timeout=timeout,
    )
```
Apply the identical change to `planning.py` (`run_planning`).

- [ ] **Step 5: Add timeout to `run_search`** — in `src/deeptalk/agents/search.py`:

Add `timeout: float = 30.0` to the signature (after `now`). Wrap the search call and add a `TimeoutError` branch. The current body builds a done artifact in `try` and an error artifact in `except Exception`. Update to:
```python
async def run_search(
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
    timeout: float = 30.0,
) -> Artifact:
    try:
        async with asyncio.timeout(timeout):
            providers = router.chain_for(AGENT)
            result = await run_with_fallback(providers, lambda p: p.search_answer(query))
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=AGENT,
            status="done",
            title=query,
            payload={
                "answer": result.text,
                "citations": [{"title": c.title, "url": c.url} for c in result.citations],
                "model": result.model,
            },
            created_at=now,
        )
    except TimeoutError:
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=AGENT,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=f"agent timed out after {timeout}s",
        )
    except Exception as error:  # noqa: BLE001
        cause = error.__cause__ or error
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=AGENT,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=str(cause),
        )
    store.append(artifact)
    await bus.publish(artifact)
    return artifact
```
Add `import asyncio` at the top of `search.py` (keep `import uuid` and existing imports).

- [ ] **Step 6: Run to verify it passes + full suite**

Run: `uv run pytest tests/test_agent_timeout.py -v && uv run pytest -q`
Expected: timeout 2 passed; full suite green (existing agent tests call `run_*` without `timeout` — the default 30.0 keeps them working).

- [ ] **Step 7: Commit**

```bash
git add src/deeptalk/agents/common.py src/deeptalk/agents/search.py src/deeptalk/agents/proscons.py src/deeptalk/agents/planning.py tests/test_agent_timeout.py
git commit -m "feat: add agent timeouts (hang -> error card)"
```

---

### Task 4: Orchestrator task retention + error logging

**Files:**
- Modify: `src/deeptalk/orchestrator.py`
- Test: `tests/test_orchestrator.py` (append)

- [ ] **Step 1: Append a failing test** — to `tests/test_orchestrator.py`:

```python
import contextlib


class _PerTextDetector:
    """Returns a distinct Intent per text (topic == text), so dedup doesn't merge."""

    async def detect(self, text):
        from deeptalk.intent.models import Intent

        return Intent(kind="search", query=text, topic=text)


async def test_run_orchestrator_survives_a_failing_handle():
    bus = EventBus()
    fired = []

    async def fire(intent):
        fired.append(intent.topic)
        if intent.topic == "boom?":
            raise RuntimeError("agent blew up")

    orch = Orchestrator(_PerTextDetector(), fire=fire)
    task = asyncio.create_task(run_orchestrator(bus, orch, "s1"))
    await asyncio.sleep(0)
    await bus.publish(TranscriptEvent(session_id="s1", ts=0.0, text="boom?", is_final=True))
    await asyncio.sleep(0.02)
    await bus.publish(TranscriptEvent(session_id="s1", ts=1.0, text="ok?", is_final=True))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    # the failing handle did not kill the loop — the second line still fired
    assert "boom?" in fired
    assert "ok?" in fired
```

- [ ] **Step 2: Run to verify it fails or is flaky**

Run: `uv run pytest tests/test_orchestrator.py::test_run_orchestrator_survives_a_failing_handle -v`
Expected: The loop already survives (tasks are isolated), BUT the failing task's exception is currently never retrieved (a "Task exception was never retrieved" warning). This test passes for the survival assertion; the point of the task is to retain + log. If it passes already, proceed to make the retention explicit (Step 3) so exceptions are handled, not warned.

- [ ] **Step 3: Update `run_orchestrator`** — in `src/deeptalk/orchestrator.py`:

Add `import logging` at the top. Replace `run_orchestrator` with:
```python
_log = logging.getLogger("deeptalk.orchestrator")


async def run_orchestrator(bus: EventBus, orchestrator: Orchestrator, session_id: str) -> None:
    """Consume the transcript bus; handle each final line for this session."""
    q = bus.subscribe()
    tasks: set[asyncio.Task] = set()

    def _on_done(task: asyncio.Task) -> None:
        tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            _log.warning("orchestrator handle failed: %r", task.exception())

    try:
        while True:
            ev = await q.get()
            if ev.session_id == session_id and getattr(ev, "is_final", False):
                task = asyncio.create_task(orchestrator.handle(ev.text))
                tasks.add(task)
                task.add_done_callback(_on_done)
    finally:
        bus.unsubscribe(q)
        for task in tasks:
            task.cancel()
```
(Keep the `Orchestrator` class unchanged.)

- [ ] **Step 4: Run to verify it passes + full suite**

Run: `uv run pytest tests/test_orchestrator.py -v && uv run pytest -q`
Expected: all orchestrator tests pass (including the new survival test); no "Task exception was never retrieved" warnings; full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: retain orchestrator fire tasks and log their failures"
```

---

### Task 5: Wire cost cap + lease + timeout into the app

**Files:**
- Modify: `src/deeptalk/config.py`, `src/deeptalk/server/dispatch.py`, `src/deeptalk/server/app.py`, `src/deeptalk/server/__main__.py`
- Test: `tests/test_dispatch.py` (append)

- [ ] **Step 1: Extend `Config`** — add fields after `recording_path`:

```python
    max_agent_calls: int = 50  # per-session cap; -1 = unlimited
    agent_timeout: float = 30.0
```
And in `from_env`:
```python
            max_agent_calls=int(e.get("DEEPTALK_MAX_AGENT_CALLS", "50")),
            agent_timeout=float(e.get("DEEPTALK_AGENT_TIMEOUT", "30")),
```

- [ ] **Step 2: Append a failing dispatch test** — to `tests/test_dispatch.py`:

```python
import uuid as _uuid  # noqa: F401 (ensures import availability if needed)

from deeptalk.cost.tracker import CostTracker


async def test_budget_cap_emits_system_artifact(tmp_path):
    store, bus, router = _ctx(tmp_path)
    tracker = CostTracker(max_calls=1)
    fire = make_fire(router, store, bus, "s1", now=lambda: 1.0, tracker=tracker)

    from deeptalk.intent.models import Intent

    await fire(Intent(kind="search", query="q1", topic="t1"))  # allowed
    await fire(Intent(kind="search", query="q2", topic="t2"))  # over cap

    arts = store.all_artifacts("s1")
    agents = [a.agent for a in arts]
    assert "search" in agents          # first fired
    assert "system" in agents          # second became a budget artifact
    budget = [a for a in arts if a.agent == "system"][0]
    assert budget.status == "error"
    assert "budget" in budget.error.lower()
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_dispatch.py::test_budget_cap_emits_system_artifact -v`
Expected: FAIL — `make_fire` has no `tracker` kwarg.

- [ ] **Step 4: Update `src/deeptalk/server/dispatch.py`** — add the cost guard + timeout passthrough:

```python
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from deeptalk.agents.planning import run_planning
from deeptalk.agents.proscons import run_proscons
from deeptalk.agents.search import run_search
from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.cost.tracker import CostTracker
from deeptalk.intent.models import Intent
from deeptalk.llm.router import ModelRouter

_AGENTS = {
    "search": run_search,
    "debate": run_proscons,
    "planning": run_planning,
}


def make_fire(
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    session_id: str,
    now: Callable[[], float],
    tracker: CostTracker | None = None,
    timeout: float = 30.0,
) -> Callable[[Intent], Awaitable[None]]:
    """Build the orchestrator's `fire` callback that routes a kind to its agent,
    enforcing the per-session cost cap and per-agent timeout."""

    async def fire(intent: Intent) -> None:
        runner = _AGENTS.get(intent.kind)
        if runner is None:
            return
        if tracker is not None and not tracker.allow(session_id):
            budget = Artifact(
                id=uuid.uuid4().hex,
                session_id=session_id,
                agent="system",
                status="error",
                title=intent.query,
                payload={},
                created_at=now(),
                error="session agent-call budget exceeded",
            )
            store.append(budget)
            await bus.publish(budget)
            return
        await runner(intent.query, session_id, router, store, bus, now(), timeout=timeout)

    return fire
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (existing 4 + the budget test). Existing dispatch tests don't pass `tracker`, so the cap is disabled there — unaffected.

- [ ] **Step 6: Add the GPU lease around diarization** — in `src/deeptalk/server/app.py`:

Add an import:
```python
from deeptalk.gpu.lease import GpuLease
```
Add `gpu_lease: "GpuLease | None" = None` to the `create_app` signature (after `recording_path`). In the `/finalize` handler, wrap the diarization in the lease when present. Replace the diarization block:
```python
            if diarizer is not None and recording_path and _Path(recording_path).is_file():
                segments = await diarizer.diarize(recording_path)
```
with:
```python
            if diarizer is not None and recording_path and _Path(recording_path).is_file():
                if gpu_lease is not None:
                    async with gpu_lease.hold():
                        segments = await diarizer.diarize(recording_path)
                else:
                    segments = await diarizer.diarize(recording_path)
```
(The rest of the loop appending diarized events is unchanged.)

- [ ] **Step 7: Wire the entrypoint** — in `src/deeptalk/server/__main__.py`:

Add imports:
```python
from deeptalk.cost.tracker import CostTracker
from deeptalk.gpu.lease import GpuLease
```
In `main()`, after `router = build_router(config)` (and near `wiki_store`/`diarizer`), add:
```python
    cost_tracker = CostTracker(config.max_agent_calls)
    gpu_lease = GpuLease()
```
Change the `make_fire(...)` call inside `lifespan` to pass the tracker + timeout:
```python
        fire = make_fire(
            router, artifact_store, artifact_bus, config.session_id, time.time,
            tracker=cost_tracker, timeout=config.agent_timeout,
        )
```
Add `gpu_lease=gpu_lease,` to the `create_app(...)` call.

- [ ] **Step 8: Full suite + smoke**

Run: `uv run pytest -q`
Expected: all green.

Smoke — server boots with hardening wired (default fake), auto-fire still produces an artifact, finalize still builds a wiki:
```bash
rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-7.log 2>&1 &
SERVER_PID=$!
sleep 8
echo "ARTIFACTS:"; uv run python -c "from deeptalk.artifacts.store import ArtifactStore; print([(x.agent,x.status) for x in ArtifactStore('deeptalk-demo.db').all_artifacts('demo')])"
echo "FINALIZE:"; curl -s -X POST http://127.0.0.1:8000/finalize -H 'content-type: application/json' -d '{"session_id":"demo"}'; echo
kill $SERVER_PID 2>/dev/null
```
Expected: an auto-fired artifact (e.g. proscons done) and finalize `{"status":"ok"}` — proving the hardened wiring didn't break the loop. Paste `/tmp/deeptalk-7.log` tail on failure.

- [ ] **Step 9: Commit**

```bash
git add src/deeptalk/config.py src/deeptalk/server/dispatch.py src/deeptalk/server/app.py src/deeptalk/server/__main__.py tests/test_dispatch.py
git commit -m "feat: wire cost cap, agent timeout, and GPU lease into the app"
```

---

## Self-Review

**Spec coverage (Phase 7):** Implements §9/§10 hardening: GPU lease (Task 1, applied to diarization Task 6), per-session cost cap (Task 2 + dispatch guard Task 5), agent timeouts (Task 3), and no-silent-failure orchestrator task retention (Task 4). The mockup agent is Phase 8.

**Limitation noted honestly:** `GpuLease` serializes the GPU sections we explicitly guard (diarization). It does **not** free a resident model's memory — running live nemotron + VibeVoice simultaneously on 6GB still requires not doing both at once (diarize post-session). The lease is the mechanism; the operational policy (diarize after the meeting) remains. Auto-unloading nemotron to make room is a future refinement, not in scope here.

**Placeholder scan:** No TBD/TODO. Every step has exact code + commands + expected output.

**Type consistency:** `run_search`/`run_proscons`/`run_planning` all gain `timeout: float = 30.0` keeping the uniform `(query, session_id, router, store, bus, now, timeout=...)` shape the `_AGENTS` map calls (Task 5 passes `timeout=` positionally-safe via keyword). `run_completion_agent`'s new `timeout` kwarg is passed by proscons/planning. `CostTracker.allow(session_id)` (Task 2) is called in `make_fire` (Task 5). `GpuLease.hold()` (Task 1) is used in `/finalize` (Task 6). `make_fire(..., tracker, timeout)` consistent between Task 5 and the entrypoint (Task 7). `create_app(..., gpu_lease)` consistent between Task 6 and Task 7. Config fields `max_agent_calls`/`agent_timeout` (Task 5) read in the entrypoint.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase7-hardening.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
