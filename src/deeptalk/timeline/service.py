from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from uuid import uuid4

log = logging.getLogger(__name__)

from deeptalk.bus import EventBus
from deeptalk.llm.ollama_provider import OllamaProvider
from deeptalk.timeline.models import TimelineEntry, TimelineEvent
from deeptalk.timeline.store import TimelineStore
from deeptalk.transcript.store import TranscriptStore

_PROMPT = """You are summarizing a meeting transcript. Extract distinct discussion topics.

EXISTING TOPICS (previous topics — reuse these topic_ids if the same topic continues):
{existing}

NEW TEXT:
{new_text}

Return a JSON object with an "entries" array. Each entry must have:
- topic_id: kebab-case id. Reuse an existing topic_id if the same topic continues, otherwise create a new one.
- label: short topic title (3-5 words)
- end_ts: timestamp as a float
- summary: 1-2 sentence summary of what was said
- decisions: array of strings (can be empty)
- action_items: array of strings (can be empty)

Rules:
- Reuse existing topic_ids for continuing topics. Create new kebab-case ids for new topics.
- Do NOT include start_ts. Do NOT use placeholder text — write real summaries.
- If the text has no meaningful meeting content, return {{"entries": []}}
- Return ONLY valid JSON, no markdown, no code fences."""


def _parse_json(raw: str) -> dict | None:
    """Extract JSON object from LLM response, even if wrapped in markdown."""
    # Try to find JSON between triple backticks
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    # Also try bare JSON
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


class TimelineService:
    """Background service that periodically summarizes transcript text,
    merges results into a persistent timeline, and publishes updates."""

    def __init__(
        self,
        store: TimelineStore,
        transcript_store: TranscriptStore,
        timeline_bus: EventBus,
        ollama: OllamaProvider,
        interval: float = 45.0,
    ) -> None:
        self._store = store
        self._transcript_store = transcript_store
        self._timeline_bus = timeline_bus
        self._ollama = ollama
        self._interval = interval
        self._last_ts: dict[str, float] = {}

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self._tick()
            except Exception:
                log.exception("timeline tick failed, will retry in %ss", self._interval)

    async def _tick(self) -> None:
        # Find all session IDs in the transcript store
        for session_id in self._transcript_store.list_sessions():
            events = self._transcript_store.all_events(session_id)
            events = [e for e in events if e.is_final]
            last_ts = self._last_ts.get(session_id, 0.0)
            new_events = [e for e in events if e.ts > last_ts]
            if not new_events:
                continue
            new_text = "\n".join(e.text for e in new_events)

            # 2. Get existing entries for context
            existing = self._store.all_entries(session_id)
            existing_json = json.dumps(
                [{"topic_id": e.topic_id, "label": e.label, "summary": e.summary,
                  "decisions": list(e.decisions), "action_items": list(e.action_items)}
                 for e in existing],
                indent=2,
            )

            # 3. Call Ollama
            prompt = _PROMPT.format(existing=existing_json, new_text=new_text)
            raw = await self._ollama.complete(prompt)
            data = _parse_json(raw)
            if not data or "entries" not in data:
                continue

            # 4. Merge results
            updated_ids: list[str] = []
            for entry_data in data["entries"]:
                topic_id = entry_data.get("topic_id", "").strip()
                if not topic_id:
                    continue
                end_ts = entry_data.get("end_ts")
                if end_ts is None:
                    end_ts = last_ts
                existing_entry = self._store.get_by_topic(session_id, topic_id)
                if existing_entry:
                    merged = TimelineEntry(
                        id=existing_entry.id,
                        session_id=session_id,
                        topic_id=topic_id,
                        label=entry_data.get("label", existing_entry.label),
                        start_ts=existing_entry.start_ts,
                        end_ts=end_ts,
                        summary=entry_data.get("summary", existing_entry.summary),
                        decisions=tuple(entry_data.get("decisions", existing_entry.decisions)),
                        action_items=tuple(entry_data.get("action_items", existing_entry.action_items)),
                        created_at=existing_entry.created_at,
                    )
                else:
                    merged = TimelineEntry(
                        id=uuid4().hex,
                        session_id=session_id,
                        topic_id=topic_id,
                        label=entry_data.get("label", topic_id),
                        start_ts=end_ts,
                        end_ts=end_ts,
                        summary=entry_data.get("summary", ""),
                        decisions=tuple(entry_data.get("decisions", [])),
                        action_items=tuple(entry_data.get("action_items", [])),
                        created_at=time.time(),
                    )
                self._store.upsert(merged)
                updated_ids.append(merged.id)

            # 5. Publish snapshot
            if updated_ids:
                snapshot = self._store.all_entries(session_id)
                event = TimelineEvent(
                    session_id=session_id,
                    entries=tuple(snapshot),
                    updated_ids=tuple(updated_ids),
                    created_at=time.time(),
                )
                await self._timeline_bus.publish(event)

            # Advance cursor only after everything succeeded (no data loss on failure)
            self._last_ts[session_id] = max(e.ts for e in new_events)
