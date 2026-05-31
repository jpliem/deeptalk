# DeepTalk Phase 8 — Mockup / Diagram Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The fourth agent. When the conversation turns to UI or system design, classify the line as `mockup`, generate a **Mermaid diagram** via the LLM, and render it as a card (with a code-block fallback for invalid Mermaid). Gated behind a default-on flag.

**Architecture:** A `run_mockup` agent (same `run_completion_agent` pattern) emits `{diagram: "<mermaid>", caption}`. The intent detectors gain a `mockup` kind (heuristic visual-design signals + LLM). `make_fire` maps `mockup → run_mockup`, skipping it when `enable_mockup` is off. The UI `ArtifactCard` renders a `mockup` artifact by running Mermaid on the diagram source, falling back to a `<pre>` code block if rendering throws.

**Tech Stack:** Python 3.12 backend; React + `mermaid` (new UI dep) + Vitest.

---

## Roadmap context

Phase 8 of spec §15 — the last, flagged-optional agent. Phases 1–7 on `main`. After this the spec roadmap is complete; remaining items are the hardware-validation actions, not phases.

## File Structure (Phase 8)

```
deeptalk/
  src/deeptalk/
    agents/mockup.py            # NEW: run_mockup
    intent/heuristic.py         # MODIFY: mockup signals
    intent/llm.py               # MODIFY: mockup kind
    llm/fake.py                 # MODIFY: stub diagram/caption keys
    llm/factory.py              # MODIFY: mockup route
    server/dispatch.py          # MODIFY: mockup runner + enable_mockup flag
    config.py                   # MODIFY: enable_mockup
    server/__main__.py          # MODIFY: pass enable_mockup
    fixtures/sample_meeting.jsonl  # MODIFY: add a mockup demo line
  ui/
    package.json                # MODIFY: add mermaid dep
    src/types.ts                # MODIFY: diagram/caption in payload
    src/ArtifactCard.tsx        # MODIFY: mockup body (mermaid render + fallback)
    src/styles.css              # MODIFY: mockup card styles
  tests/
    test_agents_mockup.py       # NEW
    test_intent_heuristic.py    # MODIFY: mockup tests
    test_intent_llm.py          # MODIFY: mockup test
    test_dispatch.py            # MODIFY: mockup + flag tests
  ui/src/__tests__/ArtifactCard.test.tsx  # MODIFY: mockup render test
```

---

### Task 1: Mockup agent

**Files:**
- Create: `src/deeptalk/agents/mockup.py`
- Modify: `src/deeptalk/llm/fake.py` (stub), `src/deeptalk/llm/factory.py` (route)
- Test: `tests/test_agents_mockup.py`

- [ ] **Step 1: Write the failing test** — `tests/test_agents_mockup.py`:

```python
from deeptalk.agents.mockup import run_mockup
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter


def _router(provider):
    return ModelRouter(providers={"p": provider}, routes={"mockup": ["p"]}, default=["p"])


async def test_mockup_builds_diagram_artifact(tmp_path):
    provider = FakeLlmProvider(completion='{"diagram": "graph TD; A-->B", "caption": "flow"}')
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_mockup("sketch the login flow", "s1", _router(provider), store, bus, now=3.0)

    assert art.status == "done"
    assert art.agent == "mockup"
    assert art.payload["diagram"] == "graph TD; A-->B"
    assert art.payload["caption"] == "flow"


async def test_mockup_error_on_unparseable(tmp_path):
    provider = FakeLlmProvider(completion="not json")
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_mockup("q", "s1", _router(provider), store, bus, now=1.0)
    assert art.status == "error"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_agents_mockup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.agents.mockup'`

- [ ] **Step 3: Write the agent** — `src/deeptalk/agents/mockup.py`:

```python
from __future__ import annotations

from typing import Any

from deeptalk.agents.common import run_completion_agent
from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter

AGENT = "mockup"

_PROMPT = (
    "The team is discussing a UI or system design. Capture it as a Mermaid diagram "
    "(use 'graph TD' or 'flowchart' syntax). "
    'Respond ONLY as JSON: {{"diagram": "<mermaid source>", "caption": "<one line>"}}.'
    "\n\nDiscussion: {query}"
)


def _payload(data: dict[str, Any]) -> dict[str, Any]:
    return {"diagram": data.get("diagram", ""), "caption": data.get("caption", "")}


async def run_mockup(
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

- [ ] **Step 4: Add `mockup` route** — in `src/deeptalk/llm/factory.py`, add `"mockup": chain` to the routes dict:

```python
        routes={
            "search": chain, "intent": chain, "proscons": chain,
            "planning": chain, "wiki": chain, "mockup": chain,
        },
```

- [ ] **Step 5: Extend the fake stub** — in `src/deeptalk/llm/fake.py`, add diagram/caption keys to `_JSON_STUB` (append before the closing brace):

```python
_JSON_STUB = (
    '{"is_search": false, "kind": "none", "query": "", '
    '"pros": ["fake pro"], "cons": ["fake con"], '
    '"recommendation": "fake recommendation", '
    '"steps": ["fake step one", "fake step two"], '
    '"topics": ["fake topic"], "decisions": ["fake decision"], '
    '"action_items": ["fake action item"], '
    '"diagram": "graph TD; A[Idea]-->B[Mockup]", "caption": "fake diagram"}'
)
```

- [ ] **Step 6: Run to verify it passes + full suite**

Run: `uv run pytest tests/test_agents_mockup.py -v && uv run pytest -q`
Expected: mockup 2 passed; full suite green.

- [ ] **Step 7: Commit**

```bash
git add src/deeptalk/agents/mockup.py src/deeptalk/llm/factory.py src/deeptalk/llm/fake.py tests/test_agents_mockup.py
git commit -m "feat: add mockup (Mermaid diagram) agent"
```

---

### Task 2: Intent kind `mockup`

**Files:**
- Modify: `src/deeptalk/intent/heuristic.py`, `src/deeptalk/intent/llm.py`
- Test: `tests/test_intent_heuristic.py`, `tests/test_intent_llm.py`

- [ ] **Step 1: Append heuristic tests** — to `tests/test_intent_heuristic.py`:

```python
async def test_mockup_signal_is_mockup():
    intent = await HeuristicIntentDetector().detect("can you mockup the dashboard")
    assert intent is not None and intent.kind == "mockup"


async def test_diagram_signal_is_mockup():
    intent = await HeuristicIntentDetector().detect("draw a diagram of the auth flow")
    assert intent is not None and intent.kind == "mockup"


async def test_wireframe_signal_is_mockup():
    intent = await HeuristicIntentDetector().detect("wireframe the login screen")
    assert intent is not None and intent.kind == "mockup"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_intent_heuristic.py -v`
Expected: FAIL — those lines currently classify as search/None, not mockup.

- [ ] **Step 3: Add mockup signals** — in `src/deeptalk/intent/heuristic.py`, add the signals tuple and check it FIRST in `_classify`:

Add near the other signal tuples:
```python
_MOCKUP_SIGNALS = (
    "mockup", "wireframe", "diagram", "sketch", "flowchart",
    "draw the", "draw a", "what should the ui", "screen layout",
    "lay out the screen", "ui look like",
)
```
Change `_classify` so mockup is checked before planning/debate/search:
```python
def _classify(low: str, line: str) -> str | None:
    padded = f" {low} "
    if any(sig in low for sig in _MOCKUP_SIGNALS):
        return "mockup"
    if any(sig in low for sig in _PLANNING_SIGNALS):
        return "planning"
    if any(sig in padded for sig in _DEBATE_SIGNALS):
        return "debate"
    if line.endswith("?") or any(low.startswith(lead) for lead in _QUESTION_LEADS):
        return "search"
    return None
```

- [ ] **Step 4: Run to verify heuristic passes**

Run: `uv run pytest tests/test_intent_heuristic.py -v`
Expected: PASS (all, including the 3 new mockup tests).

- [ ] **Step 5: Append an LLM test** — to `tests/test_intent_llm.py`:

```python
async def test_classifies_mockup():
    provider = FakeLlmProvider(completion='{"kind": "mockup", "query": "dashboard layout"}')
    intent = await LlmIntentDetector(_router(provider)).detect("let's design the dashboard")
    assert intent is not None and intent.kind == "mockup"
```

- [ ] **Step 6: Run to verify it fails**

Run: `uv run pytest tests/test_intent_llm.py::test_classifies_mockup -v`
Expected: FAIL — `mockup` is not yet in `_VALID_KINDS`.

- [ ] **Step 7: Add `mockup` to the LLM detector** — in `src/deeptalk/intent/llm.py`:

Change `_VALID_KINDS`:
```python
_VALID_KINDS = ("search", "debate", "planning", "mockup")
```
Add a line to the prompt's kind list (after the planning line):
```python
    "- mockup: a UI or system design worth sketching as a diagram\n"
```
(Keep the JSON instruction line; just insert the mockup description into the bulleted list.)

- [ ] **Step 8: Run to verify it passes + full suite**

Run: `uv run pytest tests/test_intent_llm.py -v && uv run pytest -q`
Expected: LLM tests pass; full suite green.

- [ ] **Step 9: Commit**

```bash
git add src/deeptalk/intent/heuristic.py src/deeptalk/intent/llm.py tests/test_intent_heuristic.py tests/test_intent_llm.py
git commit -m "feat: classify mockup intent kind"
```

---

### Task 3: Dispatch + enable_mockup flag + entrypoint

**Files:**
- Modify: `src/deeptalk/server/dispatch.py`, `src/deeptalk/config.py`, `src/deeptalk/server/__main__.py`, `fixtures/sample_meeting.jsonl`
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Extend `Config`** — add after `agent_timeout`:

```python
    enable_mockup: bool = True
```
And in `from_env`:
```python
            enable_mockup=e.get("DEEPTALK_ENABLE_MOCKUP", "true").lower() != "false",
```

- [ ] **Step 2: Append dispatch tests** — to `tests/test_dispatch.py`:

```python
async def test_dispatch_mockup(tmp_path):
    store, bus, router = _ctx(tmp_path)
    fire = make_fire(router, store, bus, "s1", now=lambda: 1.0)
    from deeptalk.intent.models import Intent

    await fire(Intent(kind="mockup", query="dashboard", topic="t"))
    assert store.all_artifacts("s1")[0].agent == "mockup"


async def test_dispatch_mockup_skipped_when_disabled(tmp_path):
    store, bus, router = _ctx(tmp_path)
    fire = make_fire(router, store, bus, "s1", now=lambda: 1.0, enable_mockup=False)
    from deeptalk.intent.models import Intent

    await fire(Intent(kind="mockup", query="dashboard", topic="t"))
    assert store.all_artifacts("s1") == []
```

The `_ctx` helper's router needs a `mockup` route. Update `_ctx`'s `ModelRouter` routes to include `"mockup": ["fake"]` (add it alongside the existing routes).

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: FAIL — `make_fire` has no `enable_mockup`; `mockup` not in `_AGENTS`.

- [ ] **Step 4: Update `src/deeptalk/server/dispatch.py`**

Add the import:
```python
from deeptalk.agents.mockup import run_mockup
```
Add `"mockup": run_mockup` to the `_AGENTS` map:
```python
_AGENTS = {
    "search": run_search,
    "debate": run_proscons,
    "planning": run_planning,
    "mockup": run_mockup,
}
```
Add `enable_mockup: bool = True` to `make_fire`'s signature (after `timeout`). Inside `fire`, before resolving the runner, add the skip guard:
```python
    async def fire(intent: Intent) -> None:
        if intent.kind == "mockup" and not enable_mockup:
            return
        runner = _AGENTS.get(intent.kind)
        ...
```
(The cost-cap + timeout logic stays as-is, after this guard.)

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_dispatch.py -v`
Expected: PASS (existing + 2 new mockup tests).

- [ ] **Step 6: Wire the entrypoint** — in `src/deeptalk/server/__main__.py`, pass the flag to `make_fire`:

```python
        fire = make_fire(
            router, artifact_store, artifact_bus, config.session_id, time.time,
            tracker=cost_tracker, timeout=config.agent_timeout,
            enable_mockup=config.enable_mockup,
        )
```

- [ ] **Step 7: Add a mockup demo line** — append to `fixtures/sample_meeting.jsonl`:

```
{"ts": 6.0, "text": "can you mockup the dashboard layout", "is_final": true}
```
(So the default demo auto-fires a mockup card too.)

- [ ] **Step 8: Full suite + smoke**

Run: `uv run pytest -q`
Expected: all green.

Smoke — the demo now auto-fires a mockup (default fake provides a stub diagram):
```bash
rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-8.log 2>&1 &
SERVER_PID=$!
sleep 9
uv run python -c "from deeptalk.artifacts.store import ArtifactStore; print([(x.agent,x.status) for x in ArtifactStore('deeptalk-demo.db').all_artifacts('demo')])"
kill $SERVER_PID 2>/dev/null
```
Expected: artifacts include a `('mockup', 'done')` (alongside the proscons from the debate line). Paste `/tmp/deeptalk-8.log` tail on failure.

- [ ] **Step 9: Commit**

```bash
git add src/deeptalk/server/dispatch.py src/deeptalk/config.py src/deeptalk/server/__main__.py fixtures/sample_meeting.jsonl tests/test_dispatch.py
git commit -m "feat: dispatch mockup agent behind enable_mockup flag"
```

---

### Task 4: UI mockup card (Mermaid render + fallback)

**Files:**
- Modify: `ui/package.json` (mermaid dep), `ui/src/types.ts`, `ui/src/ArtifactCard.tsx`
- Test: `ui/src/__tests__/ArtifactCard.test.tsx`

- [ ] **Step 1: Add the mermaid dependency**

Run: `cd ui && npm install mermaid@^11`

- [ ] **Step 2: Widen the payload type** — in `ui/src/types.ts`, add to `ArtifactPayload`:

```ts
  diagram?: string
  caption?: string
```

- [ ] **Step 3: Append a failing test** — inside the `describe('ArtifactCard', ...)` block in `ui/src/__tests__/ArtifactCard.test.tsx`:

```tsx
  it('renders a mockup artifact: caption + mermaid source', () => {
    render(
      <ArtifactCard
        artifact={art({
          agent: 'mockup',
          title: 'dashboard',
          payload: { diagram: 'graph TD; A-->B', caption: 'dashboard flow' },
        })}
      />,
    )
    expect(screen.getByText('dashboard flow')).toBeInTheDocument()
    // the raw mermaid source is always present (fallback / pre-render content)
    expect(screen.getByText(/graph TD; A-->B/)).toBeInTheDocument()
  })
```
At the top of the test file, mock mermaid so jsdom doesn't try real SVG rendering (add near the other imports):
```tsx
vi.mock('mermaid', () => ({ default: { initialize: vi.fn(), run: vi.fn() } }))
```
(Ensure `vi` is imported from `vitest` at the top — it is used elsewhere in this file.)

- [ ] **Step 4: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/ArtifactCard.test.tsx`
Expected: FAIL — no mockup branch renders the caption/diagram.

- [ ] **Step 5: Add the mockup body to `ui/src/ArtifactCard.tsx`**

Add imports at the top:
```tsx
import { useEffect, useRef } from 'react'
import mermaid from 'mermaid'
```
Add a `MockupBody` component (next to the other body functions):
```tsx
function MockupBody({ a }: { a: Artifact }) {
  const ref = useRef<HTMLPreElement>(null)
  const diagram = a.payload.diagram ?? ''

  useEffect(() => {
    if (!ref.current || !diagram) return
    try {
      mermaid.initialize({ startOnLoad: false, theme: 'dark' })
      mermaid.run({ nodes: [ref.current] })
    } catch {
      // leave the raw mermaid source visible as a fallback
    }
  }, [diagram])

  return (
    <>
      {a.payload.caption && <p className="card-answer">{a.payload.caption}</p>}
      <pre ref={ref} className="mermaid mockup-diagram">
        {diagram}
      </pre>
    </>
  )
}
```
Add the branch in `ArtifactCard` (after the `planning` branch, before the `else`/search):
```tsx
      ) : artifact.agent === 'mockup' ? (
        <MockupBody a={artifact} />
```

- [ ] **Step 6: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/ArtifactCard.test.tsx`
Expected: PASS (existing card tests + the new mockup test). Mermaid is mocked, so the `<pre>` keeps its raw source which the test asserts.

- [ ] **Step 7: Commit**

```bash
git add ui/package.json ui/package-lock.json ui/src/types.ts ui/src/ArtifactCard.tsx ui/src/__tests__/ArtifactCard.test.tsx
git commit -m "feat(ui): render mockup artifacts as Mermaid diagrams"
```

---

### Task 5: Mockup styles + build

**Files:**
- Modify: `ui/src/styles.css`

- [ ] **Step 1: Append to `ui/src/styles.css`**

```css
.mockup-diagram {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  padding: 0.75rem;
  margin: 0.4rem 0 0;
  overflow-x: auto;
  font-family: var(--mono);
  font-size: 0.8rem;
  white-space: pre-wrap;
}

/* mermaid replaces the <pre> content with an <svg> on success */
.mockup-diagram svg {
  max-width: 100%;
  height: auto;
}
```

- [ ] **Step 2: Typecheck, test, build**

Run:
```bash
cd ui && npm run typecheck && npm test && npm run build
```
Expected: typecheck clean; all UI tests pass; `dist/` built (mermaid bundled — the JS bundle grows, expected).

- [ ] **Step 3: End-to-end smoke (mockup card data present)**

```bash
cd .. && rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-8b.log 2>&1 &
SERVER_PID=$!
sleep 9
uv run python -c "from deeptalk.artifacts.store import ArtifactStore; print([(x.agent, sorted(x.payload.keys())) for x in ArtifactStore('deeptalk-demo.db').all_artifacts('demo') if x.agent=='mockup'])"
kill $SERVER_PID 2>/dev/null
```
Expected: a mockup artifact with payload keys `['caption', 'diagram']`. The browser renders it as a diagram. Paste `/tmp/deeptalk-8b.log` tail on failure.

- [ ] **Step 4: Commit**

```bash
git add ui/src/styles.css
git commit -m "style(ui): mockup diagram card"
```

---

## On a machine with an Anthropic key (real diagrams)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
DEEPTALK_SEARCH_PROVIDER=anthropic uv run python -m deeptalk.server
```
Now "let's design the dashboard" / "draw the auth flow" lines auto-produce real Mermaid
diagrams. Disable with `DEEPTALK_ENABLE_MOCKUP=false` if they're too noisy. If a diagram
fails to render, the card shows the raw Mermaid source (graceful fallback).

---

## Self-Review

**Spec coverage (Phase 8):** Adds the §7 mockup agent (#8, the flagged/last one): a `mockup` intent kind (heuristic + LLM), `run_mockup` producing Mermaid, dispatch behind `enable_mockup` (default on), and a UI card that renders Mermaid with a code-block fallback. This completes the spec §15 roadmap.

**Placeholder scan:** No TBD/TODO. The Mermaid-render-can-fail risk (the reason this agent was deferred) is handled explicitly: the `<pre>` holds the raw source and a `try/catch` around `mermaid.run` leaves it visible on failure. Every step has exact code + commands + expected output.

**Type consistency:** `run_mockup(query, session_id, router, store, bus, now, timeout=...)` matches the uniform agent shape the `_AGENTS` map calls (Task 3). `Intent.kind` gains `mockup` (Task 2), consumed by `_AGENTS["mockup"]` (Task 3) and gated by `enable_mockup` (Tasks 1/3 config). Payload `{diagram, caption}` from `run_mockup._payload` (Task 1) matches the UI `ArtifactPayload.diagram/caption` (Task 4) and `MockupBody` rendering. Router gains a `mockup` route (Task 1) backing `chain_for("mockup")`. The fake stub's diagram/caption keys (Task 1) feed the default-fake demo + the smoke.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase8-mockup-agent.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
