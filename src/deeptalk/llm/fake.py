from __future__ import annotations

from deeptalk.artifacts.models import Citation
from deeptalk.llm.provider import LlmResult


class FakeLlmProvider:
    """Deterministic provider for dev and tests — no network, no key."""

    def __init__(
        self,
        name: str = "fake",
        answer: str | None = None,
        citations: list[Citation] | None = None,
    ) -> None:
        self._name = name
        self._answer = answer
        self._citations = citations

    @property
    def name(self) -> str:
        return self._name

    async def search_answer(self, query: str) -> LlmResult:
        text = self._answer if self._answer is not None else f"(fake) answer for: {query}"
        citations = (
            self._citations
            if self._citations is not None
            else [Citation(title="Example", url="https://example.com")]
        )
        return LlmResult(text=text, citations=citations, model="fake")
