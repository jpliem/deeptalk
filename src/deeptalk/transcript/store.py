from __future__ import annotations

import sqlite3

from deeptalk.transcript.events import TranscriptEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transcript_event (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT    NOT NULL,
    ts         REAL    NOT NULL,
    text       TEXT    NOT NULL,
    is_final   INTEGER NOT NULL,
    source     TEXT    NOT NULL,
    speaker    INTEGER,
    span_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_session ON transcript_event(session_id, seq);
"""


class TranscriptStore:
    """Append-only persistence for transcript events. The single source of truth."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(self, ev: TranscriptEvent) -> int:
        cur = self._conn.execute(
            "INSERT INTO transcript_event "
            "(session_id, ts, text, is_final, source, speaker, span_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ev.session_id, ev.ts, ev.text, int(ev.is_final), ev.source, ev.speaker, ev.span_id),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def all_events(self, session_id: str) -> list[TranscriptEvent]:
        rows = self._conn.execute(
            "SELECT session_id, ts, text, is_final, source, speaker, span_id "
            "FROM transcript_event WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [
            TranscriptEvent(
                session_id=r["session_id"],
                ts=r["ts"],
                text=r["text"],
                is_final=bool(r["is_final"]),
                source=r["source"],
                speaker=r["speaker"],
                span_id=r["span_id"],
            )
            for r in rows
        ]
