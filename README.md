# DeepTalk

Real-time meeting assistant. DeepTalk listens to a discussion, transcribes it via
STT (fake / Nemotron / Whisper / Qwen3-ASR), auto-detects intent, fires AI agents
that produce search answers, pros/cons, plans, and Mermaid diagrams — surfaced as
cards on a live chat-style dashboard.  A background timeline service periodically
summarizes the conversation into topics, decisions, and action items.  Post-session,
speaker diarization (VibeVoice) labels who said what, and a wiki is built.

## Architecture

```mermaid
flowchart TB
    subgraph Inputs["Audio Inputs"]
        MIC["🎤 Live Mic (WebSocket)"]
        FILE["📁 File Upload (POST /upload)"]
        FIXTURE["📼 Fixture Replay (dev)"]
    end

    subgraph STT["Speech-to-Text"]
        FAKE["FakeStt (fixture)"]
        NEMO["Nemotron (GPU, nemo)"]
        WHISPER["faster-whisper (GPU)"]
        QWEN["Qwen3-ASR (sidecar)"]
    end

    subgraph Core["Core Pipeline"]
        TS["TranscriptStore (SQLite)"]
        BUS["Event Bus"]
        ORCH["Orchestrator"]
        INTENT["Intent Detector<br/>(heuristic / llm)"]
    end

    subgraph Agents["AI Agents"]
        SEARCH["🔍 Search Agent<br/>(Anthropic / OpenRouter / Ollama)"]
        PC["⚖️ Pros/Cons Agent"]
        PLAN["📋 Planning Agent"]
        MOCKUP["🎨 Mockup Agent<br/>(Mermaid)"]
    end

    subgraph Outputs["Outputs"]
        ART["Artifact Cards<br/>(SQLite + WebSocket)"]
        WS_TRANSCRIPT["/ws/transcript"]
        WS_ARTIFACTS["/ws/artifacts"]
    end

    subgraph Timeline["Timeline (Rolling Summary)"]
        T_SVC["TimelineService<br/>(every N seconds via Ollama)"]
        T_STORE["TimelineStore (SQLite)"]
        T_WS["/ws/timeline"]
    end

    subgraph Finalize["Post-Session"]
        DIARIZE["VibeVoice Diarizer<br/>(GPU)"]
        WIKI["Wiki Store (SQLite)"]
    end

    subgraph UI["React UI"]
        APP["App.tsx"]
        CHAT["Chat Feed<br/>(transcript + cards)"]
        SIDEBAR["Sidebar<br/>(sessions + timeline)"]
        T_PANEL["TimelinePanel<br/>(dot / swimlane)"]
    end

    MIC -->|"16 kHz PCM via /ws/live-audio"| WHISPER
    MIC --> QWEN
    FILE -->|"POST /upload → ffmpeg decode"| NEMO
    FILE --> QWEN
    FIXTURE --> FAKE

    NEMO --> TS
    WHISPER --> TS
    QWEN --> TS
    FAKE --> TS

    TS -->|"events"| BUS
    BUS -->|"transcript events"| WS_TRANSCRIPT
    WS_TRANSCRIPT --> CHAT

    BUS --> ORCH
    ORCH --> INTENT
    INTENT --> SEARCH
    INTENT --> PC
    INTENT --> PLAN
    INTENT --> MOCKUP

    SEARCH --> ART
    PC --> ART
    PLAN --> ART
    MOCKUP --> ART

    ART -->|"artifact events"| WS_ARTIFACTS
    WS_ARTIFACTS --> CHAT

    TS -.->|"new text"| T_SVC
    T_SVC --> T_STORE
    T_STORE --> T_WS
    T_WS --> T_PANEL

    TS -->|"POST /finalize"| DIARIZE
    DIARIZE --> WIKI
    ART -.-> WIKI
```

**Data flow (simplified):** Audio → STT → TranscriptStore → EventBus → both the UI (via WebSocket) and the Orchestrator → Agents → Artifact cards → UI.

A separate TimelineService polls new transcript text, summarizes it via Ollama, merges into a timeline store, and pushes live updates over `/ws/timeline`.

## Current state

Everything below works end-to-end on a developer machine (fake STT, fake agents) and on a GPU laptop (real STT, real agents, diarization).

### What's implemented (all phases 1–9)

| Area | Status | Notes |
|------|--------|-------|
| **Transcript spine** (SQLite append-only store + WebSocket push) | ✅ | Source of truth; dedup by span_id |
| **Live STT** — fake, Nemotron (nemo), faster-whisper, Qwen3-ASR | ✅ | Qwen is a separate sidecar process |
| **Live mic streaming** — AudioWorkletNode → /ws/live-audio WebSocket | ✅ | 16 kHz PCM; also works with file upload |
| **Model router** — Anthropic Claude, OpenRouter (Gemini), Ollama (local) | ✅ | Pick via `DEEPTALK_SEARCH_PROVIDER` |
| **Intent detector** — heuristic (free) or LLM-powered | ✅ | |
| **Orchestrator** — routes detected intents to agents | ✅ | Concurrency limit, cost tracking, timeout |
| **Search agent** — web search + answer with citations | ✅ | |
| **Pros/Cons agent** — extracts pros, cons, recommendation | ✅ | |
| **Planning agent** — generates step-by-step plans | ✅ | |
| **Mockup agent** — generates Mermaid diagrams via `enable_mockup` flag | ✅ | Lazy-loads mermaid in the UI |
| **Session wiki** — topics, decisions, action items (post-finalize) | ✅ | |
| **Speaker diarization** — VibeVoice (post-session) | ✅ | GPU-only; auto-records when `DEEPTALK_RECORDING` is set |
| **Timeline (rolling summarization)** — background Ollama service | ✅ | Merges topics by (session, topic_id); dot + swimlane views |
| **Session management** — create, switch, rename, delete sessions | ✅ | localStorage + SQLite per-session isolation |
| **Chat-style UI** — transcript bubbles, user messages, artifact cards | ✅ | New sidebar layout, mobile overlay |
| **Audio file upload** — mp3/m4a/wav → ffmpeg decode → STT | ✅ | |
| **GPU lease** — VRAM reservation, concurrent-STT guard | ✅ | |
| **Cost/timeout hardening** — max agent calls, per-agent timeout | ✅ | |

### In development / on deck

- End-to-end Nemotron validation on real GPU hardware (NeMo API tuning)
- Export / share session transcripts
- Real-time speaker identification (not just post-session diarization)

## Quickstart

```bash
# Requires: Python 3.12+, Node.js 18+, uv
uv sync
cd ui && npm install && npm run build && cd ..
DEEPTALK_STT=fake uv run python -m deeptalk.server
# open http://127.0.0.1:8000/
```

> **Seeing `{"detail":"Not Found"}` at `/`?** You skipped `npm run build`. The API works — check `curl http://127.0.0.1:8000/health`.

### Real agents (any machine + API key)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
DEEPTALK_SEARCH_PROVIDER=anthropic uv run python -m deeptalk.server
```

Or with a local Ollama model:

```bash
DEEPTALK_SEARCH_PROVIDER=ollama DEEPTALK_OLLAMA_MODEL=llama3.2:3b uv run python -m deeptalk.server
```

### GPU + real STT (Linux / WSL2)

```bash
uv sync --extra gpu
cd ui && npm install && npm run build && cd ..

# Whisper (faster-whisper)
DEEPTALK_STT=whisper DEEPTALK_AUDIO_FILE=/path/16k_mono.wav uv run python -m deeptalk.server

# Qwen3-ASR sidecar
qwen-asr-serve Qwen/Qwen3-ASR-0.6B --host 127.0.0.1 --port 8010
DEEPTALK_STT=qwen DEEPTALK_AUDIO_FILE=/path/16k_mono.wav uv run python -m deeptalk.server
```

### Timeline (rolling summarization via Ollama)

```bash
# Requires Ollama running on localhost:11434 with a model loaded (e.g. llama3.2:3b)
DEEPTALK_TIMELINE_INTERVAL=45 uv run python -m deeptalk.server
```

Set `DEEPTALK_TIMELINE_INTERVAL=0` to disable. The timeline appears in the sidebar — toggle between **Dots** and **Swimlane** views. Click an entry to jump to that moment in the transcript.

### Live mic (Linux desktop, not WSL)

```bash
DEEPTALK_STT=whisper DEEPTALK_AUDIO=mic uv run python -m deeptalk.server
# Click the 🎤 button in the input bar to start streaming
```

### Diarization + wiki

```bash
DEEPTALK_DIARIZE=vibevoice DEEPTALK_RECORDING=/path/meeting.wav uv run python -m deeptalk.server
# In the UI, click "Build wiki" — or:
curl -X POST localhost:8000/finalize -H 'content-type: application/json' -d '{"session_id":"demo"}'
```

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness |
| `GET /` | UI (after `npm run build`) |
| `WS /ws/transcript?session_id=` | Live transcript stream |
| `WS /ws/artifacts?session_id=` | Live agent card stream |
| `WS /ws/live-audio?session_id=` | Accepts 16 kHz PCM binary frames for live STT |
| `WS /ws/timeline?session_id=` | Live timeline entry stream |
| `POST /ask` `{session_id, query}` | Run the search agent manually |
| `POST /upload` `{session_id, file}` | Upload audio for transcription |
| `POST /finalize` `{session_id}` | Build wiki (+ diarize if configured) |
| `POST /clear` `{session_id}` | Clear session data |
| `GET /wiki?session_id=` | Get the session wiki |

## Configuration (environment variables)

| Variable | Default | Meaning |
|----------|---------|---------|
| `DEEPTALK_STT` | `fake` | `fake`, `whisper` (faster-whisper), `qwen` (Qwen3-ASR sidecar), `nemotron` |
| `DEEPTALK_WHISPER_MODEL` | `base` | faster-whisper model size |
| `DEEPTALK_AUDIO` | `file` | `file` or `mic` |
| `DEEPTALK_AUDIO_FILE` | — | Path to 16 kHz mono WAV |
| `DEEPTALK_QWEN_ASR_URL` | `http://127.0.0.1:8010/v1/audio/transcriptions` | Qwen3-ASR endpoint |
| `DEEPTALK_QWEN_ASR_MODEL` | `Qwen/Qwen3-ASR-0.6B` | Qwen3-ASR model name |
| `DEEPTALK_QWEN_ASR_CHUNK_MS` | `2000` | PCM window for live Qwen |
| `DEEPTALK_SEARCH_PROVIDER` | `fake` | `fake`, `anthropic`, `openrouter`, `ollama` |
| `DEEPTALK_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `DEEPTALK_OLLAMA_MODEL` | `llama3.2:3b` | Ollama model name |
| `DEEPTALK_TIMELINE_INTERVAL` | `45` | Seconds between timeline summarizations (`0` = off) |
| `DEEPTALK_ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Claude model name |
| `DEEPTALK_OPENROUTER_MODEL` | `google/gemini-2.5-flash` | OpenRouter model |
| `DEEPTALK_INTENT` | `heuristic` | `heuristic` or `llm` |
| `DEEPTALK_DIARIZE` | `off` | `off` or `vibevoice` |
| `DEEPTALK_RECORDING` | — | WAV path for recording + diarization |
| `DEEPTALK_MAX_AGENT_CALLS` | `50` | Per-session agent cap (`-1` = unlimited) |
| `DEEPTALK_AGENT_TIMEOUT` | `30` | Per-agent timeout (seconds) |
| `DEEPTALK_SESSION_ID` | `demo` | Current session ID |
| `DEEPTALK_DB` | `deeptalk-demo.db` | SQLite path |
| `DEEPTALK_FIXTURE` | bundled | Fixture path (when STT=fake) |
| `DEEPTALK_HOST` / `DEEPTALK_PORT` | `127.0.0.1` / `8000` | Bind address |
| `ANTHROPIC_API_KEY` | — | Required for Anthropic provider |
| `OPENROUTER_API_KEY` | — | Required for OpenRouter provider |

## UI dev mode

```bash
cd ui
VITE_WS_BASE=ws://127.0.0.1:8000 npm run dev   # Vite on :5173
# Python server on :8000
```

## Tests

```bash
uv run pytest -q     # Python backend
cd ui && npm test    # UI (Vitest)
```

## Known gaps

- **Nemotron** STT is wired but not validated on real GPU hardware — will need NeMo API / chunk-size tuning on first run.
- **Live mic** is unavailable in WSL2 (no default audio input device).
- **Timeline** requires a local Ollama instance — no remote LLM fallback yet.
