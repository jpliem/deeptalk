from fastapi.testclient import TestClient

from deeptalk.artifacts.models import Artifact
from deeptalk.artifacts.store import ArtifactStore
from deeptalk.bus import EventBus
from deeptalk.llm.fake import FakeLlmProvider
from deeptalk.llm.router import AllProvidersFailed, ModelRouter, run_with_fallback
from deeptalk.report.builder import build_report
from deeptalk.server.app import create_app
from deeptalk.timeline.models import TimelineEntry
from deeptalk.timeline.store import TimelineStore
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.transcript.store import TranscriptStore
from deeptalk.wiki.models import Wiki
from deeptalk.wiki.store import WikiStore


class _StubProvider:
    def __init__(self, answer="A concise executive summary.", fail=False):
        self._answer = answer
        self._fail = fail

    @property
    def name(self):
        return "stub"

    async def complete(self, prompt: str) -> str:
        if self._fail:
            raise RuntimeError("provider down")
        return self._answer


def _router(provider=None):
    p = provider or _StubProvider()
    return ModelRouter(providers={"stub": p}, routes={}, default=["stub"])


def _event(text, ts=0.0, speaker=None, is_final=True):
    return TranscriptEvent(
        session_id="s1", ts=ts, text=text, is_final=is_final, speaker=speaker
    )


def _entry(label, start=0.0, end=10.0, decisions=(), actions=(), summary=""):
    return TimelineEntry(
        id=f"t-{label}",
        session_id="s1",
        topic_id=label,
        label=label,
        start_ts=start,
        end_ts=end,
        summary=summary,
        decisions=tuple(decisions),
        action_items=tuple(actions),
        created_at=0.0,
    )


async def test_report_contains_all_sections():
    md = await build_report(
        session_id="s1",
        events=[_event("we should ship friday", ts=65.0, speaker=1)],
        timeline_entries=[
            _entry("Release planning", 0, 120, ["ship friday"], ["update changelog"],
                   summary="Discussed the release date.")
        ],
        wiki=Wiki(session_id="s1", topics=["Release planning"],
                  decisions=["Ship Friday"], action_items=["Update changelog"],
                  created_at=0.0),
        artifacts=[
            Artifact(id="a1", session_id="s1", agent="search", status="done",
                     title="when is the freeze", payload={"answer": "Thursday."},
                     created_at=0.0),
            Artifact(id="a2", session_id="s1", agent="proscons", status="error",
                     title="failed one", payload={}, created_at=0.0),
        ],
        router=_router(),
        now=1_784_000_000.0,
    )

    assert md.startswith("# Meeting Report — s1")
    assert "## Executive Summary" in md
    assert "A concise executive summary." in md
    assert "### Release planning (00:00–02:00)" in md
    assert "Discussed the release date." in md
    # deduped across timeline + wiki (case-insensitive)
    decisions_section = md.split("## Decisions")[1].split("## Action Items")[0]
    assert decisions_section.lower().count("ship friday") == 1
    assert "- [ ] update changelog" in md.lower()
    assert "**search** — when is the freeze: Thursday." in md
    assert "failed one" not in md  # error artifacts excluded
    assert "- [01:05] Speaker 1: we should ship friday" in md


async def test_report_summary_falls_back_when_llm_fails():
    md = await build_report(
        session_id="s1",
        events=[_event("hello")],
        timeline_entries=[_entry("Databases")],
        wiki=None,
        artifacts=[],
        router=_router(_StubProvider(fail=True)),
        now=0.0,
    )
    assert "The meeting covered: Databases." in md
    assert "_No agent findings._" in md


async def test_report_handles_empty_session_data():
    md = await build_report(
        session_id="s1",
        events=[_event("only line")],
        timeline_entries=[],
        wiki=None,
        artifacts=[],
        router=_router(_StubProvider(fail=True)),
        now=0.0,
    )
    assert "_No topics identified._" in md
    assert "_None recorded._" in md
    assert "- [00:00] only line" in md


def _app_deps(tmp_path):
    store = TranscriptStore(str(tmp_path / "t.db"))
    store.append(_event("should we use postgres", ts=3.0))
    tstore = TimelineStore(str(tmp_path / "tl.db"))
    tstore.upsert(_entry("Databases", 0, 30, ["use postgres"], []))
    return {
        "store": store,
        "bus": EventBus(),
        "artifact_store": ArtifactStore(str(tmp_path / "a.db")),
        "artifact_bus": EventBus(),
        "router": ModelRouter(
            providers={"fake": FakeLlmProvider()}, routes={}, default=["fake"]
        ),
        "wiki_store": WikiStore(str(tmp_path / "w.db")),
        "timeline_store": tstore,
        "timeline_bus": EventBus(),
    }


def test_report_endpoint_returns_markdown(tmp_path):
    app = create_app(**_app_deps(tmp_path))
    client = TestClient(app)

    resp = client.get("/report?session_id=s1")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.text.startswith("# Meeting Report — s1")
    assert "use postgres" in resp.text
    assert "- [00:03] should we use postgres" in resp.text


def test_report_endpoint_404_when_no_transcript(tmp_path):
    app = create_app(**_app_deps(tmp_path))
    client = TestClient(app)
    assert client.get("/report?session_id=empty").status_code == 404
