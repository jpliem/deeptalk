from __future__ import annotations

import json
import re

from deeptalk.intent.models import Intent, normalize_topic
from deeptalk.llm.router import ModelRouter, run_with_fallback

_VALID_KINDS = ("search", "debate", "planning", "mockup")

_PROMPT = (
    "Classify a line from a meeting transcript into one kind:\n"
    "- search: a question or fact worth looking up\n"
    "- debate: a decision between options / pros and cons\n"
    "- planning: a goal that needs a plan or steps\n"
    "- mockup: a UI or system design worth sketching as a diagram\n"
    "- none: anything else\n"
    'Respond ONLY as JSON: {{"kind": "search|debate|planning|mockup|none", '
    '"query": "<concise topic/query>"}}.\n\nLine: {text}'
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
    """Classifies transcript lines into a kind with an LLM via `complete`."""

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
        if not data:
            return None
        kind = data.get("kind")
        if kind not in _VALID_KINDS:
            return None
        query = (data.get("query") or text).strip()
        return Intent(kind=kind, query=query, topic=normalize_topic(query))
