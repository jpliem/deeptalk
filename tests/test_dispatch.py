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


from deeptalk.cost.tracker import CostTracker


async def test_budget_cap_emits_system_artifact(tmp_path):
    store, bus, router = _ctx(tmp_path)
    tracker = CostTracker(max_calls=1)
    fire = make_fire(router, store, bus, "s1", now=lambda: 1.0, tracker=tracker)

    from deeptalk.intent.models import Intent

    await fire(Intent(kind="search", query="q1", topic="t1"))
    await fire(Intent(kind="search", query="q2", topic="t2"))

    arts = store.all_artifacts("s1")
    agents = [a.agent for a in arts]
    assert "search" in agents
    assert "system" in agents
    budget = [a for a in arts if a.agent == "system"][0]
    assert budget.status == "error"
    assert "budget" in budget.error.lower()
