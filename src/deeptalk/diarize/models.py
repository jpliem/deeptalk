from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiarizedSegment:
    speaker: int
    start: float
    end: float
    text: str
