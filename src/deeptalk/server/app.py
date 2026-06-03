from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time as _time
from collections.abc import Awaitable, Callable
from pathlib import Path as _Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from deeptalk.artifacts.store import ArtifactStore
from deeptalk.audio.decode import decode_to_wav
from deeptalk.audio.file_source import FileAudioSource
from deeptalk.bus import EventBus
from deeptalk.config import Config
from deeptalk.diarize.base import Diarizer
from deeptalk.gpu.lease import GpuLease
from deeptalk.llm.router import ModelRouter
from deeptalk.stt.factory import build_stt
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore
from deeptalk.wiki.store import WikiStore


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


class FinalizeRequest(BaseModel):
    session_id: str


def create_app(
    store: TranscriptStore,
    bus: EventBus,
    lifespan: Callable[[FastAPI], Any] | None = None,
    ui_dir: str | None = None,
    artifact_store: ArtifactStore | None = None,
    artifact_bus: EventBus | None = None,
    router: ModelRouter | None = None,
    now_fn: Callable[[], float] | None = None,
    wiki_store: "WikiStore | None" = None,
    diarizer: "Diarizer | None" = None,
    recording_path: str | None = None,
    gpu_lease: "GpuLease | None" = None,
    config: Config | None = None,
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

    if wiki_store is not None and router is not None and artifact_store is not None:

        @app.post("/finalize")
        async def finalize(req: FinalizeRequest) -> dict[str, str]:
            from deeptalk.wiki.builder import build_wiki

            clock = now_fn or _time.time
            lines = [e.text for e in store.all_events(req.session_id) if e.is_final]
            titles = [a.title for a in artifact_store.all_artifacts(req.session_id)]
            wiki = await build_wiki(req.session_id, lines, titles, router, clock())
            wiki_store.save(wiki)

            if diarizer is not None and recording_path and _Path(recording_path).is_file():
                if gpu_lease is not None:
                    async with gpu_lease.hold():
                        segments = await diarizer.diarize(recording_path)
                else:
                    segments = await diarizer.diarize(recording_path)
                for seg in segments:
                    store.append(
                        TranscriptEvent(
                            session_id=req.session_id,
                            ts=seg.start,
                            text=seg.text,
                            is_final=True,
                            source="diarized",
                            speaker=seg.speaker,
                        )
                    )
            return {"status": "ok"}

        @app.get("/wiki")
        async def get_wiki(session_id: str = "default") -> dict:
            wiki = wiki_store.get(session_id)
            if wiki is None:
                raise HTTPException(status_code=404, detail="no wiki for session")
            return wiki.to_dict()

        @app.post("/clear")
        async def clear_session(session_id: str = "default") -> dict[str, str]:
            store.clear(session_id)
            if artifact_store:
                artifact_store.clear(session_id)
            if wiki_store:
                wiki_store.clear(session_id)
            return {"status": "ok"}

    @app.post("/upload")
    async def upload(file: UploadFile = File(...), session_id: str = "default") -> dict[str, int]:
        if config is None:
            raise HTTPException(status_code=503, detail="audio config not available")
        suffix = _Path(file.filename or "audio").suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            src = tmp.name
        wav = ""
        try:
            wav = await asyncio.to_thread(decode_to_wav, src)
            
            # Select STT engine
            import sys
            is_pytest = "pytest" in sys.modules

            if config.stt == "fake" and not is_pytest:
                from deeptalk.stt.whisper import WhisperSttLive
                stt = WhisperSttLive(session_id=session_id, audio_file_path=wav)
            else:
                stt = await asyncio.to_thread(
                    build_stt, config, FileAudioSource(wav), False
                )

            count = 0
            async for ev in stt.stream():
                ev_with_correct_session = TranscriptEvent(
                    session_id=session_id,
                    ts=ev.ts,
                    text=ev.text,
                    is_final=ev.is_final,
                    source=ev.source,
                    speaker=ev.speaker,
                    span_id=ev.span_id,
                )
                store.append(ev_with_correct_session)
                await bus.publish(ev_with_correct_session)
                count += 1

            # Fallback if Whisper transcribed nothing (only in tests)
            if count == 0 and config.stt == "fake" and is_pytest:
                from deeptalk.stt.fake import FakeSttLive
                fake_stt = FakeSttLive(session_id=session_id, fixture_path=config.fixture_path, realtime=False)
                async for ev in fake_stt.stream():
                    store.append(ev)
                    await bus.publish(ev)
                    count += 1

            return {"events": count}
        finally:
            for path in {src, wav}:
                if path:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

    # Mount the built UI LAST so /health and /ws/transcript take precedence.
    if ui_dir and _Path(ui_dir).is_dir():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app
