# DeepTalk Phase 3A — Model Router + Search Agent (backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the agent layer's backbone: a multi-provider Model Router with a fallback chain, an Artifact data model + store + bus, a web-search agent, and a manual `POST /ask` trigger that produces a sourced answer Artifact streamed over a `/ws/artifacts` WebSocket. All Mac-testable with a fake LLM provider; the real Anthropic (Claude + web_search) provider is validated with an API key.

**Architecture:** Agents call the LLM only through `ModelRouter`, which maps an agent name to an ordered provider chain and runs the call with fallback. Providers implement a small `LlmProvider` seam (`FakeLlmProvider` for dev/tests, `AnthropicProvider` for real web search). The search agent turns a query into an `Artifact`, persists it to an append-only `ArtifactStore`, and publishes it on an artifact `EventBus`; `/ws/artifacts` streams backlog + live, mirroring the transcript channel. `POST /ask` awaits the search and returns the artifact summary.

**Tech Stack:** Python 3.12, uv, FastAPI, pytest + pytest-asyncio, `anthropic` SDK (base dep, key only needed at call time).

---

## Roadmap context

Plan 3A of Phase 3 (spec §15 phase 3). Phases 1, 2A, 2B are on `main`. Phase 3B (next) adds the ask box + artifact cards to the React UI. Auto-firing agents from the transcript is Phase 4 (intent detector + orchestrator) — Phase 3 uses a manual `/ask` trigger.

## Hardware/key-validation note

Every task is built and unit-tested on macOS with a `FakeLlmProvider`. The one component not exercised in tests is **Task 5's `AnthropicProvider`**, which needs `ANTHROPIC_API_KEY` + network — its real call is validated by running `/ask` with `DEEPTALK_SEARCH_PROVIDER=anthropic`. The Anthropic web_search tool shape is version-sensitive; the code is best-effort and flagged **VALIDATE WITH KEY**. This mirrors the NeMo adapter isolation from Phase 2A.

## File Structure (Phase 3A)

```
deeptalk/
  pyproject.toml                        # MODIFY: add `anthropic` base dep
  src/deeptalk/
    config.py                           # MODIFY: search_provider, anthropic_model
    artifacts/
      __init__.py                       # NEW
      models.py                         # NEW: Artifact, Citation
      store.py                          # NEW: ArtifactStore (SQLite)
    llm/
      __init__.py                       # NEW
      provider.py                       # NEW: LlmProvider Protocol, LlmResult
      fake.py                           # NEW: FakeLlmProvider
      router.py                         # NEW: ModelRouter, run_with_fallback
      anthropic_provider.py             # NEW: AnthropicProvider (VALIDATE WITH KEY)
      factory.py                        # NEW: build_router(config)
    agents/
      __init__.py                       # NEW
      search.py                         # NEW: run_search
    server/
      app.py                            # MODIFY: artifact deps, /ws/artifacts, /ask
      __main__.py                       # MODIFY: build artifact store/bus + router
  tests/
    test_artifacts.py                   # NEW
    test_llm_provider.py                # NEW
    test_router.py                      # NEW
    test_search_agent.py                # NEW
    test_anthropic_provider.py          # NEW
    test_ask_and_artifacts_ws.py        # NEW
```

---

### Task 1: Artifact model + ArtifactStore

**Files:**
- Create: `src/deeptalk/artifacts/__init__.py` (empty)
- Create: `src/deeptalk/artifacts/models.py`
- Create: `src/deeptalk/artifacts/store.py`
- Test: `tests/test_artifacts.py`

- [ ] **Step 1: Create the empty package init**

Run: `touch src/deeptalk/artifacts/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_artifacts.py`:

```python
import pytest

from deeptalk.artifacts.models import Artifact, Citation
from deeptalk.artifacts.store import ArtifactStore


def _artifact(session="s1", id="a1", status="done"):
    return Artifact(
        id=id,
        session_id=session,
        agent="search",
        status=status,
        title="what is X",
        payload={"answer": "X is Y", "citations": [{"title": "T", "url": "https://e.com"}]},
        created_at=123.0,
    )


def test_citation_and_artifact_to_dict():
    c = Citation(title="T", url="https://e.com")
    assert c.title == "T" and c.url == "https://e.com"
    d = _artifact().to_dict()
    assert d["agent"] == "search"
    assert d["payload"]["answer"] == "X is Y"
    assert d["latency_ms"] is None and d["error"] is None


def test_artifact_is_immutable():
    import dataclasses
    a = _artifact()
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.status = "error"


def test_store_append_and_all_in_order(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    store.append(_artifact(id="a1"))
    store.append(_artifact(id="a2"))
    arts = store.all_artifacts("s1")
    assert [a.id for a in arts] == ["a1", "a2"]
    assert all(isinstance(a, Artifact) for a in arts)


def test_store_filters_by_session(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    store.append(_artifact(session="s1", id="keep"))
    store.append(_artifact(session="s2", id="drop"))
    assert [a.id for a in store.all_artifacts("s1")] == ["keep"]


def test_store_round_trips_payload(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    store.append(_artifact())
    got = store.all_artifacts("s1")[0]
    assert got.payload == {"answer": "X is Y", "citations": [{"title": "T", "url": "https://e.com"}]}
    assert got.created_at == 123.0


def test_store_persists_across_instances(tmp_path):
    db = str(tmp_path / "a.db")
    ArtifactStore(db).append(_artifact(id="p1"))
    assert [a.id for a in ArtifactStore(db).all_artifacts("s1")] == ["p1"]
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_artifacts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.artifacts.models'`

- [ ] **Step 4: Write the models** — `src/deeptalk/artifacts/models.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Citation:
    title: str
    url: str


@dataclass(frozen=True)
class Artifact:
    """An agent's output, rendered as a card and persisted to the session."""

    id: str
    session_id: str
    agent: str
    status: str  # "done" | "error"
    title: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    latency_ms: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 5: Write the store** — `src/deeptalk/artifacts/store.py`:

```python
from __future__ import annotations

import json
import sqlite3

from deeptalk.artifacts.models import Artifact

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifact (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT    NOT NULL,
    session_id TEXT    NOT NULL,
    agent      TEXT    NOT NULL,
    status     TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    payload    TEXT    NOT NULL,
    created_at REAL    NOT NULL,
    latency_ms INTEGER,
    error      TEXT
);
CREATE INDEX IF NOT EXISTS idx_artifact_session ON artifact(session_id, seq);
"""


class ArtifactStore:
    """Append-only persistence for agent artifacts."""

    def __init__(self, db_path: str) -> None:
        # check_same_thread=False: the ASGI server may read this connection from a
        # worker thread different from the one that opened it. Safe here because
        # writes are serialized through the single event loop.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(self, art: Artifact) -> int:
        cur = self._conn.execute(
            "INSERT INTO artifact "
            "(id, session_id, agent, status, title, payload, created_at, latency_ms, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                art.id,
                art.session_id,
                art.agent,
                art.status,
                art.title,
                json.dumps(art.payload),
                art.created_at,
                art.latency_ms,
                art.error,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def all_artifacts(self, session_id: str) -> list[Artifact]:
        rows = self._conn.execute(
            "SELECT id, session_id, agent, status, title, payload, created_at, latency_ms, error "
            "FROM artifact WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [
            Artifact(
                id=r["id"],
                session_id=r["session_id"],
                agent=r["agent"],
                status=r["status"],
                title=r["title"],
                payload=json.loads(r["payload"]),
                created_at=r["created_at"],
                latency_ms=r["latency_ms"],
                error=r["error"],
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/test_artifacts.py -v`
Expected: PASS (6 passed)

- [ ] **Step 7: Commit**

```bash
git add src/deeptalk/artifacts tests/test_artifacts.py
git commit -m "feat: add Artifact model and ArtifactStore"
```

---

### Task 2: LlmProvider seam + FakeLlmProvider

**Files:**
- Create: `src/deeptalk/llm/__init__.py` (empty)
- Create: `src/deeptalk/llm/provider.py`
- Create: `src/deeptalk/llm/fake.py`
- Test: `tests/test_llm_provider.py`

- [ ] **Step 1: Create the empty package init**

Run: `touch src/deeptalk/llm/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_llm_provider.py`:

```python
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.provider import LlmProvider, LlmResult
from deeptalk.artifacts.models import Citation


async def test_fake_provider_returns_result():
    p = FakeLlmProvider()
    assert p.name == "fake"
    result = await p.search_answer("what is rust")
    assert isinstance(result, LlmResult)
    assert "what is rust" in result.text
    assert result.citations and isinstance(result.citations[0], Citation)
    assert result.model == "fake"


def test_fake_satisfies_protocol():
    assert isinstance(FakeLlmProvider(), LlmProvider)


async def test_fake_can_be_scripted():
    p = FakeLlmProvider(answer="custom answer", citations=[Citation("Doc", "https://d.com")])
    result = await p.search_answer("q")
    assert result.text == "custom answer"
    assert result.citations[0].url == "https://d.com"
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_llm_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.llm.fake'`

- [ ] **Step 4: Write the provider seam** — `src/deeptalk/llm/provider.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from deeptalk.artifacts.models import Citation


@dataclass(frozen=True)
class LlmResult:
    text: str
    citations: list[Citation]
    model: str


@runtime_checkable
class LlmProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def search_answer(self, query: str) -> LlmResult:
        """Answer a query using web search; return text + citations."""
        ...
```

- [ ] **Step 5: Write the fake** — `src/deeptalk/llm/fake.py`:

```python
from __future__ import annotations

from deeptalk.artifacts.models import Citation
from deeptalk.llm.provider import LlmResult


class FakeLlmProvider:
    """Deterministic provider for dev and tests — no network, no key."""

    def __init__(
        self,
        name: str = "fake",
        answer: str | None = None,
        citations: list[Citation] | None = None,
    ) -> None:
        self._name = name
        self._answer = answer
        self._citations = citations

    @property
    def name(self) -> str:
        return self._name

    async def search_answer(self, query: str) -> LlmResult:
        text = self._answer if self._answer is not None else f"(fake) answer for: {query}"
        citations = (
            self._citations
            if self._citations is not None
            else [Citation(title="Example", url="https://example.com")]
        )
        return LlmResult(text=text, citations=citations, model="fake")
```

- [ ] **Step 6: Run to verify it passes**

Run: `uv run pytest tests/test_llm_provider.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add src/deeptalk/llm/__init__.py src/deeptalk/llm/provider.py src/deeptalk/llm/fake.py tests/test_llm_provider.py
git commit -m "feat: add LlmProvider seam and FakeLlmProvider"
```

---

### Task 3: ModelRouter + fallback

**Files:**
- Create: `src/deeptalk/llm/router.py`
- Test: `tests/test_router.py`

- [ ] **Step 1: Write the failing test** — `tests/test_router.py`:

```python
import pytest

from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import AllProvidersFailed, ModelRouter, run_with_fallback


def _router():
    providers = {"a": FakeLlmProvider(name="a"), "b": FakeLlmProvider(name="b")}
    return ModelRouter(providers=providers, routes={"search": ["a", "b"]}, default=["b"])


def test_chain_for_known_agent():
    r = _router()
    assert [p.name for p in r.chain_for("search")] == ["a", "b"]


def test_chain_for_unknown_agent_uses_default():
    r = _router()
    assert [p.name for p in r.chain_for("other")] == ["b"]


def test_chain_skips_unregistered_provider_names():
    providers = {"a": FakeLlmProvider(name="a")}
    r = ModelRouter(providers=providers, routes={"search": ["missing", "a"]}, default=["a"])
    assert [p.name for p in r.chain_for("search")] == ["a"]


def test_chain_raises_when_no_providers_resolve():
    r = ModelRouter(providers={}, routes={"search": ["nope"]}, default=["nope"])
    with pytest.raises(AllProvidersFailed):
        r.chain_for("search")


async def test_run_with_fallback_returns_first_success():
    calls = []

    async def op(p):
        calls.append(p.name)
        return p.name

    result = await run_with_fallback([FakeLlmProvider(name="x"), FakeLlmProvider(name="y")], op)
    assert result == "x"
    assert calls == ["x"]  # second provider not tried


async def test_run_with_fallback_falls_through_on_error():
    async def op(p):
        if p.name == "x":
            raise RuntimeError("boom")
        return p.name

    result = await run_with_fallback([FakeLlmProvider(name="x"), FakeLlmProvider(name="y")], op)
    assert result == "y"


async def test_run_with_fallback_raises_when_all_fail():
    async def op(p):
        raise RuntimeError("boom")

    with pytest.raises(AllProvidersFailed):
        await run_with_fallback([FakeLlmProvider(name="x")], op)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.llm.router'`

- [ ] **Step 3: Write the router** — `src/deeptalk/llm/router.py`:

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from deeptalk.llm.provider import LlmProvider

T = TypeVar("T")


class AllProvidersFailed(Exception):
    """No provider in the chain produced a result."""


class ModelRouter:
    """Maps an agent name to an ordered provider chain."""

    def __init__(
        self,
        providers: dict[str, LlmProvider],
        routes: dict[str, list[str]],
        default: list[str],
    ) -> None:
        self._providers = providers
        self._routes = routes
        self._default = default

    def chain_for(self, agent: str) -> list[LlmProvider]:
        names = self._routes.get(agent, self._default)
        chain = [self._providers[n] for n in names if n in self._providers]
        if not chain:
            raise AllProvidersFailed(f"no providers resolve for agent {agent!r}")
        return chain


async def run_with_fallback(
    providers: list[LlmProvider],
    op: Callable[[LlmProvider], Awaitable[T]],
) -> T:
    """Try each provider in order; return the first success, else raise."""
    last_error: Exception | None = None
    for provider in providers:
        try:
            return await op(provider)
        except Exception as error:  # noqa: BLE001 - intentional: try next provider
            last_error = error
    raise AllProvidersFailed("all providers failed") from last_error
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_router.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/deeptalk/llm/router.py tests/test_router.py
git commit -m "feat: add ModelRouter with provider fallback chain"
```

---

### Task 4: Search agent

**Files:**
- Create: `src/deeptalk/agents/__init__.py` (empty)
- Create: `src/deeptalk/agents/search.py`
- Test: `tests/test_search_agent.py`

- [ ] **Step 1: Create the empty package init**

Run: `touch src/deeptalk/agents/__init__.py`

- [ ] **Step 2: Write the failing test** — `tests/test_search_agent.py`:

```python
import asyncio

from deeptalk.agents.search import run_search
from deeptalk.artifacts.models import Citation
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter


def _router(provider):
    return ModelRouter(providers={"p": provider}, routes={"search": ["p"]}, default=["p"])


async def test_run_search_produces_done_artifact(tmp_path):
    provider = FakeLlmProvider(answer="Rust is a systems language", citations=[Citation("Rust", "https://rust-lang.org")])
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_search("what is rust", "s1", _router(provider), store, bus, now=10.0)

    assert art.status == "done"
    assert art.agent == "search"
    assert art.title == "what is rust"
    assert art.payload["answer"] == "Rust is a systems language"
    assert art.payload["citations"] == [{"title": "Rust", "url": "https://rust-lang.org"}]
    assert art.created_at == 10.0


async def test_run_search_persists_and_publishes(tmp_path):
    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    q = bus.subscribe()
    await run_search("q", "s1", _router(FakeLlmProvider()), store, bus, now=1.0)

    assert len(store.all_artifacts("s1")) == 1
    published = await asyncio.wait_for(q.get(), timeout=1.0)
    assert published.agent == "search"


async def test_run_search_records_error_when_provider_fails(tmp_path):
    class BoomProvider:
        name = "boom"

        async def search_answer(self, query):
            raise RuntimeError("api down")

    store = ArtifactStore(str(tmp_path / "a.db"))
    bus = EventBus()
    art = await run_search("q", "s1", _router(BoomProvider()), store, bus, now=2.0)

    assert art.status == "error"
    assert "api down" in art.error
    assert store.all_artifacts("s1")[0].status == "error"
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_search_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.agents.search'`

- [ ] **Step 4: Write the agent** — `src/deeptalk/agents/search.py`:

```python
from __future__ import annotations

import uuid

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter, run_with_fallback

AGENT = "search"


async def run_search(
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
) -> Artifact:
    """Run a web search for `query`, persist + publish the resulting Artifact."""
    try:
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
    except Exception as error:  # noqa: BLE001 - surfaced to the user as an error card
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=AGENT,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=str(error),
        )
    store.append(artifact)
    await bus.publish(artifact)
    return artifact
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_search_agent.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/deeptalk/agents tests/test_search_agent.py
git commit -m "feat: add web search agent producing artifacts"
```

---

### Task 5: AnthropicProvider + router factory + config (VALIDATE WITH KEY)

**Files:**
- Modify: `pyproject.toml` (add `anthropic` base dep)
- Modify: `src/deeptalk/config.py` (add `search_provider`, `anthropic_model`)
- Create: `src/deeptalk/llm/anthropic_provider.py`
- Create: `src/deeptalk/llm/factory.py`
- Test: `tests/test_anthropic_provider.py`

- [ ] **Step 1: Add the anthropic dependency**

Run: `uv add anthropic` then `uv sync`. Confirm `anthropic` is in `[project].dependencies`.

- [ ] **Step 2: Write the failing test** — `tests/test_anthropic_provider.py`:

```python
from deeptalk.config import Config
from deeptalk.llm.provider import LlmProvider
from deeptalk.llm.factory import build_router
from deeptalk.llm.anthropic_provider import AnthropicProvider


def test_anthropic_provider_shape_without_calling():
    p = AnthropicProvider(model="claude-sonnet-4-6")
    assert p.name == "anthropic"
    assert isinstance(p, LlmProvider)  # satisfies the protocol (has name + search_answer)


def test_factory_builds_fake_router_by_default():
    router = build_router(Config.from_env({}))
    chain = router.chain_for("search")
    assert [p.name for p in chain] == ["fake"]


def test_factory_wires_anthropic_when_selected():
    router = build_router(Config.from_env({"DEEPTALK_SEARCH_PROVIDER": "anthropic"}))
    chain = router.chain_for("search")
    assert [p.name for p in chain] == ["anthropic"]
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_anthropic_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'deeptalk.llm.anthropic_provider'`

- [ ] **Step 4: Extend `Config`** — in `src/deeptalk/config.py`:

Add these two fields to the `Config` dataclass (after `audio_file`):
```python
    search_provider: str = "fake"  # "fake" | "anthropic"
    anthropic_model: str = "claude-sonnet-4-6"
```
And in `from_env`, add these two keys to the `cls(...)` call:
```python
            search_provider=e.get("DEEPTALK_SEARCH_PROVIDER", "fake"),
            anthropic_model=e.get("DEEPTALK_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
```

- [ ] **Step 5: Write the Anthropic provider** — `src/deeptalk/llm/anthropic_provider.py`:

```python
from __future__ import annotations

# VALIDATE WITH KEY: This provider calls the Anthropic API with the server-side
# web_search tool. It needs ANTHROPIC_API_KEY + network and is not exercised by the
# Mac test suite. The web_search tool type string and response block shape are
# version-sensitive; if parsing returns empty text/citations on first real run,
# adjust here against the current Anthropic SDK.
# Docs: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search-tool

from deeptalk.artifacts.models import Citation
from deeptalk.llm.provider import LlmResult

_WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}


class AnthropicProvider:
    """Claude with the server-side web_search tool."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "anthropic"

    async def search_answer(self, query: str) -> LlmResult:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._api_key) if self._api_key else AsyncAnthropic()
        resp = await client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": query}],
            tools=[_WEB_SEARCH_TOOL],
        )

        text_parts: list[str] = []
        citations: list[Citation] = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
                for cit in getattr(block, "citations", None) or []:
                    url = getattr(cit, "url", None)
                    title = getattr(cit, "title", None) or url
                    if url:
                        citations.append(Citation(title=title, url=url))
        return LlmResult(text="".join(text_parts), citations=citations, model=self._model)
```

- [ ] **Step 6: Write the factory** — `src/deeptalk/llm/factory.py`:

```python
from __future__ import annotations

from deeptalk.config import Config
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.provider import LlmProvider
from deeptalk.llm.router import ModelRouter


def build_router(config: Config) -> ModelRouter:
    providers: dict[str, LlmProvider] = {"fake": FakeLlmProvider()}
    chain = ["fake"]

    if config.search_provider == "anthropic":
        from deeptalk.llm.anthropic_provider import AnthropicProvider

        providers["anthropic"] = AnthropicProvider(model=config.anthropic_model)
        chain = ["anthropic"]

    return ModelRouter(providers=providers, routes={"search": chain}, default=chain)
```

- [ ] **Step 7: Run to verify it passes**

Run: `uv run pytest tests/test_anthropic_provider.py -v`
Expected: PASS (3 passed). The provider is constructed and shape-checked but never called (no key/network in tests).

- [ ] **Step 8: Full suite**

Run: `uv run pytest -q`
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock src/deeptalk/config.py src/deeptalk/llm/anthropic_provider.py src/deeptalk/llm/factory.py tests/test_anthropic_provider.py
git commit -m "feat: add AnthropicProvider, router factory, config provider selection"
```

---

### Task 6: Artifact WebSocket channel

**Files:**
- Modify: `src/deeptalk/server/app.py`
- Test: `tests/test_ask_and_artifacts_ws.py` (artifacts WS part)

- [ ] **Step 1: Write the failing test** — create `tests/test_ask_and_artifacts_ws.py`:

```python
import time

from fastapi.testclient import TestClient

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import ModelRouter
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def _deps(tmp_path):
    return {
        "store": TranscriptStore(str(tmp_path / "t.db")),
        "bus": EventBus(),
        "artifact_store": ArtifactStore(str(tmp_path / "a.db")),
        "artifact_bus": EventBus(),
        "router": ModelRouter(
            providers={"fake": FakeLlmProvider()},
            routes={"search": ["fake"]},
            default=["fake"],
        ),
    }


def _artifact(session="s1", id="a1"):
    return Artifact(
        id=id, session_id=session, agent="search", status="done",
        title="q", payload={"answer": "a", "citations": []}, created_at=time.time(),
    )


def test_artifacts_ws_sends_backlog(tmp_path):
    deps = _deps(tmp_path)
    deps["artifact_store"].append(_artifact(id="a1"))
    deps["artifact_store"].append(_artifact(id="a2"))
    app = create_app(**deps)
    client = TestClient(app)

    with client.websocket_connect("/ws/artifacts?session_id=s1") as ws:
        first = ws.receive_json()
        second = ws.receive_json()

    assert first["id"] == "a1"
    assert second["id"] == "a2"
    assert first["agent"] == "search"


def test_artifacts_ws_filters_by_session(tmp_path):
    deps = _deps(tmp_path)
    deps["artifact_store"].append(_artifact(session="s1", id="keep"))
    deps["artifact_store"].append(_artifact(session="s2", id="drop"))
    app = create_app(**deps)
    client = TestClient(app)

    with client.websocket_connect("/ws/artifacts?session_id=s1") as ws:
        msg = ws.receive_json()

    assert msg["id"] == "keep"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ask_and_artifacts_ws.py -v`
Expected: FAIL — `create_app()` does not accept `artifact_store` / `artifact_bus` / `router`.

- [ ] **Step 3: Update `src/deeptalk/server/app.py`**

Add these imports near the top (keep existing):
```python
import asyncio
import time as _time
from collections.abc import Awaitable, Callable
from typing import Any
```
(If `Awaitable`/`Callable`/`Any` are already imported from Phase 1/2, do not duplicate.)

Add this generic helper near `stream_transcript` (it generalizes the same backlog-then-live pattern for any session-scoped, `to_dict()`-able item):
```python
async def _stream_session(send, backlog, bus, session_id):
    for item in backlog:
        if item.session_id == session_id:
            await send(item.to_dict())
    q = bus.subscribe()
    try:
        while True:
            item = await q.get()
            if item.session_id == session_id:
                await send(item.to_dict())
    finally:
        bus.unsubscribe(q)
```

Change the `create_app` signature to add the new optional deps:
```python
def create_app(
    store: TranscriptStore,
    bus: EventBus,
    lifespan: Callable[[FastAPI], Any] | None = None,
    ui_dir: str | None = None,
    artifact_store: "ArtifactStore | None" = None,
    artifact_bus: EventBus | None = None,
    router: "ModelRouter | None" = None,
    now_fn: Callable[[], float] | None = None,
) -> FastAPI:
```
Add these imports at the top of the file for the type names:
```python
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.llm.router import ModelRouter
```
Inside `create_app`, after the existing `/ws/transcript` route and BEFORE the UI mount / `return app`, register the artifacts WebSocket (only when configured):
```python
    if artifact_store is not None and artifact_bus is not None:

        @app.websocket("/ws/artifacts")
        async def ws_artifacts(ws: WebSocket) -> None:
            session_id = ws.query_params.get("session_id", "default")
            await ws.accept()
            try:
                await _stream_session(
                    ws.send_json,
                    artifact_store.all_artifacts(session_id),
                    artifact_bus,
                    session_id,
                )
            except WebSocketDisconnect:
                pass
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ask_and_artifacts_ws.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Full suite (no regressions)**

Run: `uv run pytest -q`
Expected: all green (existing transcript WS + UI static tests still pass).

- [ ] **Step 6: Commit**

```bash
git add src/deeptalk/server/app.py tests/test_ask_and_artifacts_ws.py
git commit -m "feat: add /ws/artifacts channel"
```

---

### Task 7: /ask endpoint + entrypoint wiring

**Files:**
- Modify: `src/deeptalk/server/app.py` (add `POST /ask`)
- Modify: `src/deeptalk/server/__main__.py` (build artifact store/bus + router, pass to create_app)
- Test: `tests/test_ask_and_artifacts_ws.py` (add /ask tests)

- [ ] **Step 1: Add the failing /ask tests** — append to `tests/test_ask_and_artifacts_ws.py`:

```python
def test_ask_returns_done_and_persists(tmp_path):
    deps = _deps(tmp_path)
    app = create_app(**deps)
    client = TestClient(app)

    resp = client.post("/ask", json={"session_id": "s1", "query": "what is rust"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"

    arts = deps["artifact_store"].all_artifacts("s1")
    assert len(arts) == 1
    assert arts[0].title == "what is rust"
    assert "what is rust" in arts[0].payload["answer"]


def test_ask_503_when_not_configured(tmp_path):
    from deeptalk.transcript.store import TranscriptStore as TS

    app = create_app(store=TS(str(tmp_path / "t.db")), bus=EventBus())  # no router/artifacts
    client = TestClient(app)
    resp = client.post("/ask", json={"session_id": "s1", "query": "q"})
    assert resp.status_code == 503
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ask_and_artifacts_ws.py -v`
Expected: FAIL — there is no `/ask` route yet (404, not 200/503).

- [ ] **Step 3: Add the `/ask` route to `src/deeptalk/server/app.py`**

Add this import near the top:
```python
from fastapi import HTTPException
from pydantic import BaseModel
```
Add this request model at module level (top of file, after imports):
```python
class AskRequest(BaseModel):
    session_id: str
    query: str
```
Inside `create_app`, before the UI mount / `return app`, add (it awaits the search so the artifact is persisted by the time the response returns; it is also published on the artifact bus for any live `/ws/artifacts` subscriber):
```python
    @app.post("/ask")
    async def ask(req: AskRequest) -> dict[str, str]:
        if router is None or artifact_store is None or artifact_bus is None:
            raise HTTPException(status_code=503, detail="agents not configured")
        # Imported here to avoid a circular import at module load.
        from deeptalk.agents.search import run_search

        clock = now_fn or _time.time
        artifact = await run_search(
            req.query, req.session_id, router, artifact_store, artifact_bus, clock()
        )
        return {"id": artifact.id, "status": artifact.status}
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ask_and_artifacts_ws.py -v`
Expected: PASS (4 passed total in this file).

- [ ] **Step 5: Wire the entrypoint** — in `src/deeptalk/server/__main__.py`

Add imports with the others:
```python
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.llm.factory import build_router
```
In `main()`, after `bus = EventBus()`, add:
```python
    artifact_store = ArtifactStore(config.db_path)
    artifact_bus = EventBus()
    router = build_router(config)
```
Change the `create_app(...)` call to also pass the new deps:
```python
    app = create_app(
        store=store,
        bus=bus,
        lifespan=lifespan,
        ui_dir=str(ui_dist) if ui_dist.is_dir() else None,
        artifact_store=artifact_store,
        artifact_bus=artifact_bus,
        router=router,
    )
```
(Keep the existing `ui_dist = ...` line.)

- [ ] **Step 6: Full suite + smoke**

Run: `uv run pytest -q`
Expected: all green (Phase 2B's 53 + Phase 3A's new tests).

Smoke the fake-provider `/ask` path (no API key needed — default provider is `fake`):
```bash
rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-3a.log 2>&1 &
SERVER_PID=$!
sleep 6
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'content-type: application/json' \
  -d '{"session_id":"demo","query":"what is rust"}'
echo
kill $SERVER_PID 2>/dev/null
```
Expected: JSON like `{"id":"<hex>","status":"done"}`. Paste `/tmp/deeptalk-3a.log` tail on failure.

- [ ] **Step 7: Commit**

```bash
git add src/deeptalk/server/app.py src/deeptalk/server/__main__.py tests/test_ask_and_artifacts_ws.py
git commit -m "feat: add POST /ask endpoint wired to router and search agent"
```

---

## On a machine with an Anthropic key (real validation)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
DEEPTALK_SEARCH_PROVIDER=anthropic uv run python -m deeptalk.server
curl -s -X POST http://127.0.0.1:8000/ask -H 'content-type: application/json' \
  -d '{"session_id":"demo","query":"latest stable Rust version"}'
```
Expected: a real sourced answer with citations. If `answer`/`citations` come back empty, adjust the web_search tool type or response parsing in `src/deeptalk/llm/anthropic_provider.py` (the flagged validation point).

---

## Self-Review

**Spec coverage (Phase 3A):** Implements spec §7 Model Router (#7, Task 3 + factory Task 5), Agents (#8 — the search agent, Task 4), Artifact Bus + persistence (#9 — Tasks 1, 6), the §8 router fallback chain (Task 3), and the manual trigger that stands in for Phase 4's orchestrator. Intent detection/dedup (Phase 4), more agents (pros-cons/planning/mockup), and the UI cards (Phase 3B) are later — not gaps.

**Placeholder scan:** No TBD/TODO. The sole validation-deferred component is Task 5's `AnthropicProvider` (needs a key/network), explicitly flagged with a docs link and real best-effort code; its Mac tests (construct + protocol + factory wiring) are real and complete.

**Type consistency:** `Artifact`/`Citation` (Task 1) `to_dict()` is used by the artifacts WS (Task 6) and `/ask`. `LlmProvider` (`name` prop + `async search_answer(query) -> LlmResult`, Task 2) is implemented by `FakeLlmProvider` (Task 2), `AnthropicProvider` (Task 5), and the test `BoomProvider` (Task 4), and consumed by `run_with_fallback` (Task 3) and `run_search` (Task 4). `ModelRouter(providers, routes, default)` + `chain_for(agent)` are consistent across Tasks 3, 5, 6, 7. `run_search(query, session_id, router, store, bus, now)` matches between Task 4 and the `/ask` call in Task 7. `create_app(..., artifact_store, artifact_bus, router, now_fn)` is consistent between Task 6/7 changes, the tests, and the entrypoint.

**Mount/route ordering:** `/ask` and `/ws/artifacts` are registered before the UI static mount (`/`), so they are not shadowed.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase3a-router-search-agent.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
