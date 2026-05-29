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
