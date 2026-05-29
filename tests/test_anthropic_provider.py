from deeptalk.config import Config
from deeptalk.llm.provider import LlmProvider
from deeptalk.llm.factory import build_router
from deeptalk.llm.anthropic_provider import AnthropicProvider


def test_anthropic_provider_shape_without_calling():
    p = AnthropicProvider(model="claude-sonnet-4-6")
    assert p.name == "anthropic"
    assert isinstance(p, LlmProvider)


def test_factory_builds_fake_router_by_default():
    router = build_router(Config.from_env({}))
    chain = router.chain_for("search")
    assert [p.name for p in chain] == ["fake"]


def test_factory_wires_anthropic_when_selected():
    router = build_router(Config.from_env({"DEEPTALK_SEARCH_PROVIDER": "anthropic"}))
    chain = router.chain_for("search")
    assert [p.name for p in chain] == ["anthropic"]
