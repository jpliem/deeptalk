from __future__ import annotations

import json
import sqlite3

from deeptalk.wiki.models import Wiki

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wiki (
    session_id   TEXT PRIMARY KEY,
    topics       TEXT NOT NULL,
    decisions    TEXT NOT NULL,
    action_items TEXT NOT NULL,
    created_at   REAL NOT NULL
);
"""


class WikiStore:
    """One wiki per session; save() upserts."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save(self, wiki: Wiki) -> None:
        self._conn.execute(
            "INSERT INTO wiki (session_id, topics, decisions, action_items, created_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET "
            "topics=excluded.topics, decisions=excluded.decisions, "
            "action_items=excluded.action_items, created_at=excluded.created_at",
            (
                wiki.session_id,
                json.dumps(wiki.topics),
                json.dumps(wiki.decisions),
                json.dumps(wiki.action_items),
                wiki.created_at,
            ),
        )
        self._conn.commit()

    def get(self, session_id: str) -> Wiki | None:
        row = self._conn.execute(
            "SELECT session_id, topics, decisions, action_items, created_at "
            "FROM wiki WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return Wiki(
            session_id=row["session_id"],
            topics=json.loads(row["topics"]),
            decisions=json.loads(row["decisions"]),
            action_items=json.loads(row["action_items"]),
            created_at=row["created_at"],
        )

    def close(self) -> None:
        self._conn.close()
