from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from deeptalk.bus import EventBus
from deeptalk.transcript.store import TranscriptStore


def create_app(store: TranscriptStore, bus: EventBus) -> FastAPI:
    app = FastAPI(title="DeepTalk")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws/transcript")
    async def ws_transcript(ws: WebSocket) -> None:
        session_id = ws.query_params.get("session_id", "default")
        await ws.accept()
        # 1. backlog
        for ev in store.all_events(session_id):
            await ws.send_json(ev.to_dict())
        # 2. live
        q = bus.subscribe()
        try:
            while True:
                ev = await q.get()
                if ev.session_id == session_id:
                    await ws.send_json(ev.to_dict())
        except WebSocketDisconnect:
            pass
        finally:
            bus.unsubscribe(q)

    return app
