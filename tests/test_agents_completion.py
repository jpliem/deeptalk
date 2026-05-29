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
