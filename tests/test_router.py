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
    assert calls == ["x"]


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
