from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.cost.tracker import CostTracker
from deeptalk.gpu.lease import GpuLease
from deeptalk.ingest import run_ingest
from deeptalk.intent.factory import build_detector
from deeptalk.llm.factory import build_router
from deeptalk.orchestrator import Orchestrator, run_orchestrator
from deeptalk.server.app import create_app
from deeptalk.server.dispatch import make_fire
from deeptalk.stt.factory import build_stt
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

    @asynccontextmanager
    async def lifespan(app):
        detector = build_detector(config, router)
        fire = make_fire(
            router, artifact_store, artifact_bus, config.session_id, time.time,
            tracker=cost_tracker, timeout=config.agent_timeout,
            enable_mockup=config.enable_mockup,
        )
        orchestrator = Orchestrator(detector, fire)

        stt = None
        # Only start host-level STT if the audio source is NOT mic.
        # When audio=mic, the WebSocket /ws/audio-stream endpoint handles
        # audio ingestion per-connection; starting a second SounddeviceSource
        # here would compete for the mic and cause confusion.
        if config.audio != "mic":
            try:
                stt = build_stt(config)
            except Exception as e:
                logging.getLogger("deeptalk").warning(
                    "Could not initialize host audio source at startup: %s", e
                )

        ingest_task = None
        if stt is not None:
            ingest_task = asyncio.create_task(run_ingest(stt, store, bus))
        orch_task = asyncio.create_task(run_orchestrator(bus, orchestrator, config.session_id))
        app.state.ingest_task = ingest_task
        app.state.orch_task = orch_task
        try:
            yield
        finally:
            for task in (ingest_task, orch_task):
                if task is not None:
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
    )
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
