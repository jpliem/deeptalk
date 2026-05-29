# DeepTalk Phase 4 — Intent Detector + Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agents fire automatically from the live transcript. Add an `IntentDetector` (heuristic default + optional LLM), an `Orchestrator` that detects intent on each final transcript line, dedups by topic, and fires the search agent in the background; plus UI tap-to-fire (click a transcript line to search it).

**Architecture:** A background `run_orchestrator` task subscribes to the transcript `EventBus`; for each final line it runs the configured `IntentDetector` (heuristic rules, or an LLM via the router's new `complete()` capability), dedups by normalized topic, and fires `run_search` as a bounded background task. The search artifact streams to the UI over the existing `/ws/artifacts`. Tap-to-fire reuses `/ask` from a clickable transcript line.

**Tech Stack:** Python 3.12, uv, FastAPI, pytest + pytest-asyncio (backend); React + Vitest (UI).

---

## Roadmap context

Phase 4 of spec §15. Phases 1–3 are on `main`: transcript spine, live STT, model router + search agent + `/ask` + artifact cards. This phase adds the §7 Intent Detector (#5) and Orchestrator (#6) so agents fire without the manual ask box. Remaining agents (pros/cons, planning, mockup) are Phase 5+; VibeVoice diarization + wiki are Phase 6.

## Key/validation note

Heuristic detection + orchestration are fully Mac-tested. The `LlmIntentDetector` and the providers' new `complete()` real path need `ANTHROPIC_API_KEY` (only when `DEEPTALK_INTENT=llm` + `DEEPTALK_SEARCH_PROVIDER=anthropic`); they are unit-tested with a fake provider (scripted completion) and validated with a key at runtime.

## File Structure (Phase 4)

```
deeptalk/
  src/deeptalk/
    config.py                         # MODIFY: intent_detector field
    llm/
      provider.py                     # MODIFY: add complete() to Protocol
      fake.py                         # MODIFY: add complete() + completion arg
      anthropic_provider.py           # MODIFY: add complete()
      factory.py                      # MODIFY: register "intent" route
    intent/
      __init__.py                     # NEW
      models.py                       # NEW: Intent + normalize_topic
      base.py                         # NEW: IntentDetector Protocol
      heuristic.py                    # NEW: HeuristicIntentDetector
      llm.py                          # NEW: LlmIntentDetector
      factory.py                      # NEW: build_detector(config, router)
    orchestrator.py                   # NEW: Orchestrator + run_orchestrator
    server/__main__.py                # MODIFY: start orchestrator in lifespan
  ui/src/
    TranscriptPane.tsx                # MODIFY: optional onLineClick
    App.tsx                           # MODIFY: pass onLineClick=handleAsk
  tests/
    test_provider_complete.py         # NEW
    test_intent_heuristic.py          # NEW
    test_intent_llm.py                # NEW
    test_orchestrator.py             # NEW
  ui/src/__tests__/
    TranscriptPane.test.tsx           # MODIFY: add click test
```

---

### Task 1: Add `complete()` to the provider seam

**Files:**
- Modify: `src/deeptalk/llm/provider.py`, `src/deeptalk/llm/fake.py`, `src/deeptalk/llm/anthropic_provider.py`
- Test: `tests/test_provider_complete.py`

- [ ] **Step 1: Write the failing test** — `tests/test_provider_complete.py`:

```python
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.provider import LlmProvider


async def test_fake_complete_default_echoes_prompt():
    p = FakeLlmProvider()
    out = await p.complete("classify this")
    assert "classify this" in out


async def test_fake_complete_is_scriptable():
    p = FakeLlmProvider(completion='{"is_search": true, "query": "x"}')
    out = await p.complete("anything")
    assert out == '{"is_search": true, "query": "x"}'


def test_fake_still_satisfies_protocol_with_complete():
    assert isinstance(FakeLlmProvider(), LlmProvider)


def test_anthropic_has_complete():
    from deeptalk.llm.anthropic_provider import AnthropicProvider

    assert callable(getattr(AnthropicProvider, "complete", None))
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_provider_complete.py -v`
Expected: FAIL — `FakeLlmProvider` has no `complete`.

- [ ] **Step 3: Add `complete` to the Protocol** — in `src/deeptalk/llm/provider.py`, inside `class LlmProvider(Protocol):` after `search_answer`, add:

```python
    async def complete(self, prompt: str) -> str:
        """General text completion (no web search)."""
        ...
```

- [ ] **Step 4: Update `FakeLlmProvider`** — in `src/deeptalk/llm/fake.py`:

Change `__init__` to accept a `completion` arg (add as the last parameter):
```python
    def __init__(
        self,
        name: str = "fake",
        answer: str | None = None,
        citations: list[Citation] | None = None,
        completion: str | None = None,
    ) -> None:
        self._name = name
        self._answer = answer
        self._citations = citations
        self._completion = completion
```
And add this method to the class:
```python
    async def complete(self, prompt: str) -> str:
        return self._completion if self._completion is not None else f"(fake) {prompt}"
```

- [ ] **Step 5: Update `AnthropicProvider`** — in `src/deeptalk/llm/anthropic_provider.py`, add this method to the class (after `search_answer`):

```python
    async def complete(self, prompt: str) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._api_key) if self._api_key else AsyncAnthropic()
        resp = await client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/test_provider_complete.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: Full suite (no regressions)**

Run: `uv run pytest -q`
Expected: all green (existing provider/router/search tests still pass).

- [ ] **Step 8: Commit**

```bash
git add src/deeptalk/llm/provider.py src/deeptalk/llm/fake.py src/deeptalk/llm/anthropic_provider.py tests/test_provider_complete.py
git commit -m "feat: add complete() to LlmProvider seam"
```

---

### Task 2: Intent model + heuristic detector

**Files:**
- Create: `src/deeptalk/intent/__init__.py` (empty)
- Create: `src/deeptalk/intent/models.py`
- Create: `src/deeptalk/intent/base.py`
- Create: `src/deeptalk/intent/heuristic.py`
- Test: `tests/test_intent_heuristic.py`

- [ ] **Step 1: Create the empty package init**

Run: `touch src/deeptalk/intent/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_intent_heuristic.py`:

```python
from deeptalk.intent.heuristic import HeuristicIntentDetector
from deeptalk.intent.models import Intent, normalize_topic


async def test_detects_question_mark():
    d = HeuristicIntentDetector()
    intent = await d.detect("postgres or sqlite?")
    assert isinstance(intent, Intent)
    assert intent.kind == "search"
    assert intent.query == "postgres or sqlite?"


async def test_detects_leading_question_word():
    d = HeuristicIntentDetector()
    intent = await d.detect("should we use postgres or sqlite")
    assert intent is not None
    assert intent.kind == "search"


async def test_ignores_statement():
    d = HeuristicIntentDetector()
    assert await d.detect("postgres scales better for concurrent writes") is None


async def test_ignores_blank():
    d = HeuristicIntentDetector()
    assert await d.detect("   ") is None


def test_normalize_topic_collapses_case_and_punctuation():
    assert normalize_topic("Postgres or SQLite?") == normalize_topic("postgres  or sqlite")
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_intent_heuristic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.intent.heuristic'`

- [ ] **Step 4: Write the models** — `src/deeptalk/intent/models.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    kind: str  # "search"
    query: str
    topic: str  # normalized dedup key


def normalize_topic(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — a dedup key."""
    cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()
```

- [ ] **Step 5: Write the detector interface** — `src/deeptalk/intent/base.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from deeptalk.intent.models import Intent


@runtime_checkable
class IntentDetector(Protocol):
    async def detect(self, text: str) -> Intent | None:
        """Return a search Intent for `text`, or None if nothing actionable."""
        ...
```

- [ ] **Step 6: Write the heuristic detector** — `src/deeptalk/intent/heuristic.py`:

```python
from __future__ import annotations

from deeptalk.intent.models import Intent, normalize_topic

_QUESTION_LEADS = (
    "what", "what's", "how", "why", "when", "where", "who", "which",
    "should we", "should i", "is there", "are there", "can we", "can i",
    "do we", "does", "could we",
)


class HeuristicIntentDetector:
    """Rule-based: a line is a search if it is phrased as a question."""

    async def detect(self, text: str) -> Intent | None:
        line = text.strip()
        if not line:
            return None
        low = line.lower()
        is_question = line.endswith("?") or any(low.startswith(lead) for lead in _QUESTION_LEADS)
        if not is_question:
            return None
        return Intent(kind="search", query=line, topic=normalize_topic(line))
```

- [ ] **Step 7: Run to verify it passes**

Run: `uv run pytest tests/test_intent_heuristic.py -v`
Expected: PASS (5 passed)

- [ ] **Step 8: Commit**

```bash
git add src/deeptalk/intent/__init__.py src/deeptalk/intent/models.py src/deeptalk/intent/base.py src/deeptalk/intent/heuristic.py tests/test_intent_heuristic.py
git commit -m "feat: add Intent model and heuristic detector"
```

---

### Task 3: LLM intent detector

**Files:**
- Create: `src/deeptalk/intent/llm.py`
- Test: `tests/test_intent_llm.py`

- [ ] **Step 1: Write the failing test** — `tests/test_intent_llm.py`:

```python
from deeptalk.intent.llm import LlmIntentDetector
from deeptalk.intent.models import Intent
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter


def _router(provider):
    return ModelRouter(providers={"p": provider}, routes={"intent": ["p"]}, default=["p"])


async def test_returns_intent_when_model_says_search():
    provider = FakeLlmProvider(completion='{"is_search": true, "query": "postgres vs sqlite"}')
    d = LlmIntentDetector(_router(provider))
    intent = await d.detect("we keep going back and forth on the database")
    assert isinstance(intent, Intent)
    assert intent.query == "postgres vs sqlite"


async def test_returns_none_when_model_says_not_search():
    provider = FakeLlmProvider(completion='{"is_search": false, "query": ""}')
    d = LlmIntentDetector(_router(provider))
    assert await d.detect("hello everyone") is None


async def test_returns_none_on_unparseable_output():
    provider = FakeLlmProvider(completion="not json at all")
    d = LlmIntentDetector(_router(provider))
    assert await d.detect("anything") is None


async def test_tolerates_json_wrapped_in_prose():
    provider = FakeLlmProvider(completion='Sure: {"is_search": true, "query": "x y"} done')
    d = LlmIntentDetector(_router(provider))
    intent = await d.detect("q")
    assert intent is not None and intent.query == "x y"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_intent_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.intent.llm'`

- [ ] **Step 3: Write the LLM detector** — `src/deeptalk/intent/llm.py`:

```python
from __future__ import annotations

import json
import re

from deeptalk.intent.models import Intent, normalize_topic
from deeptalk.llm.router import ModelRouter, run_with_fallback

_PROMPT = (
    "You classify a line from a meeting transcript. If it raises a question or a "
    "topic worth looking up, respond with JSON: "
    '{{"is_search": true, "query": "<a concise web search query>"}}. '
    'Otherwise respond {{"is_search": false, "query": ""}}. '
    "Respond with ONLY the JSON.\n\nLine: {text}"
)


def _parse(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class LlmIntentDetector:
    """Classifies transcript lines with an LLM via the router's `complete`."""

    def __init__(self, router: ModelRouter) -> None:
        self._router = router

    async def detect(self, text: str) -> Intent | None:
        prompt = _PROMPT.format(text=text)
        try:
            providers = self._router.chain_for("intent")
            raw = await run_with_fallback(providers, lambda p: p.complete(prompt))
        except Exception:  # noqa: BLE001 - detection is best-effort
            return None
        data = _parse(raw)
        if not data or not data.get("is_search"):
            return None
        query = (data.get("query") or text).strip()
        return Intent(kind="search", query=query, topic=normalize_topic(query))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_intent_llm.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/intent/llm.py tests/test_intent_llm.py
git commit -m "feat: add LLM intent detector"
```

---

### Task 4: Orchestrator

**Files:**
- Create: `src/deeptalk/orchestrator.py`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing test** — `tests/test_orchestrator.py`:

```python
import asyncio

from deeptalk.intent.heuristic import HeuristicIntentDetector
from deeptalk.intent.models import Intent
from deeptalk.orchestrator import Orchestrator, run_orchestrator
from deeptalk.bus import EventBus
from deeptalk.transcript.events import TranscriptEvent


class _RecordingDetector:
    def __init__(self, intent):
        self._intent = intent

    async def detect(self, text):
        return self._intent


async def test_handle_fires_on_intent(tmp_path):
    fired = []
    intent = Intent(kind="search", query="q", topic="q")
    orch = Orchestrator(_RecordingDetector(intent), fire=lambda i: fired.append(i.query) or _noop())
    result = await orch.handle("anything")
    assert result is intent
    assert fired == ["q"]


async def test_handle_dedups_by_topic():
    fired = []
    intent = Intent(kind="search", query="postgres or sqlite", topic="postgres or sqlite")

    async def fire(i):
        fired.append(i.query)

    orch = Orchestrator(_RecordingDetector(intent), fire=fire)
    await orch.handle("line one")
    second = await orch.handle("line two")  # same topic
    assert second is None
    assert fired == ["postgres or sqlite"]  # fired once


async def test_handle_skips_when_no_intent():
    fired = []

    async def fire(i):
        fired.append(i)

    orch = Orchestrator(_RecordingDetector(None), fire=fire)
    assert await orch.handle("just chatting") is None
    assert fired == []


async def test_run_orchestrator_fires_on_final_transcript_line():
    bus = EventBus()
    fired = []
    intent = Intent(kind="search", query="q", topic="q")

    async def fire(i):
        fired.append(i.query)

    orch = Orchestrator(_RecordingDetector(intent), fire=fire)
    task = asyncio.create_task(run_orchestrator(bus, orch, "s1"))
    await asyncio.sleep(0)
    await bus.publish(TranscriptEvent(session_id="s1", ts=0.0, text="should we X?", is_final=True))
    await asyncio.sleep(0.05)
    task.cancel()
    import contextlib
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert fired == ["q"]


async def test_run_orchestrator_ignores_non_final_and_other_sessions():
    bus = EventBus()
    fired = []
    intent = Intent(kind="search", query="q", topic="q")

    async def fire(i):
        fired.append(i.query)

    orch = Orchestrator(_RecordingDetector(intent), fire=fire)
    task = asyncio.create_task(run_orchestrator(bus, orch, "s1"))
    await asyncio.sleep(0)
    await bus.publish(TranscriptEvent(session_id="s1", ts=0.0, text="x", is_final=False))
    await bus.publish(TranscriptEvent(session_id="s2", ts=0.0, text="x?", is_final=True))
    await asyncio.sleep(0.05)
    task.cancel()
    import contextlib
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert fired == []


def _noop():
    async def n():
        return None
    return n()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.orchestrator'`

- [ ] **Step 3: Write the orchestrator** — `src/deeptalk/orchestrator.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from deeptalk.bus import EventBus
from deeptalk.intent.base import IntentDetector
from deeptalk.intent.models import Intent


class Orchestrator:
    """Detects intent on a line, dedups by topic, fires the agent (bounded)."""

    def __init__(
        self,
        detector: IntentDetector,
        fire: Callable[[Intent], Awaitable[None]],
        max_concurrent: int = 3,
    ) -> None:
        self._detector = detector
        self._fire = fire
        self._seen: set[str] = set()
        self._sem = asyncio.Semaphore(max_concurrent)

    async def handle(self, text: str) -> Intent | None:
        intent = await self._detector.detect(text)
        if intent is None or intent.topic in self._seen:
            return None
        self._seen.add(intent.topic)
        async with self._sem:
            await self._fire(intent)
        return intent


async def run_orchestrator(bus: EventBus, orchestrator: Orchestrator, session_id: str) -> None:
    """Consume the transcript bus; handle each final line for this session."""
    q = bus.subscribe()
    try:
        while True:
            ev = await q.get()
            if ev.session_id == session_id and getattr(ev, "is_final", False):
                asyncio.create_task(orchestrator.handle(ev.text))
    finally:
        bus.unsubscribe(q)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add Orchestrator with dedup and transcript-driven firing"
```

---

### Task 5: Detector factory + config + entrypoint wiring

**Files:**
- Modify: `src/deeptalk/config.py`
- Modify: `src/deeptalk/llm/factory.py`
- Create: `src/deeptalk/intent/factory.py`
- Modify: `src/deeptalk/server/__main__.py`
- Test: `tests/test_intent_heuristic.py` (append a factory test) — or a small new check inline

- [ ] **Step 1: Extend `Config`** — in `src/deeptalk/config.py`:

Add a field (after `anthropic_model`):
```python
    intent_detector: str = "heuristic"  # "heuristic" | "llm"
```
And in `from_env`, add to the `cls(...)` call:
```python
            intent_detector=e.get("DEEPTALK_INTENT", "heuristic"),
```

- [ ] **Step 2: Register the `intent` route in the router** — in `src/deeptalk/llm/factory.py`, change the two `return ModelRouter(...)` constructions so `routes` includes `intent` with the same chain. Concretely, replace the function body's `routes={"search": chain}` with `routes={"search": chain, "intent": chain}` (there is one `return`; update it):

```python
    return ModelRouter(providers=providers, routes={"search": chain, "intent": chain}, default=chain)
```

- [ ] **Step 3: Write the detector factory** — `src/deeptalk/intent/factory.py`:

```python
from __future__ import annotations

from deeptalk.config import Config
from deeptalk.intent.base import IntentDetector
from deeptalk.llm.router import ModelRouter


def build_detector(config: Config, router: ModelRouter) -> IntentDetector:
    if config.intent_detector == "llm":
        from deeptalk.intent.llm import LlmIntentDetector

        return LlmIntentDetector(router)
    from deeptalk.intent.heuristic import HeuristicIntentDetector

    return HeuristicIntentDetector()
```

- [ ] **Step 4: Write a factory test** — create `tests/test_intent_factory.py`:

```python
from deeptalk.config import Config
from deeptalk.intent.factory import build_detector
from deeptalk.intent.heuristic import HeuristicIntentDetector
from deeptalk.intent.llm import LlmIntentDetector
from deeptalk.llm.factory import build_router


def test_factory_default_is_heuristic():
    cfg = Config.from_env({})
    d = build_detector(cfg, build_router(cfg))
    assert isinstance(d, HeuristicIntentDetector)


def test_factory_llm_when_selected():
    cfg = Config.from_env({"DEEPTALK_INTENT": "llm"})
    d = build_detector(cfg, build_router(cfg))
    assert isinstance(d, LlmIntentDetector)
```

- [ ] **Step 5: Run the factory + intent tests**

Run: `uv run pytest tests/test_intent_factory.py tests/test_intent_heuristic.py tests/test_intent_llm.py -v`
Expected: PASS.

- [ ] **Step 6: Wire the orchestrator into the entrypoint** — in `src/deeptalk/server/__main__.py`:

Add imports with the others:
```python
import time
from deeptalk.agents.search import run_search
from deeptalk.intent.factory import build_detector
from deeptalk.orchestrator import Orchestrator, run_orchestrator
```
In `main()`, after `router = build_router(config)` (and after `artifact_store`/`artifact_bus` exist), the lifespan should ALSO start the orchestrator. Update the `lifespan` context manager so it starts BOTH the ingest task and the orchestrator task, and cancels both on shutdown. Replace the existing `lifespan` definition with:

```python
    @asynccontextmanager
    async def lifespan(app):
        detector = build_detector(config, router)

        async def fire(intent):
            await run_search(
                intent.query, config.session_id, router, artifact_store, artifact_bus, time.time()
            )

        orchestrator = Orchestrator(detector, fire)

        stt = build_stt(config)
        ingest_task = asyncio.create_task(run_ingest(stt, store, bus))
        orch_task = asyncio.create_task(run_orchestrator(bus, orchestrator, config.session_id))
        app.state.ingest_task = ingest_task
        app.state.orch_task = orch_task
        try:
            yield
        finally:
            for task in (ingest_task, orch_task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
```
(Keep the rest of `main()` — `create_app(...)` call and `uvicorn.run` — unchanged.)

- [ ] **Step 7: Full suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 8: Smoke — auto-fire from the fixture (no key, fake provider + fake STT)**

The bundled fixture line "should we use postgres or sqlite" starts with "should we" → the heuristic fires a search automatically (no manual `/ask`).
```bash
rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-4.log 2>&1 &
SERVER_PID=$!
sleep 8
uv run python -c "from deeptalk.artifacts.store import ArtifactStore; a=ArtifactStore('deeptalk-demo.db').all_artifacts('demo'); print('artifacts:', [(x.agent, x.title) for x in a])"
kill $SERVER_PID 2>/dev/null
```
Expected: at least one artifact auto-created, e.g. `artifacts: [('search', 'should we use postgres or sqlite')]` — produced WITHOUT any manual `/ask` call. Paste `/tmp/deeptalk-4.log` tail on failure.

- [ ] **Step 9: Commit**

```bash
git add src/deeptalk/config.py src/deeptalk/llm/factory.py src/deeptalk/intent/factory.py src/deeptalk/server/__main__.py tests/test_intent_factory.py
git commit -m "feat: wire orchestrator into entrypoint with detector factory"
```

---

### Task 6: UI tap-to-fire

**Files:**
- Modify: `ui/src/TranscriptPane.tsx`
- Modify: `ui/src/App.tsx`
- Test: `ui/src/__tests__/TranscriptPane.test.tsx`

- [ ] **Step 1: Add a failing click test** — append to `ui/src/__tests__/TranscriptPane.test.tsx`:

```tsx
import userEvent from '@testing-library/user-event'

it('calls onLineClick with the line text when a line is clicked', async () => {
  const onLineClick = vi.fn()
  render(<TranscriptPane events={[ev({ text: 'click me' })]} onLineClick={onLineClick} />)
  await userEvent.click(screen.getByText('click me'))
  expect(onLineClick).toHaveBeenCalledWith('click me')
})
```
(Ensure `vi` is imported in this file — it uses `describe/it/expect` from vitest; add `import { vi } from 'vitest'` if not already present.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/TranscriptPane.test.tsx`
Expected: FAIL — clicking does not call `onLineClick` (prop not supported yet).

- [ ] **Step 3: Update `ui/src/TranscriptPane.tsx`** to accept an optional `onLineClick`:

```tsx
import type { TranscriptEvent } from './types'

export function TranscriptPane({
  events,
  onLineClick,
}: {
  events: TranscriptEvent[]
  onLineClick?: (text: string) => void
}) {
  if (events.length === 0) {
    return <p className="transcript-empty">Listening…</p>
  }
  return (
    <ol className="transcript">
      {events.map((e, i) => (
        <li
          key={i}
          className={`line ${e.is_final ? 'final' : 'interim'}${onLineClick ? ' clickable' : ''}`}
          onClick={onLineClick ? () => onLineClick(e.text) : undefined}
          title={onLineClick ? 'Search this line' : undefined}
        >
          {e.speaker != null && <span className="speaker">S{e.speaker}</span>}
          <span className="text">{e.text}</span>
        </li>
      ))}
    </ol>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/TranscriptPane.test.tsx`
Expected: PASS (existing 4 + the new click test).

- [ ] **Step 5: Wire it in `ui/src/App.tsx`** — pass `onLineClick` to the transcript pane so clicking a line asks about it. Change the `<TranscriptPane events={events} />` line to:

```tsx
          <TranscriptPane events={events} onLineClick={handleAsk} />
```
(`handleAsk` already exists and takes a query string.)

- [ ] **Step 6: Add a `.clickable` affordance** — append to `ui/src/styles.css`:

```css
.line.clickable { cursor: pointer; }
.line.clickable:hover { border: 1px solid var(--accent); }
```

- [ ] **Step 7: Typecheck, test, build**

Run:
```bash
cd ui && npm run typecheck && npm test && npm run build
```
Expected: typecheck clean; all UI tests pass; `dist/` built.

- [ ] **Step 8: Commit**

```bash
git add ui/src/TranscriptPane.tsx ui/src/App.tsx ui/src/styles.css ui/src/__tests__/TranscriptPane.test.tsx
git commit -m "feat(ui): tap a transcript line to search it"
```

---

## On a machine with an Anthropic key (LLM intent validation)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
DEEPTALK_INTENT=llm DEEPTALK_SEARCH_PROVIDER=anthropic uv run python -m deeptalk.server
```
The LLM now classifies each final transcript line and fires searches for genuine
questions. If classification misbehaves, tune the prompt in
`src/deeptalk/intent/llm.py`.

---

## Self-Review

**Spec coverage (Phase 4):** Implements §7 Intent Detector (#5, Tasks 2–3, heuristic + LLM behind one interface), the Orchestrator (#6, Task 4: detect → dedup → bounded fire, transcript-bus driven), runtime selection (Task 5), and manual tap-to-fire (Task 6). The provider seam gains `complete()` (Task 1) so the LLM detector can classify without web search. Remaining agents and the wiki are later phases — not gaps.

**Placeholder scan:** No TBD/TODO. Validation-deferred pieces are the providers' real `complete()` and `LlmIntentDetector` against a live key — both unit-tested with a fake (scripted completion) and flagged for key validation. Every step has exact code + commands + expected output.

**Type consistency:** `Intent(kind, query, topic)` + `normalize_topic` (Task 2) are used by the heuristic (Task 2), LLM detector (Task 3), and orchestrator dedup (Task 4). `IntentDetector.detect(text) -> Intent | None` (Task 2) is implemented by both detectors and consumed by `Orchestrator` (Task 4) and `build_detector` (Task 5). `LlmProvider.complete(prompt) -> str` (Task 1) is implemented by Fake + Anthropic and called by `LlmIntentDetector` via `run_with_fallback` (Task 3). `Orchestrator(detector, fire, max_concurrent)` + `run_orchestrator(bus, orchestrator, session_id)` match between Task 4 and the entrypoint (Task 5). The router gains an `"intent"` route (Task 5) that `chain_for("intent")` (Task 3) relies on. UI `onLineClick(text)` (Task 6) matches `handleAsk(query)`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase4-orchestrator.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
