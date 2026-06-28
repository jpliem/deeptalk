"""Debug: manually run timeline tick against live DB."""
import asyncio, json, sys
sys.stdout.reconfigure(encoding='utf-8')

from deeptalk.transcript.store import TranscriptStore
from deeptalk.timeline.store import TimelineStore
from deeptalk.timeline.service import TimelineService
from deeptalk.bus import EventBus
from deeptalk.llm.ollama_provider import OllamaProvider

async def test():
    store = TranscriptStore('deeptalk-demo.db')
    tl_store = TimelineStore('deeptalk-demo.db')
    tl_bus = EventBus()

    events = store.all_events('demo')
    print(f'Events: {len(events)}', flush=True)
    for e in events:
        print(f'  ts={e.ts} is_final={e.is_final} text={e.text[:60]}', flush=True)

    ollama = OllamaProvider(url='http://localhost:11434', model='llama3.2:3b')
    svc = TimelineService(
        store=tl_store,
        transcript_store=store,
        timeline_bus=tl_bus,
        ollama=ollama,
        session_id='demo',
        interval=1,
    )
    print(f'last_ts before: {svc._last_ts}', flush=True)
    await svc._tick()
    print(f'last_ts after: {svc._last_ts}', flush=True)

    entries = tl_store.all_entries('demo')
    print(f'Timeline entries: {len(entries)}', flush=True)
    for e in entries:
        print(f'  {e.label}: {e.summary[:80]}', flush=True)

asyncio.run(test())
