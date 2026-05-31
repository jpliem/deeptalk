from __future__ import annotations

from deeptalk.intent.models import Intent, normalize_topic

_MOCKUP_SIGNALS = (
    "mockup", "wireframe", "diagram", "sketch", "flowchart",
    "draw the", "draw a", "what should the ui", "screen layout",
    "lay out the screen", "ui look like",
)
_PLANNING_SIGNALS = (
    "how do we build", "how do we implement", "what are the steps", "what's the plan",
    "lay out", "outline the", "break down", "roadmap", "let's plan", "lets plan",
    "plan the", "plan for", "plan a", "step by step",
)
_DEBATE_SIGNALS = (
    " or ", " vs ", " versus ", "pros and cons", "trade-off", "tradeoff",
    "which is better", "better option", "compare",
)
_QUESTION_LEADS = (
    "what", "what's", "how", "why", "when", "where", "who", "which",
    "should we", "should i", "is there", "are there", "can we", "can i",
    "do we", "does", "could we", "is ", "are ",
)


def _classify(low: str, line: str) -> str | None:
    padded = f" {low} "
    if any(sig in low for sig in _MOCKUP_SIGNALS):
        return "mockup"
    if any(sig in low for sig in _PLANNING_SIGNALS):
        return "planning"
    if any(sig in padded for sig in _DEBATE_SIGNALS):
        return "debate"
    if line.endswith("?") or any(low.startswith(lead) for lead in _QUESTION_LEADS):
        return "search"
    return None


class HeuristicIntentDetector:
    """Rule-based classifier: planning, debate, or search (or nothing)."""

    async def detect(self, text: str) -> Intent | None:
        line = text.strip()
        if not line:
            return None
        kind = _classify(line.lower(), line)
        if kind is None:
            return None
        return Intent(kind=kind, query=line, topic=normalize_topic(line))
