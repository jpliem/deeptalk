from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    kind: str  # "search"
    query: str
    topic: str  # normalized dedup key


def normalize_topic(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — a dedup key."""
    cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()
