from __future__ import annotations

from collections.abc import Awaitable, Callable

from deeptalk.agents.planning import run_planning
from deeptalk.agents.proscons import run_proscons
from deeptalk.agents.search import run_search
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
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
) -> Callable[[Intent], Awaitable[None]]:
    """Build the orchestrator's `fire` callback that routes a kind to its agent."""

    async def fire(intent: Intent) -> None:
        runner = _AGENTS.get(intent.kind)
        if runner is None:
            return
        await runner(intent.query, session_id, router, store, bus, now())

    return fire
