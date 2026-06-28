import asyncio
import time
import os
from deeptalk.config import Config
from deeptalk.transcript.store import TranscriptStore
from deeptalk.bus import EventBus
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.llm.factory import build_router
from deeptalk.intent.factory import build_detector
from deeptalk.server.dispatch import make_fire
from deeptalk.orchestrator import Orchestrator
from deeptalk.stt.whisper import WhisperSttLive

async def main():
    # Make sure we use a clean test DB for this test to avoid clashing with other things
    db_path = "test_pipeline.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    config = Config.from_env()
    print("STT Setting:", config.stt)
    print("Search Provider:", config.search_provider)
    print("OpenRouter Model:", config.openrouter_model)
    print("Intent Detector Setting:", config.intent_detector)

    store = TranscriptStore(db_path)
    bus = EventBus()
    artifact_store = ArtifactStore(db_path)
    artifact_bus = EventBus()
    router = build_router(config)
    detector = build_detector(config, router)

    def now_fn():
        return time.time()

    fire = make_fire(
        router, artifact_store, artifact_bus, "test_session", now_fn,
        tracker=None, timeout=30.0, enable_mockup=True
    )
    orchestrator = Orchestrator(detector, fire)

    audio_path = "synthesized_meeting.wav"
    if not os.path.exists(audio_path):
        print(f"Error: {audio_path} does not exist!")
        return

    print(f"\n--- Transcribing and Orchestrating {audio_path} ---")
    stt = WhisperSttLive(session_id="test_session", audio_file_path=audio_path)
    
    async for ev in stt.stream():
        print(f"Transcript Event: {ev.text}")
        store.append(ev)
        await bus.publish(ev)
        
        # Run orchestrator handle (simulating run_orchestrator)
        if ev.is_final:
            print("Detecting intent...")
            intent = await orchestrator.handle(ev.text)
            if intent:
                print(f"Matched Intent: kind={intent.kind}, query={intent.query}, topic={intent.topic}")
            else:
                print("No intent matched or already seen.")

    print("\n--- Completed ---")
    print("\n=== Transcript Events in DB ===")
    for e in store.all_events("test_session"):
        print(f"{e.ts}: [{e.source}] {e.text}")

    print("\n=== Artifacts in DB ===")
    for a in artifact_store.all_artifacts("test_session"):
        print(f"Agent: {a.agent}, Status: {a.status}, Title: '{a.title}'")
        if a.error:
            print(f"  Error: {a.error}")
        else:
            payload_str = str(a.payload)
            print(f"  Payload: {payload_str[:300]}...")

    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    asyncio.run(main())
