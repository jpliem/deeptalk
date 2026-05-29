from __future__ import annotations

from typing import Any

from deeptalk.agents.common import run_completion_agent
from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter

AGENT = "planning"

_PROMPT = (
    "Break the goal into a concrete, ordered plan. "
    'Respond ONLY as JSON: {{"steps": ["step one", "step two", "..."]}}.\n\nGoal: {query}'
)


def _payload(data: dict[str, Any]) -> dict[str, Any]:
    return {"steps": data.get("steps", [])}


async def run_planning(
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
