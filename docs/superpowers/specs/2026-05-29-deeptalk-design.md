# DeepTalk — Design Spec

- **Date:** 2026-05-29
- **Status:** Draft for review
- **Author:** brainstormed with Claude

## 1. Overview

DeepTalk is a real-time meeting/discussion assistant. It passively listens to an
in-person conversation, transcribes it live, detects intent (questions, debates,
planning, design topics), and fires AI agents in parallel that render results —
search answers, pros/cons + opinions, plans, and UI/architecture mockups — onto a
live dashboard. After the session it produces a structured wiki of what was
discussed and decided.

DeepTalk never speaks. It is a silent observer that paints artifacts on screen.
That single property drives the whole architecture: there is no speech-out / voice
agent layer.

## 2. Goals (v1)

- Capture in-person room audio from one mic.
- Live transcript with low latency.
- Detect intent and auto-fire the relevant agent(s) in parallel.
- Four agents: **web/knowledge search**, **pros/cons + opinion**, **planning /
  task breakdown**, **mockup / diagram** (mockup ships last, behind a feature flag —
  highest risk, slowest, most error-prone in real time).
- Per-agent configurable model routing (local or cloud), set by config/UI.
- Post-session diarized transcript + structured session wiki (topics, decisions,
  action items, references).
- Audio never leaves the machine; only text reaches cloud agents.

## 3. Non-Goals (v1)

- No speech-out / talking agent (PersonaPlex and similar are explicitly out — wrong
  product shape).
- No multi-device / LAN client-server split (single box).
- No live diarization (runs post-session due to 6GB VRAM limit).
- No emotion/tone analysis (MOSS-Audio deferred to a later version).
- No multi-language live transcript in v1 (nemotron live path is English-only).

## 4. Constraints

- **Hardware:** runs entirely on one RTX 3060 **laptop, 6GB VRAM** (Linux/Windows,
  CUDA). This laptop is the device physically present in the meeting.
- **Dev machine** is macOS, but the app **runs on the 3060 laptop**.
- **Hybrid by default:** local STT, cloud agent LLMs (keeps agents parallel without
  exhausting 6GB).
- 6GB cannot hold the live STT model and the diarization model simultaneously.

## 5. Model Decisions

| Model | Role | Decision |
|-------|------|----------|
| `nvidia/nemotron-speech-streaming-en-0.6b` | Tier-1 live STT | **Use.** True streaming, 0.08–1.1s latency, ~6.9% WER, ~2GB VRAM. English only, no diarization. Resident on GPU during the meeting. |
| `microsoft/VibeVoice-ASR-HF` (8B) | Tier-2 diarized record | **Use, batch only.** Diarization (who/when/what JSON), 51 languages, MIT. ~5GB at Q4 — runs **after** the meeting (or during long pauses), not concurrently with nemotron. |
| `OpenMOSS-Team/MOSS-Audio-4B-Instruct` | Audio understanding (tone/emotion/events) | **Defer.** Optional enrichment for a later version. Overlaps a text LLM for most jobs. |
| `nvidia/personaplex-7b-v1` | Speech-to-speech voice agent | **Reject.** Wrong product shape (talks back); needs A100/H100. |

Rationale: STT and "understanding" are different layers. The live transcript comes
from a streaming STT (nemotron); understanding and agent work run on text LLMs via
the router; diarization is a separate batch pass (VibeVoice).

## 6. Architecture (single box)

```
┌──────────── RTX 3060 LAPTOP (the meeting device) ────────────┐
│  🎤 mic capture                                              │
│       ↓                                                      │
│  ┌── GPU (6GB) ──────────────┐  live: nemotron only          │
│  │ Tier-1 nemotron → live txt │  VibeVoice = batch AFTER      │
│  │ Tier-2 VibeVoice (post)    │  (diarized wiki)              │
│  └────────────────────────────┘                              │
│       ↓ transcript stream                                    │
│  ORCHESTRATOR                                                │
│   ├ intent/topic detector (debounced)                        │
│   ├ dispatch + dedup → fire agents in parallel               │
│   └ MODEL ROUTER ◀── per-agent: local OR cloud               │
│       ↓                          ↓ (local route)             │
│  🖥️ Dashboard UI            Local LLM (Ollama, optional)     │
│  📚 Session wiki            💾 Session store (SQLite)         │
└────────────────────┬─────────────────────────────────────────┘
                     │ text-only (cloud route)
                     ▼
        ☁️ Anthropic / OpenAI / Gemini — parallel agents
```

Audio stays on the machine. Only text crosses to cloud agents, per router config.

## 7. Components

Design principle: **one append-only transcript event log is the single source of
truth.** All other components subscribe to it. This makes the system replayable
(feed a recorded meeting → assert agents fire) and decoupled.

| # | Module | Responsibility | Interface (in → out) | Depends |
|---|--------|----------------|----------------------|---------|
| 1 | Audio Capture | mic → frames | device → 16kHz mono PCM stream | OS audio |
| 2 | STT-Live (nemotron) | PCM → live text | PCM → `{text, ts, isFinal}` events | NeMo/CUDA |
| 3 | STT-Diarize (VibeVoice) | buffered audio → who/when/what | audio window → `{speaker,start,end,text}[]` | transformers/CUDA |
| 4 | Transcript Store | source of truth | append events / subscribe stream | SQLite |
| 5 | Intent Detector | spot questions/topics/debates | transcript window → `{type,topic,confidence,span}` (debounced) | Router |
| 6 | Orchestrator | intent → agents, dedup, concurrency cap | intent → agent jobs | — |
| 7 | Model Router | resolve any call to a provider | `{agent→provider+model}` config → client; fallback chain | Ollama + cloud SDKs |
| 8 | Agents ×4 | search / pros-cons / planning / mockup | `context → typed artifact` (declared schema + tools) | Router |
| 9 | Artifact Bus | results → cards + persist | artifact → UI event + store | — |
| 10 | Wiki Builder | structured session doc | diarized transcript + artifacts → topics/decisions/actions/refs | Router |
| 11 | Dashboard UI | transcript + live cards + wiki + settings | subscribes events; edits router config/keys | Tauri (or Electron) |
| 12 | Session Store | persist everything | SQLite: transcript, artifacts, wiki, config | — |

### Dispatch loop

```
transcript event → Intent Detector (debounced ~2s)
  → intent {type: question|debate|planning|design, topic, span}
  → Orchestrator: seen this topic already? skip. else:
  → map intent.type → agent(s):
       question → search
       debate   → pros/cons
       planning → planning
       design/UI→ mockup (flagged)
  → fire matched agents IN PARALLEL, each via Router
  → results stream to Artifact Bus → cards appear (target <5s intent→card)
```

Two baked-in calls:
- **Dedup by topic** so one discussion does not spam duplicate cards.
- **Manual override** — user taps a transcript line to force-fire any agent
  (covers intent-detector misses).

## 8. Model Router (the spine)

- Config maps `{agentName → {provider, model}}`. Providers: `local` (Ollama),
  `anthropic`, `openai`, `gemini`.
- Per-agent override; editable in the settings UI.
- **Fallback chain** per call: configured provider → backup model → local small
  model → emit "agent unavailable" artifact. One agent's failure never blocks
  others.
- API keys stored locally (OS keychain / encrypted config), validated at startup;
  missing key → per-agent "needs key" state, never a silent failure.

## 9. 6GB GPU Scheduling

A small **GPU lease manager** owns the 6GB: one resident model during live, a queue
for batch jobs.

```
DURING meeting (live):  nemotron 0.6B (~2GB) RESIDENT, owns GPU. Raw audio also
                        written to disk continuously.
AFTER meeting (batch):  unload nemotron → load VibeVoice-8B → diarize full audio →
                        build wiki. (or opportunistically during a long pause)
Local-LLM agents:       compete for 6GB → discouraged during live; default agents
                        are CLOUD. If routed local, the lease manager queues them;
                        never co-loaded with nemotron.
MOSS-Audio:             not v1; load-on-demand post-session if added later.
```

OOM is prevented by construction. If it still occurs → drop the batch job, degrade
to nemotron-only, retry.

## 10. Error Handling

Guiding rule: **session survival > any single feature.** The transcript + raw audio
recording is the floor that never fails; agents are best-effort enrichments that
fail independently and never crash the session.

| Failure | Behavior |
|---------|----------|
| Cloud API down/timeout | Router fallback chain → backup → local → "unavailable" card. Others unaffected. |
| Agent times out (>~15s) | Cancel, show error card, session continues |
| STT-Live drops | Buffer + reconnect, keep last good transcript. Raw audio always on disk → nothing lost |
| Intent detector noisy | Debounce + confidence threshold + dedup; manual tap-to-fire for misses |
| GPU OOM | Lease manager prevents; if hit, drop batch job → nemotron-only |
| API key missing | Startup warning + per-agent "needs key" state |
| Mic denied | Hard block with clear message at launch |
| Fully offline | Cloud agents → local fallback if configured, else "search disabled"; transcript + wiki still work |
| Cost runaway | Per-session token/cost cap, warn before exceeding |
| App crash mid-session | Continuous transcript + audio persistence → recover + still build wiki after |

Two pillars: **router fallback chain** and **continuous audio + transcript
persistence**.

## 11. Data Model (Session Store, SQLite)

- `session` — id, start/end, config snapshot.
- `transcript_event` — session_id, ts, text, is_final, source (live|diarized),
  speaker (nullable, filled post-diarization), span_id.
- `artifact` — session_id, agent, intent_topic, status, payload (typed JSON),
  created_at, latency_ms, cost.
- `wiki` — session_id, structured doc (topics, decisions, action_items,
  references), finalized_at.
- `router_config` — agent → provider/model.

Raw audio persisted to disk per session for post-diarization and recovery.

## 12. Testing Strategy

Golden fixtures are the backbone: short scripted meeting clips (a clip that asks a
question, debates a stack, plans tasks, sketches UI), each paired with expected
transcript, intents, and cards. Cloud LLM calls are mocked with canned responses by
default; a small gated suite hits real APIs.

- **Unit (target 80% coverage, concentrated on logic):** Model Router (resolution,
  override, fallback chain with mocked-down providers); Intent Detector (debounce +
  threshold + parsing, model mocked); each Agent (output matches declared schema);
  dedup; GPU lease manager (never co-loads, queues correctly); Wiki Builder
  (structure, not exact words).
- **Integration:** transcript → dispatch (replay event stream → correct agents fire
  in parallel, deduped, via router); STT-Live (recorded WAV → assert key phrases +
  WER under threshold); STT-Diarize (multi-speaker WAV → N speakers + who/when/what
  structure).
- **E2E:** golden meeting replay (audio → each expected card within latency budget);
  offline (network down → transcript + wiki still produced, agents degrade); crash
  recovery (kill mid-session → restart → recovery + wiki buildable).
- **Quality gates:** latency assertion (<5s intent→card on goldens), WER regression
  threshold, cost-cap warning on simulated spend.

**LLM testing rule:** never assert exact model text — assert schema, which agent
fired, fallback behavior, and latency. Determinism comes from mocked canned outputs.

## 13. Latency Targets

- Live caption: < ~1.1s (nemotron chunk).
- Intent → first agent card: **< 5s** (headline target, asserted in E2E).
- Diarization + wiki: post-session (no live budget).

## 14. Open Decisions (resolve during planning)

- **UI shell:** Tauri (lighter, Rust) vs Electron (easier, larger). Recommend Tauri
  for footprint; Electron if web tooling speed matters more.
- **Cloud providers for v1:** which of Anthropic / OpenAI / Gemini to wire first
  (router supports all; pick a default).
- **Intent detector model:** small local LLM vs a cheap cloud model. Affects live
  GPU budget if local.
- **Mockup agent output format:** HTML vs Mermaid vs both.

## 15. Suggested Build Order (v1 phasing)

1. Audio capture + nemotron live transcript + Transcript Store (the floor).
2. Dashboard UI: live transcript pane.
3. Model Router + one agent (search) end-to-end via cloud.
4. Intent Detector + Orchestrator dispatch + dedup + manual override.
5. Remaining text agents: pros/cons, planning.
6. VibeVoice batch diarization + Wiki Builder.
7. GPU lease manager hardening + error/fallback paths.
8. Mockup agent (flagged) last.

## 16. Risks

- Mockup agent quality/latency in real time (mitigated: flagged, ships last).
- 6GB ceiling if user routes agents local (mitigated: cloud default + lease manager).
- nemotron English-only for live (multilingual recovered post via VibeVoice).
- Cloud agent cost (mitigated: per-session cap + warnings).
- Intent detection precision (mitigated: debounce + confidence + dedup + manual override).
```
