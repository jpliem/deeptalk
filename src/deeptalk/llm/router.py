from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from deeptalk.llm.provider import LlmProvider

T = TypeVar("T")


class AllProvidersFailed(Exception):
    """No provider in the chain produced a result."""


class ModelRouter:
    """Maps an agent name to an ordered provider chain."""

    def __init__(
        self,
        providers: dict[str, LlmProvider],
        routes: dict[str, list[str]],
        default: list[str],
    ) -> None:
        self._providers = providers
        self._routes = routes
        self._default = default

    def chain_for(self, agent: str) -> list[LlmProvider]:
        names = self._routes.get(agent, self._default)
        chain = [self._providers[n] for n in names if n in self._providers]
        if not chain:
            raise AllProvidersFailed(f"no providers resolve for agent {agent!r}")
        return chain


async def run_with_fallback(
    providers: list[LlmProvider],
    op: Callable[[LlmProvider], Awaitable[T]],
) -> T:
    """Try each provider in order; return the first success, else raise."""
    last_error: Exception | None = None
    for provider in providers:
        try:
            return await op(provider)
        except Exception as error:  # noqa: BLE001 - intentional: try next provider
            last_error = error
    raise AllProvidersFailed("all providers failed") from last_error
