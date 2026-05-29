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

    stt: str = "fake"  # "fake" | "nemotron"
    audio: str = "file"  # "file" | "mic"
    session_id: str = "demo"
    db_path: str = "deeptalk-demo.db"
    fixture_path: str = _DEFAULT_FIXTURE
    audio_file: str | None = None
    search_provider: str = "fake"  # "fake" | "anthropic"
    anthropic_model: str = "claude-sonnet-4-6"
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        e = os.environ if env is None else env
        return cls(
            stt=e.get("DEEPTALK_STT", "fake"),
            audio=e.get("DEEPTALK_AUDIO", "file"),
            session_id=e.get("DEEPTALK_SESSION_ID", "demo"),
            db_path=e.get("DEEPTALK_DB", "deeptalk-demo.db"),
            fixture_path=e.get("DEEPTALK_FIXTURE", _DEFAULT_FIXTURE),
            audio_file=e.get("DEEPTALK_AUDIO_FILE"),
            search_provider=e.get("DEEPTALK_SEARCH_PROVIDER", "fake"),
            anthropic_model=e.get("DEEPTALK_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            host=e.get("DEEPTALK_HOST", "127.0.0.1"),
            port=int(e.get("DEEPTALK_PORT", "8000")),
        )
