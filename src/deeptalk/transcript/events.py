from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TranscriptEvent:
    """A single transcript fragment. Immutable; the store is the source of truth."""

    session_id: str
    ts: float
    text: str
    is_final: bool
    source: str = "live"  # "live" | "diarized"
    speaker: int | None = None
    span_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TranscriptEvent":
        return cls(
            session_id=data["session_id"],
            ts=data["ts"],
            text=data["text"],
            is_final=data["is_final"],
            source=data.get("source", "live"),
            speaker=data.get("speaker"),
            span_id=data.get("span_id"),
        )
