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
