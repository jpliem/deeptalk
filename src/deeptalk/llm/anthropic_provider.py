from __future__ import annotations

# VALIDATE WITH KEY: This provider calls the Anthropic API with the server-side
# web_search tool. It needs ANTHROPIC_API_KEY + network and is not exercised by the
# Mac test suite. The web_search tool type string and response block shape are
# version-sensitive; if parsing returns empty text/citations on first real run,
# adjust here against the current Anthropic SDK.
# Docs: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search-tool

from deeptalk.artifacts.models import Citation
from deeptalk.llm.provider import LlmResult

_WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}


class AnthropicProvider:
    """Claude with the server-side web_search tool."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key

    @property
    def name(self) -> str:
        return "anthropic"

    async def search_answer(self, query: str) -> LlmResult:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._api_key) if self._api_key else AsyncAnthropic()
        resp = await client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": query}],
            tools=[_WEB_SEARCH_TOOL],
        )

        text_parts: list[str] = []
        citations: list[Citation] = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
                for cit in getattr(block, "citations", None) or []:
                    url = getattr(cit, "url", None)
                    title = getattr(cit, "title", None) or url
                    if url:
                        citations.append(Citation(title=title, url=url))
        return LlmResult(text="".join(text_parts), citations=citations, model=self._model)
