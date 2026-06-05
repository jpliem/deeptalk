from __future__ import annotations

import asyncio
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
    timeout: float = 30.0,
    artifact_id: str | None = None,
) -> Artifact:
    """Run a web search for `query`, persist + publish the resulting Artifact."""
    art_id = artifact_id or uuid.uuid4().hex
    try:
        async with asyncio.timeout(timeout):
            providers = router.chain_for(AGENT)
            result = await run_with_fallback(providers, lambda p: p.search_answer(query))
        artifact = Artifact(
            id=art_id,
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
    except TimeoutError:
        artifact = Artifact(
            id=art_id,
            session_id=session_id,
            agent=AGENT,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=f"agent timed out after {timeout}s",
        )
    except Exception as error:  # noqa: BLE001
        cause = error.__cause__ or error
        artifact = Artifact(
            id=art_id,
            session_id=session_id,
            agent=AGENT,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=str(cause),
        )
    store.append(artifact)
    await bus.publish(artifact)
    return artifact
