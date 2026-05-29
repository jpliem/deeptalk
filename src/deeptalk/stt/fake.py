from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from deeptalk.stt.base import SttLive
from deeptalk.transcript.events import TranscriptEvent


class FakeSttLive(SttLive):
    """Replays transcript lines from a JSONL fixture. Used for dev/tests without CUDA."""

    def __init__(self, session_id: str, fixture_path: str, realtime: bool = False) -> None:
        self._session_id = session_id
        self._fixture_path = fixture_path
        self._realtime = realtime

    async def stream(self) -> AsyncIterator[TranscriptEvent]:
        prev_ts = 0.0
        with open(self._fixture_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if self._realtime:
                    delay = max(0.0, row["ts"] - prev_ts)
                    await asyncio.sleep(delay)
                    prev_ts = row["ts"]
                yield TranscriptEvent(
                    session_id=self._session_id,
                    ts=row["ts"],
                    text=row["text"],
                    is_final=row["is_final"],
                    source=row.get("source", "live"),
                    speaker=row.get("speaker"),
                    span_id=row.get("span_id"),
                )
