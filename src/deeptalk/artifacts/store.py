from __future__ import annotations

import json
import sqlite3

from deeptalk.artifacts.models import Artifact

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifact (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    id         TEXT    NOT NULL,
    session_id TEXT    NOT NULL,
    agent      TEXT    NOT NULL,
    status     TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    payload    TEXT    NOT NULL,
    created_at REAL    NOT NULL,
    latency_ms INTEGER,
    error      TEXT
);
CREATE INDEX IF NOT EXISTS idx_artifact_session ON artifact(session_id, seq);
"""


class ArtifactStore:
    """Append-only persistence for agent artifacts."""

    def __init__(self, db_path: str) -> None:
        # check_same_thread=False: the ASGI server may read this connection from a
        # worker thread different from the one that opened it. Safe here because
        # writes are serialized through the single event loop.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(self, art: Artifact) -> int:
        exists = self._conn.execute(
            "SELECT seq FROM artifact WHERE session_id = ? AND id = ?",
            (art.session_id, art.id),
        ).fetchone()
        if exists:
            self._conn.execute(
                "UPDATE artifact SET status = ?, payload = ?, latency_ms = ?, error = ? "
                "WHERE session_id = ? AND id = ?",
                (
                    art.status,
                    json.dumps(art.payload),
                    art.latency_ms,
                    art.error,
                    art.session_id,
                    art.id,
                ),
            )
            self._conn.commit()
            return int(exists["seq"])
        else:
            cur = self._conn.execute(
                "INSERT INTO artifact "
                "(id, session_id, agent, status, title, payload, created_at, latency_ms, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    art.id,
                    art.session_id,
                    art.agent,
                    art.status,
                    art.title,
                    json.dumps(art.payload),
                    art.created_at,
                    art.latency_ms,
                    art.error,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def all_artifacts(self, session_id: str) -> list[Artifact]:
        rows = self._conn.execute(
            "SELECT id, session_id, agent, status, title, payload, created_at, latency_ms, error "
            "FROM artifact WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        return [
            Artifact(
                id=r["id"],
                session_id=r["session_id"],
                agent=r["agent"],
                status=r["status"],
                title=r["title"],
                payload=json.loads(r["payload"]),
                created_at=r["created_at"],
                latency_ms=r["latency_ms"],
                error=r["error"],
            )
            for r in rows
        ]

    def clear(self, session_id: str) -> None:
        self._conn.execute("DELETE FROM artifact WHERE session_id = ?", (session_id,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
