from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Citation:
    title: str
    url: str


@dataclass(frozen=True)
class Artifact:
    """An agent's output, rendered as a card and persisted to the session."""

    id: str
    session_id: str
    agent: str
    status: str  # "done" | "error"
    title: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    latency_ms: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
