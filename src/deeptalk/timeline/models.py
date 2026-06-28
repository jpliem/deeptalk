from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TimelineEntry:
    """A topic segment in the meeting timeline.

    topic_id is stable across summarization cycles so that the same topic
    discussed at multiple points in the meeting can be merged (end_ts extended).
    """

    id: str
    session_id: str
    topic_id: str
    label: str
    start_ts: float
    end_ts: float
    summary: str = ""
    decisions: tuple[str, ...] = field(default_factory=tuple)
    action_items: tuple[str, ...] = field(default_factory=tuple)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["decisions"] = list(d["decisions"])
        d["action_items"] = list(d["action_items"])
        return d


@dataclass(frozen=True)
class TimelineEvent:
    """Published on timeline_bus when entries are created or updated."""

    session_id: str
    entries: tuple[TimelineEntry, ...] = field(default_factory=tuple)
    updated_ids: tuple[str, ...] = field(default_factory=tuple)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "entries": [e.to_dict() for e in self.entries],
            "updated_ids": list(self.updated_ids),
            "created_at": self.created_at,
        }
