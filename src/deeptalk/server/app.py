from __future__ import annotations

import time as _time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.router import ModelRouter
from deeptalk.transcript.store import TranscriptStore


async def stream_transcript(
    send: Callable[[dict[str, Any]], Awaitable[None]],
    store: TranscriptStore,
    bus: EventBus,
    session_id: str,
) -> None:
    """Send the session backlog, then forward live bus events for that session.

    Extracted from the WebSocket handler so the backlog+live logic can be tested
    in-loop with a fake `send`, without WebSocket/cross-thread machinery.
    """
    for ev in store.all_events(session_id):
        await send(ev.to_dict())
    q = bus.subscribe()
    try:
        while True:
            ev = await q.get()
            if ev.session_id == session_id:
                await send(ev.to_dict())
    finally:
        bus.unsubscribe(q)


async def _stream_session(send, backlog, bus, session_id):
    for item in backlog:
        if item.session_id == session_id:
            await send(item.to_dict())
    q = bus.subscribe()
    try:
        while True:
            item = await q.get()
            if item.session_id == session_id:
                await send(item.to_dict())
    finally:
        bus.unsubscribe(q)


class AskRequest(BaseModel):
    session_id: str
    query: str


def create_app(
    store: TranscriptStore,
    bus: EventBus,
    lifespan: Callable[[FastAPI], Any] | None = None,
    ui_dir: str | None = None,
    artifact_store: ArtifactStore | None = None,
    artifact_bus: EventBus | None = None,
    router: ModelRouter | None = None,
    now_fn: Callable[[], float] | None = None,
) -> FastAPI:
    app = FastAPI(title="DeepTalk", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws/transcript")
    async def ws_transcript(ws: WebSocket) -> None:
        session_id = ws.query_params.get("session_id", "default")
        await ws.accept()
        try:
            await stream_transcript(ws.send_json, store, bus, session_id)
        except WebSocketDisconnect:
            pass

    if artifact_store is not None and artifact_bus is not None:

        @app.websocket("/ws/artifacts")
        async def ws_artifacts(ws: WebSocket) -> None:
            session_id = ws.query_params.get("session_id", "default")
            await ws.accept()
            try:
                await _stream_session(
                    ws.send_json,
                    artifact_store.all_artifacts(session_id),
                    artifact_bus,
                    session_id,
                )
            except WebSocketDisconnect:
                pass

    @app.post("/ask")
    async def ask(req: AskRequest) -> dict[str, str]:
        if router is None or artifact_store is None or artifact_bus is None:
            raise HTTPException(status_code=503, detail="agents not configured")
        from deeptalk.agents.search import run_search

        clock = now_fn or _time.time
        artifact = await run_search(
            req.query, req.session_id, router, artifact_store, artifact_bus, clock()
        )
        return {"id": artifact.id, "status": artifact.status}

    # Mount the built UI LAST so /health and /ws/transcript take precedence.
    if ui_dir and Path(ui_dir).is_dir():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app
