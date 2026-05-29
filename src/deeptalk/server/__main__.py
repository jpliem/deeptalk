from __future__ import annotations

import asyncio
import contextlib
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn

from deeptalk.agents.search import run_search
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.ingest import run_ingest
from deeptalk.intent.factory import build_detector
from deeptalk.llm.factory import build_router
from deeptalk.orchestrator import Orchestrator, run_orchestrator
from deeptalk.server.app import create_app
from deeptalk.stt.factory import build_stt
from deeptalk.transcript.store import TranscriptStore


def main() -> None:
    config = Config.from_env()
    store = TranscriptStore(config.db_path)
    bus = EventBus()
    artifact_store = ArtifactStore(config.db_path)
    artifact_bus = EventBus()
    router = build_router(config)

    @asynccontextmanager
    async def lifespan(app):
        detector = build_detector(config, router)

        async def fire(intent):
            await run_search(
                intent.query, config.session_id, router, artifact_store, artifact_bus, time.time()
            )

        orchestrator = Orchestrator(detector, fire)

        stt = build_stt(config)
        ingest_task = asyncio.create_task(run_ingest(stt, store, bus))
        orch_task = asyncio.create_task(run_orchestrator(bus, orchestrator, config.session_id))
        app.state.ingest_task = ingest_task
        app.state.orch_task = orch_task
        try:
            yield
        finally:
            for task in (ingest_task, orch_task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    ui_dist = Path(__file__).resolve().parents[3] / "ui" / "dist"
    app = create_app(
        store=store,
        bus=bus,
        lifespan=lifespan,
        ui_dir=str(ui_dist) if ui_dist.is_dir() else None,
        artifact_store=artifact_store,
        artifact_bus=artifact_bus,
        router=router,
    )
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
