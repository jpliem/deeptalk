from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.provider import LlmProvider


async def test_fake_complete_default_echoes_prompt():
    p = FakeLlmProvider()
    out = await p.complete("classify this")
    assert "classify this" in out


async def test_fake_complete_is_scriptable():
    p = FakeLlmProvider(completion='{"is_search": true, "query": "x"}')
    out = await p.complete("anything")
    assert out == '{"is_search": true, "query": "x"}'


def test_fake_still_satisfies_protocol_with_complete():
    assert isinstance(FakeLlmProvider(), LlmProvider)


def test_anthropic_has_complete():
    from deeptalk.llm.anthropic_provider import AnthropicProvider

    assert callable(getattr(AnthropicProvider, "complete", None))


async def test_fake_complete_returns_json_stub_for_json_prompts():
    import json
    p = FakeLlmProvider()
    out = await p.complete("Respond ONLY as JSON with pros and cons")
    data = json.loads(out)
    assert "pros" in data and "cons" in data and "steps" in data
