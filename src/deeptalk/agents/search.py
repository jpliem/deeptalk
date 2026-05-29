from __future__ import annotations

import uuid

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter, run_with_fallback

AGENT = "search"


async def run_search(
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
) -> Artifact:
    """Run a web search for `query`, persist + publish the resulting Artifact."""
    try:
        providers = router.chain_for(AGENT)
        result = await run_with_fallback(providers, lambda p: p.search_answer(query))
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=AGENT,
            status="done",
            title=query,
            payload={
                "answer": result.text,
                "citations": [{"title": c.title, "url": c.url} for c in result.citations],
                "model": result.model,
            },
            created_at=now,
        )
    except Exception as error:  # noqa: BLE001 - surfaced to the user as an error card
        # Unwrap AllProvidersFailed so the user sees the root cause message.
        root = error.__cause__ if error.__cause__ is not None else error
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=AGENT,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=str(root),
        )
    store.append(artifact)
    await bus.publish(artifact)
    return artifact
