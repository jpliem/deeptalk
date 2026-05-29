from __future__ import annotations

from typing import Protocol, runtime_checkable

from deeptalk.intent.models import Intent


@runtime_checkable
class IntentDetector(Protocol):
    async def detect(self, text: str) -> Intent | None:
        """Return a search Intent for `text`, or None if nothing actionable."""
        ...
