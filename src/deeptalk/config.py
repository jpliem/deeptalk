from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_FIXTURE = str(
    Path(__file__).resolve().parents[2] / "fixtures" / "sample_meeting.jsonl"
)


@dataclass(frozen=True)
class Config:
    """Runtime configuration, sourced from environment variables."""

    stt: str = "fake"  # "fake" | "nemotron" | "qwen"
    whisper_model: str = "base"  # faster-whisper size: tiny|base|small|medium|large-v3
    audio: str = "file"  # "file" | "mic"
    session_id: str = "demo"
    db_path: str = "deeptalk-demo.db"
    fixture_path: str = _DEFAULT_FIXTURE
    audio_file: str | None = None
    qwen_asr_url: str = "http://127.0.0.1:8010/v1/audio/transcriptions"
    qwen_asr_model: str = "Qwen/Qwen3-ASR-0.6B"
    qwen_asr_chunk_ms: int = 2000
    search_provider: str = "fake"  # "fake" | "anthropic" | "openrouter"
    anthropic_model: str = "claude-sonnet-4-6"
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_api_key: str | None = None
    intent_detector: str = "heuristic"  # "heuristic" | "llm"
    diarize: str = "off"  # "off" | "vibevoice"
    recording_path: str | None = None
    max_agent_calls: int = 50  # per-session cap; -1 = unlimited
    agent_timeout: float = 30.0
    enable_mockup: bool = True
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        if env is None:
            dotenv_path = Path(__file__).resolve().parents[2] / ".env"
            if dotenv_path.is_file():
                with open(dotenv_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip('"').strip("'")
                            if k:
                                os.environ.setdefault(k, v)
            e = os.environ
        else:
            e = env

        return cls(
            stt=e.get("DEEPTALK_STT", "fake"),
            whisper_model=e.get("DEEPTALK_WHISPER_MODEL", "base"),
            audio=e.get("DEEPTALK_AUDIO", "file"),
            session_id=e.get("DEEPTALK_SESSION_ID", "demo"),
            db_path=e.get("DEEPTALK_DB", "deeptalk-demo.db"),
            fixture_path=e.get("DEEPTALK_FIXTURE", _DEFAULT_FIXTURE),
            audio_file=e.get("DEEPTALK_AUDIO_FILE"),
            qwen_asr_url=e.get(
                "DEEPTALK_QWEN_ASR_URL",
                "http://127.0.0.1:8010/v1/audio/transcriptions",
            ),
            qwen_asr_model=e.get("DEEPTALK_QWEN_ASR_MODEL", "Qwen/Qwen3-ASR-0.6B"),
            qwen_asr_chunk_ms=int(e.get("DEEPTALK_QWEN_ASR_CHUNK_MS", "2000")),
            search_provider=e.get("DEEPTALK_SEARCH_PROVIDER", "fake"),
            anthropic_model=e.get("DEEPTALK_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            openrouter_model=e.get("DEEPTALK_OPENROUTER_MODEL", "google/gemini-2.5-flash"),
            openrouter_api_key=e.get("OPENROUTER_API_KEY"),
            intent_detector=e.get("DEEPTALK_INTENT", "heuristic"),
            diarize=e.get("DEEPTALK_DIARIZE", "off"),
            recording_path=e.get("DEEPTALK_RECORDING"),
            max_agent_calls=int(e.get("DEEPTALK_MAX_AGENT_CALLS", "50")),
            agent_timeout=float(e.get("DEEPTALK_AGENT_TIMEOUT", "30")),
            enable_mockup=e.get("DEEPTALK_ENABLE_MOCKUP", "true").lower() != "false",
            host=e.get("DEEPTALK_HOST", "127.0.0.1"),
            port=int(e.get("DEEPTALK_PORT", "8000")),
        )
