from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from deeptalk.agents.mockup import run_mockup
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
    "mockup": run_mockup,
}


def make_fire(
    router: ModelRouter,
    store: ArtifactStore,
    bus: EventBus,
    session_id: str,
    now: Callable[[], float],
    tracker: CostTracker | None = None,
    timeout: float = 30.0,
    enable_mockup: bool = True,
) -> Callable[[Intent], Awaitable[None]]:
    """Build the orchestrator's `fire` callback that routes a kind to its agent,
    enforcing the per-session cost cap and per-agent timeout."""

    async def fire(intent: Intent) -> None:
        if intent.kind == "mockup" and not enable_mockup:
            return
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

        art_id = uuid.uuid4().hex
        agent_name = "proscons" if intent.kind == "debate" else intent.kind
        pending = Artifact(
            id=art_id,
            session_id=session_id,
            agent=agent_name,
            status="pending",
            title=intent.query,
            payload={},
            created_at=now(),
        )
        store.append(pending)
        await bus.publish(pending)

        await runner(intent.query, session_id, router, store, bus, now(), timeout=timeout, artifact_id=art_id)

    return fire
