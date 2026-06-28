from __future__ import annotations

from typing import Any

from deeptalk.agents.common import run_completion_agent
from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter

AGENT = "mockup"

_PROMPT = (
    "The team is discussing a UI or system design. Capture it as a Mermaid diagram "
    "(use 'graph TD' or 'flowchart' syntax). "
    'Respond ONLY as JSON: {{"diagram": "<mermaid source>", "caption": "<one line>"}}.'
    "\n\nDiscussion: {query}"
)


def _payload(data: dict[str, Any]) -> dict[str, Any]:
    return {"diagram": data.get("diagram", ""), "caption": data.get("caption", "")}


async def run_mockup(
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
    timeout: float = 30.0,
    artifact_id: str | None = None,
    **kwargs: object,
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
        timeout=timeout,
        artifact_id=artifact_id,
    )
