from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from deeptalk.bus import EventBus
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


def create_app(
    store: TranscriptStore,
    bus: EventBus,
    lifespan: Callable[[FastAPI], Any] | None = None,
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

    return app
