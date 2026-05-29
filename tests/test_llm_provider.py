from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.provider import LlmProvider, LlmResult
from deeptalk.artifacts.models import Citation


async def test_fake_provider_returns_result():
    p = FakeLlmProvider()
    assert p.name == "fake"
    result = await p.search_answer("what is rust")
    assert isinstance(result, LlmResult)
    assert "what is rust" in result.text
    assert result.citations and isinstance(result.citations[0], Citation)
    assert result.model == "fake"


def test_fake_satisfies_protocol():
    assert isinstance(FakeLlmProvider(), LlmProvider)


async def test_fake_can_be_scripted():
    p = FakeLlmProvider(answer="custom answer", citations=[Citation("Doc", "https://d.com")])
    result = await p.search_answer("q")
    assert result.text == "custom answer"
    assert result.citations[0].url == "https://d.com"
