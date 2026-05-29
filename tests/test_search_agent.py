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
