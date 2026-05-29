from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

import uvicorn

from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.ingest import run_ingest
from deeptalk.server.app import create_app
from deeptalk.stt.factory import build_stt
from deeptalk.transcript.store import TranscriptStore


def main() -> None:
    config = Config.from_env()
    store = TranscriptStore(config.db_path)
    bus = EventBus()

    @asynccontextmanager
    async def lifespan(app):
        stt = build_stt(config)
        task = asyncio.create_task(run_ingest(stt, store, bus))
        app.state.ingest_task = task
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = create_app(store=store, bus=bus, lifespan=lifespan)
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
