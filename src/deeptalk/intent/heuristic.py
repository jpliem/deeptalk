from __future__ import annotations

from deeptalk.intent.models import Intent, normalize_topic

_QUESTION_LEADS = (
    "what", "what's", "how", "why", "when", "where", "who", "which",
    "should we", "should i", "is there", "are there", "can we", "can i",
    "do we", "does", "could we",
)


class HeuristicIntentDetector:
    """Rule-based: a line is a search if it is phrased as a question."""

    async def detect(self, text: str) -> Intent | None:
        line = text.strip()
        if not line:
            return None
        low = line.lower()
        is_question = line.endswith("?") or any(low.startswith(lead) for lead in _QUESTION_LEADS)
        if not is_question:
            return None
        return Intent(kind="search", query=line, topic=normalize_topic(line))
