# DeepTalk Phase 5A — Pros/Cons + Planning Agents (backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two more agents — **pros/cons + opinion** (fires on a debated decision) and **planning** (fires on a goal/plan discussion) — driven by the existing orchestrator. Extend intent detection to classify a line's *kind* (search / debate / planning) and dispatch each kind to its agent.

**Architecture:** Intent now carries a `kind`; the heuristic and LLM detectors classify into `search | debate | planning`. The orchestrator is unchanged — the entrypoint's `fire` closure switches on `intent.kind` and calls `run_search`, `run_proscons`, or `run_planning`. The two new agents use the router's `complete()` (general LLM, JSON output) via a shared `run_completion_agent` helper, producing structured `Artifact` payloads. The `FakeLlmProvider` gains a JSON stub so dev/tests get realistic structured output with no key.

**Tech Stack:** Python 3.12, uv, FastAPI, pytest + pytest-asyncio.

---

## Roadmap context

Phase 5A of spec §15 phase 5. Phases 1–4 on `main`: transcript → live STT → router + search agent + artifacts + ask box → orchestrator auto-fire + tap-to-fire. This adds the §7 pros/cons and planning agents. The mockup agent (Phase 8) and the UI cards for these payloads (Phase 5B) are separate.

## File Structure (Phase 5A)

```
deeptalk/
  src/deeptalk/
    intent/
      heuristic.py            # MODIFY: classify kind (planning/debate/search)
      llm.py                  # MODIFY: classify kind via JSON
    llm/
      fake.py                 # MODIFY: JSON stub default for agent prompts
      factory.py              # MODIFY: add proscons/planning routes
    agents/
      common.py               # NEW: run_completion_agent + parse_json
      proscons.py             # NEW: run_proscons
      planning.py             # NEW: run_planning
    server/__main__.py        # MODIFY: fire dispatch by intent.kind
  tests/
    test_intent_heuristic.py  # MODIFY: kind assertions
    test_intent_llm.py        # MODIFY: kind assertions
    test_provider_complete.py # MODIFY: add json-stub test
    test_agents_completion.py # NEW: proscons + planning
```

---

### Task 1: Classify intent kind (heuristic + LLM)

**Files:**
- Modify: `src/deeptalk/intent/heuristic.py`, `src/deeptalk/intent/llm.py`
- Modify: `tests/test_intent_heuristic.py`, `tests/test_intent_llm.py`

- [ ] **Step 1: Replace `tests/test_intent_heuristic.py`** with kind-aware tests:

```python
from deeptalk.intent.heuristic import HeuristicIntentDetector
from deeptalk.intent.models import Intent, normalize_topic


async def test_question_is_search():
    intent = await HeuristicIntentDetector().detect("what is rust")
    assert isinstance(intent, Intent) and intent.kind == "search"


async def test_question_mark_is_search():
    intent = await HeuristicIntentDetector().detect("is rust memory safe?")
    assert intent is not None and intent.kind == "search"


async def test_or_choice_is_debate():
    intent = await HeuristicIntentDetector().detect("should we use postgres or sqlite")
    assert intent is not None and intent.kind == "debate"


async def test_pros_and_cons_is_debate():
    intent = await HeuristicIntentDetector().detect("what are the pros and cons of kafka")
    assert intent is not None and intent.kind == "debate"


async def test_planning_phrase_is_planning():
    intent = await HeuristicIntentDetector().detect("how do we build the auth system")
    assert intent is not None and intent.kind == "planning"


async def test_lets_plan_is_planning():
    intent = await HeuristicIntentDetector().detect("let's plan the migration")
    assert intent is not None and intent.kind == "planning"


async def test_statement_is_none():
    assert await HeuristicIntentDetector().detect("postgres scales better for writes") is None


async def test_blank_is_none():
    assert await HeuristicIntentDetector().detect("   ") is None


def test_normalize_topic_stable():
    assert normalize_topic("Postgres or SQLite?") == normalize_topic("postgres  or sqlite")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_intent_heuristic.py -v`
Expected: FAIL — current detector only returns `kind="search"`, so debate/planning tests fail.

- [ ] **Step 3: Rewrite `src/deeptalk/intent/heuristic.py`**

```python
from __future__ import annotations

from deeptalk.intent.models import Intent, normalize_topic

_PLANNING_SIGNALS = (
    "how do we build", "how do we implement", "what are the steps", "what's the plan",
    "lay out", "outline the", "break down", "roadmap", "let's plan", "lets plan",
    "plan the", "plan for", "plan a", "step by step",
)
_DEBATE_SIGNALS = (
    " or ", " vs ", " versus ", "pros and cons", "trade-off", "tradeoff",
    "which is better", "better option", "compare",
)
_QUESTION_LEADS = (
    "what", "what's", "how", "why", "when", "where", "who", "which",
    "should we", "should i", "is there", "are there", "can we", "can i",
    "do we", "does", "could we", "is ", "are ",
)


def _classify(low: str, line: str) -> str | None:
    padded = f" {low} "
    if any(sig in low for sig in _PLANNING_SIGNALS):
        return "planning"
    if any(sig in padded for sig in _DEBATE_SIGNALS):
        return "debate"
    if line.endswith("?") or any(low.startswith(lead) for lead in _QUESTION_LEADS):
        return "search"
    return None


class HeuristicIntentDetector:
    """Rule-based classifier: planning, debate, or search (or nothing)."""

    async def detect(self, text: str) -> Intent | None:
        line = text.strip()
        if not line:
            return None
        kind = _classify(line.lower(), line)
        if kind is None:
            return None
        return Intent(kind=kind, query=line, topic=normalize_topic(line))
```

- [ ] **Step 4: Run to verify heuristic passes**

Run: `uv run pytest tests/test_intent_heuristic.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Replace `tests/test_intent_llm.py`** with kind-aware tests:

```python
from deeptalk.intent.llm import LlmIntentDetector
from deeptalk.intent.models import Intent
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter


def _router(provider):
    return ModelRouter(providers={"p": provider}, routes={"intent": ["p"]}, default=["p"])


async def test_classifies_debate():
    provider = FakeLlmProvider(completion='{"kind": "debate", "query": "postgres vs sqlite"}')
    intent = await LlmIntentDetector(_router(provider)).detect("we keep arguing about the db")
    assert isinstance(intent, Intent)
    assert intent.kind == "debate"
    assert intent.query == "postgres vs sqlite"


async def test_classifies_planning():
    provider = FakeLlmProvider(completion='{"kind": "planning", "query": "plan the migration"}')
    intent = await LlmIntentDetector(_router(provider)).detect("we need to migrate")
    assert intent is not None and intent.kind == "planning"


async def test_none_kind_returns_none():
    provider = FakeLlmProvider(completion='{"kind": "none", "query": ""}')
    assert await LlmIntentDetector(_router(provider)).detect("hello everyone") is None


async def test_unparseable_returns_none():
    provider = FakeLlmProvider(completion="not json")
    assert await LlmIntentDetector(_router(provider)).detect("anything") is None


async def test_json_in_prose_ok():
    provider = FakeLlmProvider(completion='ok: {"kind": "search", "query": "x y"} end')
    intent = await LlmIntentDetector(_router(provider)).detect("q")
    assert intent is not None and intent.kind == "search" and intent.query == "x y"
```

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_intent_llm.py -v`
Expected: FAIL — current LLM detector returns based on `is_search`, not `kind`.

- [ ] **Step 7: Rewrite `src/deeptalk/intent/llm.py`**

```python
from __future__ import annotations

import json
import re

from deeptalk.intent.models import Intent, normalize_topic
from deeptalk.llm.router import ModelRouter, run_with_fallback

_VALID_KINDS = ("search", "debate", "planning")

_PROMPT = (
    "Classify a line from a meeting transcript into one kind:\n"
    "- search: a question or fact worth looking up\n"
    "- debate: a decision between options / pros and cons\n"
    "- planning: a goal that needs a plan or steps\n"
    "- none: anything else\n"
    'Respond ONLY as JSON: {{"kind": "search|debate|planning|none", '
    '"query": "<concise topic/query>"}}.\n\nLine: {text}'
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
    """Classifies transcript lines into a kind with an LLM via `complete`."""

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
        if not data:
            return None
        kind = data.get("kind")
        if kind not in _VALID_KINDS:
            return None
        query = (data.get("query") or text).strip()
        return Intent(kind=kind, query=query, topic=normalize_topic(query))
```

- [ ] **Step 8: Run to verify LLM passes + full suite**

Run: `uv run pytest tests/test_intent_llm.py -v && uv run pytest -q`
Expected: LLM 5 passed; full suite green (orchestrator tests still pass — they use a recording detector, unaffected).

- [ ] **Step 9: Commit**

```bash
git add src/deeptalk/intent/heuristic.py src/deeptalk/intent/llm.py tests/test_intent_heuristic.py tests/test_intent_llm.py
git commit -m "feat: classify intent kind (search/debate/planning)"
```

---

### Task 2: Fake JSON stub + completion-agent helper + pros/cons agent

**Files:**
- Modify: `src/deeptalk/llm/fake.py`
- Modify: `tests/test_provider_complete.py`
- Create: `src/deeptalk/agents/common.py`
- Create: `src/deeptalk/agents/proscons.py`
- Test: `tests/test_agents_completion.py`

- [ ] **Step 1: Add a failing fake-stub test** — append to `tests/test_provider_complete.py`:

```python
async def test_fake_complete_returns_json_stub_for_json_prompts():
    import json
    p = FakeLlmProvider()
    out = await p.complete("Respond ONLY as JSON with pros and cons")
    data = json.loads(out)
    assert "pros" in data and "cons" in data and "steps" in data
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_provider_complete.py::test_fake_complete_returns_json_stub_for_json_prompts -v`
Expected: FAIL — default `complete` echoes the prompt (not JSON).

- [ ] **Step 3: Update `FakeLlmProvider.complete`** — in `src/deeptalk/llm/fake.py`, add a module-level stub constant and update `complete`:

Add near the top (after imports):
```python
_JSON_STUB = (
    '{"is_search": false, "kind": "none", "query": "", '
    '"pros": ["fake pro"], "cons": ["fake con"], '
    '"recommendation": "fake recommendation", '
    '"steps": ["fake step one", "fake step two"]}'
)
```
Replace the `complete` method body with:
```python
    async def complete(self, prompt: str) -> str:
        if self._completion is not None:
            return self._completion
        if "json" in prompt.lower():
            return _JSON_STUB
        return f"(fake) {prompt}"
```
(The existing `test_fake_complete_default_echoes_prompt` uses prompt "classify this" — no "json" — so it still echoes and passes.)

- [ ] **Step 4: Run to verify fake tests pass**

Run: `uv run pytest tests/test_provider_complete.py -v`
Expected: PASS (5 passed — the 4 original + the new stub test).

- [ ] **Step 5: Write the failing agent test** — `tests/test_agents_completion.py`:

```python
import asyncio

from deeptalk.agents.proscons import run_proscons
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter


def _router(provider, agent):
    return ModelRouter(providers={"p": provider}, routes={agent: ["p"]}, default=["p"])


async def test_proscons_builds_structured_artifact(tmp_path):
    provider = FakeLlmProvider(
        completion='{"pros": ["fast"], "cons": ["complex"], "recommendation": "use it"}'
    )
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_proscons("kafka or rabbitmq", "s1", _router(provider, "proscons"), store, bus, now=5.0)

    assert art.status == "done"
    assert art.agent == "proscons"
    assert art.title == "kafka or rabbitmq"
    assert art.payload["pros"] == ["fast"]
    assert art.payload["cons"] == ["complex"]
    assert art.payload["recommendation"] == "use it"
    assert store.all_artifacts("s1")[0].agent == "proscons"


async def test_proscons_persists_and_publishes(tmp_path):
    provider = FakeLlmProvider(completion='{"pros": [], "cons": [], "recommendation": ""}')
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    q = bus.subscribe()
    await run_proscons("q", "s1", _router(provider, "proscons"), store, bus, now=1.0)
    published = await asyncio.wait_for(q.get(), timeout=1.0)
    assert published.agent == "proscons"


async def test_proscons_error_on_unparseable(tmp_path):
    provider = FakeLlmProvider(completion="not json")
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_proscons("q", "s1", _router(provider, "proscons"), store, bus, now=2.0)
    assert art.status == "error"
    assert art.error
```

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_agents_completion.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.agents.proscons'`

- [ ] **Step 7: Write the shared helper** — `src/deeptalk/agents/common.py`:

```python
from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from typing import Any

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter, run_with_fallback


def parse_json(raw: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


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
) -> Artifact:
    """Run a JSON-output completion agent: call -> parse -> artifact -> persist/publish."""
    try:
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

- [ ] **Step 8: Write the pros/cons agent** — `src/deeptalk/agents/proscons.py`:

```python
from __future__ import annotations

from typing import Any

from deeptalk.agents.common import run_completion_agent
from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter

AGENT = "proscons"

_PROMPT = (
    "A team is weighing a decision. Give a balanced analysis. "
    'Respond ONLY as JSON: {{"pros": ["..."], "cons": ["..."], '
    '"recommendation": "..."}}.\n\nDecision: {query}'
)


def _payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "pros": data.get("pros", []),
        "cons": data.get("cons", []),
        "recommendation": data.get("recommendation", ""),
    }


async def run_proscons(
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
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
    )
```

- [ ] **Step 9: Run to verify it passes**

Run: `uv run pytest tests/test_agents_completion.py -v`
Expected: PASS (3 passed)

- [ ] **Step 10: Commit**

```bash
git add src/deeptalk/llm/fake.py tests/test_provider_complete.py src/deeptalk/agents/common.py src/deeptalk/agents/proscons.py tests/test_agents_completion.py
git commit -m "feat: add completion-agent helper, pros/cons agent, fake JSON stub"
```

---

### Task 3: Planning agent

**Files:**
- Create: `src/deeptalk/agents/planning.py`
- Modify: `tests/test_agents_completion.py` (append planning tests)

- [ ] **Step 1: Append failing planning tests** — to `tests/test_agents_completion.py`:

```python
from deeptalk.agents.planning import run_planning


async def test_planning_builds_steps_artifact(tmp_path):
    provider = FakeLlmProvider(completion='{"steps": ["set up repo", "add auth", "ship"]}')
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_planning("build the auth system", "s1", _router(provider, "planning"), store, bus, now=7.0)

    assert art.status == "done"
    assert art.agent == "planning"
    assert art.payload["steps"] == ["set up repo", "add auth", "ship"]


async def test_planning_error_on_unparseable(tmp_path):
    provider = FakeLlmProvider(completion="nope")
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_planning("q", "s1", _router(provider, "planning"), store, bus, now=2.0)
    assert art.status == "error"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_agents_completion.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.agents.planning'`

- [ ] **Step 3: Write the planning agent** — `src/deeptalk/agents/planning.py`:

```python
from __future__ import annotations

from typing import Any

from deeptalk.agents.common import run_completion_agent
from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter

AGENT = "planning"

_PROMPT = (
    "Break the goal into a concrete, ordered plan. "
    'Respond ONLY as JSON: {{"steps": ["step one", "step two", "..."]}}.\n\nGoal: {query}'
)


def _payload(data: dict[str, Any]) -> dict[str, Any]:
    return {"steps": data.get("steps", [])}


async def run_planning(
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
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
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_agents_completion.py -v`
Expected: PASS (5 passed total)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/agents/planning.py tests/test_agents_completion.py
git commit -m "feat: add planning agent"
```

---

### Task 4: Router routes + orchestrator dispatch by kind

**Files:**
- Modify: `src/deeptalk/llm/factory.py`
- Modify: `src/deeptalk/server/__main__.py`
- Test: `tests/test_dispatch.py` (new — verifies kind→agent mapping logic)

- [ ] **Step 1: Add proscons/planning routes** — in `src/deeptalk/llm/factory.py`, change the `routes=` dict in the `return ModelRouter(...)` to include all agent routes on the same chain:

```python
    return ModelRouter(
        providers=providers,
        routes={"search": chain, "intent": chain, "proscons": chain, "planning": chain},
        default=chain,
    )
```

- [ ] **Step 2: Write a failing dispatch test** — `tests/test_dispatch.py`:

This verifies the kind→agent dispatch mapping in isolation (the entrypoint closure logic), without booting uvicorn.

```python
from deeptalk.server.dispatch import make_fire
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.intent.models import Intent
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter


def _router():
    p = FakeLlmProvider()
    return ModelRouter(
        providers={"fake": p},
        routes={"search": ["fake"], "proscons": ["fake"], "planning": ["fake"]},
        default=["fake"],
    )


def _ctx(tmp_path):
    return ArtifactStore(str(tmp_path / "a.db")), EventBus(), _router()


async def test_dispatch_search(tmp_path):
    store, bus, router = _ctx(tmp_path)
    fire = make_fire(router, store, bus, "s1", now=lambda: 1.0)
    await fire(Intent(kind="search", query="what is rust", topic="t"))
    arts = store.all_artifacts("s1")
    assert len(arts) == 1 and arts[0].agent == "search"


async def test_dispatch_debate(tmp_path):
    store, bus, router = _ctx(tmp_path)
    fire = make_fire(router, store, bus, "s1", now=lambda: 1.0)
    await fire(Intent(kind="debate", query="kafka or rabbitmq", topic="t"))
    assert store.all_artifacts("s1")[0].agent == "proscons"


async def test_dispatch_planning(tmp_path):
    store, bus, router = _ctx(tmp_path)
    fire = make_fire(router, store, bus, "s1", now=lambda: 1.0)
    await fire(Intent(kind="planning", query="build auth", topic="t"))
    assert store.all_artifacts("s1")[0].agent == "planning"


async def test_dispatch_unknown_kind_noops(tmp_path):
    store, bus, router = _ctx(tmp_path)
    fire = make_fire(router, store, bus, "s1", now=lambda: 1.0)
    await fire(Intent(kind="mystery", query="x", topic="t"))
    assert store.all_artifacts("s1") == []
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.server.dispatch'`

- [ ] **Step 4: Create `src/deeptalk/server/dispatch.py`**

Extracting the dispatch into a testable factory (instead of an inline closure) keeps it unit-testable.

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable

from deeptalk.agents.planning import run_planning
from deeptalk.agents.proscons import run_proscons
from deeptalk.agents.search import run_search
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
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
) -> Callable[[Intent], Awaitable[None]]:
    """Build the orchestrator's `fire` callback that routes a kind to its agent."""

    async def fire(intent: Intent) -> None:
        runner = _AGENTS.get(intent.kind)
        if runner is None:
            return
        await runner(intent.query, session_id, router, store, bus, now())

    return fire
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (4 passed). The `search`/`debate`/`planning` kinds each create the right agent's artifact; unknown kind no-ops.

- [ ] **Step 6: Wire the entrypoint to use `make_fire`** — in `src/deeptalk/server/__main__.py`:

Add the import:
```python
from deeptalk.server.dispatch import make_fire
```
In the `lifespan`, replace the inline `fire` definition (the `async def fire(intent): await run_search(...)`) with:
```python
        fire = make_fire(router, artifact_store, artifact_bus, config.session_id, time.time)
```
Remove the now-unused direct `run_search` import from `__main__.py` if present (the dispatch module owns it). Keep `build_detector`, `Orchestrator`, `run_orchestrator`, `time` imports.

- [ ] **Step 7: Full suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 8: Smoke — debate line auto-fires pros/cons (default fake stub, no key)**

The fixture line "should we use postgres or sqlite" classifies as **debate** (`" or "`) → orchestrator dispatches to the pros/cons agent → the fake JSON stub yields a structured payload.
```bash
rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-5a.log 2>&1 &
SERVER_PID=$!
sleep 8
uv run python -c "from deeptalk.artifacts.store import ArtifactStore; a=ArtifactStore('deeptalk-demo.db').all_artifacts('demo'); print([(x.agent, x.status) for x in a])"
kill $SERVER_PID 2>/dev/null
```
Expected: `[('proscons', 'done')]` (or similar) — a pros/cons artifact auto-created from the debate line. Paste `/tmp/deeptalk-5a.log` tail on failure.

- [ ] **Step 9: Commit**

```bash
git add src/deeptalk/llm/factory.py src/deeptalk/server/dispatch.py src/deeptalk/server/__main__.py tests/test_dispatch.py
git commit -m "feat: dispatch intent kinds to search/proscons/planning agents"
```

---

## On a machine with an Anthropic key (real agents)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
DEEPTALK_SEARCH_PROVIDER=anthropic uv run python -m deeptalk.server
```
Now debate lines get real pros/cons + a recommendation; planning lines get a real
step plan; questions get web-sourced answers — all auto-fired from the transcript.

---

## Self-Review

**Spec coverage (Phase 5A):** Adds the §7 pros/cons+opinion and planning agents (#8), classified by an extended Intent Detector (#5, now search/debate/planning) and dispatched by the Orchestrator (#6, unchanged — dispatch lives in a testable `make_fire`). The mockup agent is Phase 8; the UI cards for these payloads are Phase 5B — not gaps.

**Placeholder scan:** No TBD/TODO. The fake JSON stub gives realistic dev/test output with no key; real structured reasoning is validated with a key. Every step has exact code + commands + expected output.

**Type consistency:** `Intent.kind` now spans `search|debate|planning` (Task 1), consumed by `make_fire`'s `_AGENTS` map (Task 4). `run_completion_agent(agent, query, session_id, router, store, bus, now, prompt, build_payload)` (Task 2) is used by `run_proscons` (Task 2) and `run_planning` (Task 3) with matching signatures `run_X(query, session_id, router, store, bus, now)` — identical to `run_search`, so all three slot into `_AGENTS` uniformly. `FakeLlmProvider.complete` JSON stub (Task 2) satisfies the proscons/planning/intent parsers. Router routes for `proscons`/`planning` (Task 4) back `chain_for` in `run_completion_agent`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase5a-proscons-planning-agents.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
