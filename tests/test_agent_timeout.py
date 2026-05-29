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
