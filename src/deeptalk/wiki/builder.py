from __future__ import annotations

from deeptalk.agents.common import parse_json
from deeptalk.llm.router import ModelRouter, run_with_fallback
from deeptalk.wiki.models import Wiki

AGENT = "wiki"

_PROMPT = (
    "You are summarizing a meeting. Transcript lines:\n{transcript}\n\n"
    "Assistant findings:\n{artifacts}\n\n"
    "Produce a concise wiki. Respond ONLY as JSON: "
    '{{"topics": ["..."], "decisions": ["..."], "action_items": ["..."]}}.'
)


async def build_wiki(
    session_id: str,
    transcript_lines: list[str],
    artifact_titles: list[str],
    router: ModelRouter,
    now: float,
) -> Wiki:
    prompt = _PROMPT.format(
        transcript="\n".join(transcript_lines) or "(none)",
        artifacts="\n".join(artifact_titles) or "(none)",
    )
    data: dict = {}
    try:
        providers = router.chain_for(AGENT)
        raw = await run_with_fallback(providers, lambda p: p.complete(prompt))
        data = parse_json(raw) or {}
    except Exception:  # noqa: BLE001 - wiki is best-effort; empty on failure
        data = {}
    return Wiki(
        session_id=session_id,
        topics=data.get("topics", []),
        decisions=data.get("decisions", []),
        action_items=data.get("action_items", []),
        created_at=now,
    )
