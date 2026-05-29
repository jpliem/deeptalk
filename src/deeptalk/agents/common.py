from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import Callable
from typing import Any

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter, run_with_fallback


def parse_json(raw: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


async def run_completion_agent(
    *,
    agent: str,
    query: str,
    session_id: str,
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    now: float,
    prompt: str,
    build_payload: Callable[[dict[str, Any]], dict[str, Any]],
    timeout: float = 30.0,
) -> Artifact:
    """Run a JSON-output completion agent: call -> parse -> artifact -> persist/publish."""
    try:
        async with asyncio.timeout(timeout):
            providers = router.chain_for(agent)
            raw = await run_with_fallback(providers, lambda p: p.complete(prompt))
        data = parse_json(raw)
        if data is None:
            raise ValueError("could not parse model output")
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=agent,
            status="done",
            title=query,
            payload=build_payload(data),
            created_at=now,
        )
    except TimeoutError:
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=agent,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=f"agent timed out after {timeout}s",
        )
    except Exception as error:  # noqa: BLE001
        cause = error.__cause__ or error
        artifact = Artifact(
            id=uuid.uuid4().hex,
            session_id=session_id,
            agent=agent,
            status="error",
            title=query,
            payload={},
            created_at=now,
            error=str(cause),
        )
    store.append(artifact)
    await bus.publish(artifact)
    return artifact
