from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from deeptalk.agents.planning import run_planning
from deeptalk.agents.proscons import run_proscons
from deeptalk.agents.search import run_search
from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.cost.tracker import CostTracker
from deeptalk.intent.models import Intent
from deeptalk.llm.router import ModelRouter

_AGENTS = {
    "search": run_search,
    "debate": run_proscons,
    "planning": run_planning,
}


def make_fire(
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    session_id: str,
    now: Callable[[], float],
    tracker: CostTracker | None = None,
    timeout: float = 30.0,
) -> Callable[[Intent], Awaitable[None]]:
    """Build the orchestrator's `fire` callback that routes a kind to its agent,
    enforcing the per-session cost cap and per-agent timeout."""

    async def fire(intent: Intent) -> None:
        runner = _AGENTS.get(intent.kind)
        if runner is None:
            return
        if tracker is not None and not tracker.allow(session_id):
            budget = Artifact(
                id=uuid.uuid4().hex,
                session_id=session_id,
                agent="system",
                status="error",
                title=intent.query,
                payload={},
                created_at=now(),
                error="session agent-call budget exceeded",
            )
            store.append(budget)
            await bus.publish(budget)
            return
        await runner(intent.query, session_id, router, store, bus, now(), timeout=timeout)

    return fire
