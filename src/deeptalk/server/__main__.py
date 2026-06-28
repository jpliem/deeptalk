from __future__ import annotations

import asyncio
import contextlib
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn

from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.cost.tracker import CostTracker
from deeptalk.gpu.lease import GpuLease
from deeptalk.ingest import run_ingest
from deeptalk.intent.factory import build_detector
from deeptalk.llm.factory import build_router
from deeptalk.llm.ollama_provider import OllamaProvider
from deeptalk.orchestrator import Orchestrator, run_orchestrator
from deeptalk.server.app import create_app
from deeptalk.server.dispatch import make_fire
from deeptalk.stt.factory import build_stt
from deeptalk.timeline.store import TimelineStore
from deeptalk.timeline.service import TimelineService
from deeptalk.transcript.store import TranscriptStore
from deeptalk.wiki.store import WikiStore


def main() -> None:
    config = Config.from_env()
    store = TranscriptStore(config.db_path)
    bus = EventBus()
    artifact_store = ArtifactStore(config.db_path)
    artifact_bus = EventBus()
    router = build_router(config)
    wiki_store = WikiStore(config.db_path)
    diarizer = None
    if config.diarize == "vibevoice":
        from deeptalk.diarize.vibevoice import VibeVoiceDiarizer

        diarizer = VibeVoiceDiarizer()

    cost_tracker = CostTracker(config.max_agent_calls)
    gpu_lease = GpuLease()

    # Timeline (rolling summarization)
    timeline_store = TimelineStore(config.db_path)
    timeline_bus = EventBus()

    @asynccontextmanager
    async def lifespan(app):
        detector = build_detector(config, router)
        fire = make_fire(
            router, artifact_store, artifact_bus, config.session_id, time.time,
            tracker=cost_tracker, timeout=config.agent_timeout,
            enable_mockup=config.enable_mockup,
        )
        orchestrator = Orchestrator(detector, fire)

        stt = build_stt(config)
        ingest_task = asyncio.create_task(run_ingest(stt, store, bus))
        orch_task = asyncio.create_task(run_orchestrator(bus, orchestrator, config.session_id))

        # Start timeline service (if interval > 0)
        timeline_task: asyncio.Task | None = None
        if config.timeline_interval > 0:
            ollama = OllamaProvider(url=config.ollama_url, model=config.ollama_model)
            svc = TimelineService(
                store=timeline_store,
                transcript_store=store,
                timeline_bus=timeline_bus,
                ollama=ollama,
                interval=config.timeline_interval,
            )
            timeline_task = asyncio.create_task(svc.run())

        app.state.ingest_task = ingest_task
        app.state.orch_task = orch_task
        app.state.timeline_task = timeline_task
        try:
            yield
        finally:
            for task in (ingest_task, orch_task, timeline_task):
                if task:
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
        wiki_store=wiki_store,
        diarizer=diarizer,
        recording_path=config.recording_path,
        gpu_lease=gpu_lease,
        config=config,
        timeline_store=timeline_store,
        timeline_bus=timeline_bus,
    )
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
