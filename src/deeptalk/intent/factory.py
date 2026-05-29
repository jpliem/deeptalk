from __future__ import annotations

from deeptalk.config import Config
from deeptalk.intent.base import IntentDetector
from deeptalk.llm.router import ModelRouter


def build_detector(config: Config, router: ModelRouter) -> IntentDetector:
    if config.intent_detector == "llm":
        from deeptalk.intent.llm import LlmIntentDetector

        return LlmIntentDetector(router)
    from deeptalk.intent.heuristic import HeuristicIntentDetector

    return HeuristicIntentDetector()
