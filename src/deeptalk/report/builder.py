from __future__ import annotations

import logging
from datetime import datetime, timezone

from deeptalk.artifacts.models import Artifact
from deeptalk.llm.router import ModelRouter, run_with_fallback
from deeptalk.timeline.models import TimelineEntry
from deeptalk.transcript.events import TranscriptEvent
from deeptalk.wiki.models import Wiki

log = logging.getLogger(__name__)

AGENT = "report"

_MAX_SUMMARY_TRANSCRIPT_LINES = 60
_MAX_FINDING_CHARS = 200

_SUMMARY_PROMPT = (
    "Write a 3-5 sentence executive summary of this meeting in plain prose. "
    "No headings, no bullet points, no preamble.\n\n"
    "Topics discussed:\n{topics}\n\n"
    "Transcript (excerpt):\n{transcript}"
)


def _fmt_ts(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        cleaned = item.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


async def _executive_summary(
    router: ModelRouter, topics: list[str], lines: list[str]
) -> str:
    prompt = _SUMMARY_PROMPT.format(
        topics="\n".join(topics) or "(none)",
        transcript="\n".join(lines[-_MAX_SUMMARY_TRANSCRIPT_LINES:]) or "(none)",
    )
    try:
        providers = router.chain_for(AGENT)
        text = (await run_with_fallback(providers, lambda p: p.complete(prompt))).strip()
        if text:
            return text
    except Exception as error:  # noqa: BLE001 - report is best-effort
        log.warning("report: executive summary failed: %r", error)
    if topics:
        return "The meeting covered: " + "; ".join(topics) + "."
    return f"The session recorded {len(lines)} transcript lines."


def _finding_body(artifact: Artifact) -> str:
    p = artifact.payload
    if artifact.agent == "search":
        body = p.get("answer", "")
    elif artifact.agent == "proscons":
        body = p.get("recommendation", "")
    elif artifact.agent == "planning":
        steps = p.get("steps", [])
        body = f"{len(steps)}-step plan" if steps else ""
    elif artifact.agent == "mockup":
        body = p.get("caption", "diagram")
    else:
        body = ""
    body = " ".join(str(body).split())
    if len(body) > _MAX_FINDING_CHARS:
        body = body[: _MAX_FINDING_CHARS - 1] + "…"
    return body


async def build_report(
    session_id: str,
    events: list[TranscriptEvent],
    timeline_entries: list[TimelineEntry],
    wiki: Wiki | None,
    artifacts: list[Artifact],
    router: ModelRouter,
    now: float,
) -> str:
    """Assemble the meeting minutes as Markdown.

    Structure comes from data already gathered during the session (timeline,
    wiki, agent artifacts, transcript); only the executive summary needs an
    LLM call, and it degrades to a deterministic sentence when that fails.
    """
    final_events = [e for e in events if e.is_final]
    lines = [e.text for e in final_events]

    topic_labels = [t.label for t in timeline_entries] or list(wiki.topics if wiki else [])
    decisions = _dedup(
        [d for t in timeline_entries for d in t.decisions]
        + list(wiki.decisions if wiki else [])
    )
    actions = _dedup(
        [a for t in timeline_entries for a in t.action_items]
        + list(wiki.action_items if wiki else [])
    )

    summary = await _executive_summary(router, topic_labels, lines)
    generated = datetime.fromtimestamp(now, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    md: list[str] = [
        f"# Meeting Report — {session_id}",
        "",
        f"_Generated {generated}_",
        "",
        "## Executive Summary",
        "",
        summary,
        "",
        "## Topics",
        "",
    ]

    if timeline_entries:
        for t in timeline_entries:
            md.append(f"### {t.label} ({_fmt_ts(t.start_ts)}–{_fmt_ts(t.end_ts)})")
            md.append("")
            if t.summary:
                md.append(t.summary)
                md.append("")
    elif topic_labels:
        md.extend(f"- {label}" for label in topic_labels)
        md.append("")
    else:
        md.append("_No topics identified._")
        md.append("")

    md.append("## Decisions")
    md.append("")
    if decisions:
        md.extend(f"- {d}" for d in decisions)
    else:
        md.append("_None recorded._")
    md.append("")

    md.append("## Action Items")
    md.append("")
    if actions:
        md.extend(f"- [ ] {a}" for a in actions)
    else:
        md.append("_None recorded._")
    md.append("")

    md.append("## Assistant Findings")
    md.append("")
    done = [a for a in artifacts if a.status == "done"]
    if done:
        for a in done:
            body = _finding_body(a)
            md.append(f"- **{a.agent}** — {a.title}" + (f": {body}" if body else ""))
    else:
        md.append("_No agent findings._")
    md.append("")

    md.append("## Transcript")
    md.append("")
    if final_events:
        for e in final_events:
            speaker = f"Speaker {e.speaker}: " if e.speaker is not None else ""
            md.append(f"- [{_fmt_ts(e.ts)}] {speaker}{e.text}")
    else:
        md.append("_Empty transcript._")
    md.append("")

    return "\n".join(md)
