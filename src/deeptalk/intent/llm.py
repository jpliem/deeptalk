from __future__ import annotations

import json
import re

from deeptalk.intent.models import Intent, normalize_topic
from deeptalk.llm.router import ModelRouter, run_with_fallback

_PROMPT = (
    "You classify a line from a meeting transcript. If it raises a question or a "
    "topic worth looking up, respond with JSON: "
    '{{"is_search": true, "query": "<a concise web search query>"}}. '
    'Otherwise respond {{"is_search": false, "query": ""}}. '
    "Respond with ONLY the JSON.\n\nLine: {text}"
)


def _parse(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class LlmIntentDetector:
    """Classifies transcript lines with an LLM via the router's `complete`."""

    def __init__(self, router: ModelRouter) -> None:
        self._router = router

    async def detect(self, text: str) -> Intent | None:
        prompt = _PROMPT.format(text=text)
        try:
            providers = self._router.chain_for("intent")
            raw = await run_with_fallback(providers, lambda p: p.complete(prompt))
        except Exception:  # noqa: BLE001 - detection is best-effort
            return None
        data = _parse(raw)
        if not data or not data.get("is_search"):
            return None
        query = (data.get("query") or text).strip()
        return Intent(kind="search", query=query, topic=normalize_topic(query))
