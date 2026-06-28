from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from deeptalk.timeline.models import TimelineEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS timeline_entry (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    topic_id     TEXT NOT NULL,
    label        TEXT NOT NULL,
    start_ts     REAL NOT NULL,
    end_ts       REAL NOT NULL,
    summary      TEXT NOT NULL DEFAULT '',
    decisions    TEXT NOT NULL DEFAULT '[]',
    action_items TEXT NOT NULL DEFAULT '[]',
    created_at   REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_timeline_session_topic
    ON timeline_entry(session_id, topic_id);
"""


class TimelineStore:
    """Persists timeline entries — one entry per topic per session.

    Topics are merged by (session_id, topic_id): if a topic re-emerges
    in a later summarization window, end_ts is extended and the summary
    / decisions / action items are replaced.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = str(Path(db_path))
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def _row_to_entry(self, row: sqlite3.Row) -> TimelineEntry:
        return TimelineEntry(
            id=row["id"],
            session_id=row["session_id"],
            topic_id=row["topic_id"],
            label=row["label"],
            start_ts=row["start_ts"],
            end_ts=row["end_ts"],
            summary=row["summary"],
            decisions=tuple(json.loads(row["decisions"])),
            action_items=tuple(json.loads(row["action_items"])),
            created_at=row["created_at"],
        )

    def upsert(self, entry: TimelineEntry) -> None:
        """Insert or update on (session_id, topic_id) conflict."""
        self._conn.execute(
            """
            INSERT INTO timeline_entry
                (id, session_id, topic_id, label, start_ts, end_ts,
                 summary, decisions, action_items, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, topic_id) DO UPDATE SET
                end_ts       = excluded.end_ts,
                summary      = excluded.summary,
                decisions    = excluded.decisions,
                action_items = excluded.action_items
            """,
            (
                entry.id,
                entry.session_id,
                entry.topic_id,
                entry.label,
                entry.start_ts,
                entry.end_ts,
                entry.summary,
                json.dumps(list(entry.decisions)),
                json.dumps(list(entry.action_items)),
                entry.created_at,
            ),
        )
        self._conn.commit()

    def get_by_topic(self, session_id: str, topic_id: str) -> TimelineEntry | None:
        row = self._conn.execute(
            "SELECT * FROM timeline_entry WHERE session_id=? AND topic_id=?",
            (session_id, topic_id),
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def all_entries(self, session_id: str) -> list[TimelineEntry]:
        rows = self._conn.execute(
            "SELECT * FROM timeline_entry WHERE session_id=? ORDER BY start_ts",
            (session_id,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def clear(self, session_id: str) -> None:
        self._conn.execute(
            "DELETE FROM timeline_entry WHERE session_id=?", (session_id,)
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
