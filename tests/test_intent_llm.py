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
