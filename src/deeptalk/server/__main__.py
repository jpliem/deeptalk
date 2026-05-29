from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import uvicorn

from deeptalk.bus import EventBus
from deeptalk.ingest import run_ingest
from deeptalk.server.app import create_app
from deeptalk.stt.fake import FakeSttLive
from deeptalk.transcript.store import TranscriptStore

SESSION_ID = "demo"
FIXTURE = str(Path(__file__).resolve().parents[3] / "fixtures" / "sample_meeting.jsonl")


def main() -> None:
    store = TranscriptStore("deeptalk-demo.db")
    bus = EventBus()
    app = create_app(store=store, bus=bus)

    @app.on_event("startup")
    async def _start_ingest() -> None:
        stt = FakeSttLive(session_id=SESSION_ID, fixture_path=FIXTURE, realtime=True)
        app.state.ingest_task = asyncio.create_task(run_ingest(stt, store, bus))

    @app.on_event("shutdown")
    async def _stop_ingest() -> None:
        task = getattr(app.state, "ingest_task", None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
