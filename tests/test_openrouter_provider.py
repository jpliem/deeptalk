from deeptalk.config import Config
from deeptalk.llm.provider import LlmProvider
from deeptalk.llm.factory import build_router
from deeptalk.llm.openrouter_provider import OpenRouterProvider


def test_openrouter_provider_shape_without_calling():
    p = OpenRouterProvider(model="google/gemini-2.5-flash")
    assert p.name == "openrouter"
    assert isinstance(p, LlmProvider)


def test_factory_wires_openrouter_when_selected():
    router = build_router(Config.from_env({"DEEPTALK_SEARCH_PROVIDER": "openrouter"}))
    chain = router.chain_for("search")
    assert [p.name for p in chain] == ["openrouter"]
