from __future__ import annotations

from typing import Any

from deeptalk.agents.common import run_completion_agent
from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter

AGENT = "proscons"

_PROMPT = (
    "A team is weighing a decision. Give a balanced analysis. "
    'Respond ONLY as JSON: {{"pros": ["..."], "cons": ["..."], '
    '"recommendation": "..."}}.\n\nDecision: {query}'
)


def _payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "pros": data.get("pros", []),
        "cons": data.get("cons", []),
        "recommendation": data.get("recommendation", ""),
    }


async def run_proscons(
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
) -> Artifact:
    return await run_completion_agent(
        agent=AGENT,
        query=query,
        session_id=session_id,
        router=router,
        store=store,
        bus=bus,
        now=now,
        prompt=_PROMPT.format(query=query),
        build_payload=_payload,
    )
