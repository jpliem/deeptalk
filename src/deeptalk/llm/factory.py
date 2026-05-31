from __future__ import annotations

from deeptalk.config import Config
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.provider import LlmProvider
from deeptalk.llm.router import ModelRouter


def build_router(config: Config) -> ModelRouter:
    providers: dict[str, LlmProvider] = {"fake": FakeLlmProvider()}
    chain = ["fake"]

    if config.search_provider == "anthropic":
        from deeptalk.llm.anthropic_provider import AnthropicProvider

        providers["anthropic"] = AnthropicProvider(model=config.anthropic_model)
        chain = ["anthropic"]

    return ModelRouter(
        providers=providers,
        routes={
            "search": chain, "intent": chain, "proscons": chain,
            "planning": chain, "wiki": chain, "mockup": chain,
        },
        default=chain,
    )
