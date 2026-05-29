from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from deeptalk.artifacts.models import Citation


@dataclass(frozen=True)
class LlmResult:
    text: str
    citations: list[Citation]
    model: str


@runtime_checkable
class LlmProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def search_answer(self, query: str) -> LlmResult:
        """Answer a query using web search; return text + citations."""
        ...
