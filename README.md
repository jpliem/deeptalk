# DeepTalk

Real-time meeting assistant. DeepTalk listens to a discussion, transcribes it live,
auto-detects intent, and fires AI agents that surface **web-search answers**,
**pros/cons + a recommendation**, and **task plans** as cards on a live dashboard —
then builds a **session wiki** (topics, decisions, action items). Optional speaker
diarization labels who said what.

Implemented: Phases 1–7 (transcript spine → live STT → model router + search agent →
intent detector + orchestrator → pros/cons + planning agents → wiki + diarization →
GPU lease + cost/timeout hardening). The mockup/diagram agent (Phase 8) is optional
and not yet built. See `docs/superpowers/specs` and `docs/superpowers/plans`.

## Architecture (single box)

```
mic → STT (nemotron, live) → transcript store (SQLite, source of truth)
                           → event bus → WebSocket → React UI
                                       → orchestrator → intent detect → agents → artifact cards
post-session: VibeVoice diarization (who/when/what) + LLM session wiki
```

Audio stays on the machine. Only text reaches the cloud agents. STT, the LLM
provider, the intent detector, and the diarizer are each swappable behind one
interface — fakes for dev on any machine, real models on the GPU box.

## Requirements

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node.js 18+ + npm (for the UI)
- Real speech-to-text / diarization: an NVIDIA GPU (CUDA) — the `[gpu]` extra (Linux/WSL)
- Real agent answers: an Anthropic API key

## Quickstart (any machine, no GPU, fake STT + fake agents)

```bash
uv sync
cd ui && npm install && npm run build && cd ..   # REQUIRED — without it, / returns {"detail":"Not Found"}
uv run python -m deeptalk.server
# open http://127.0.0.1:8000/   (replays a sample meeting; agents fire with fake answers)
```

> **Seeing `{"detail":"Not Found"}` at `/`?** You skipped the UI build. `/` only serves
> the app after `npm run build` creates `ui/dist`. The API works regardless — check
> `curl http://127.0.0.1:8000/health`.

## Real agent answers (any machine + Anthropic key)

STT can stay fake (or be nemotron on a GPU); the *agents* become real with a key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
DEEPTALK_SEARCH_PROVIDER=anthropic uv run python -m deeptalk.server
```
Now questions get web-sourced answers (Claude + web_search), debates get real
pros/cons, planning talk gets real step plans. Set `DEEPTALK_INTENT=llm` for smarter
intent classification (otherwise a free heuristic is used).

## Running on the GPU laptop (Linux **or WSL2**)

```bash
git clone https://github.com/jpliem/deeptalk && cd deeptalk
uv sync --extra gpu                              # torch + nemo + transformers (CUDA)
cd ui && npm install && npm run build && cd ..   # fixes the / 404
```

**WSL notes (important):**
- CUDA works in WSL2 with the NVIDIA WSL driver → torch/nemo/VibeVoice run fine.
- **The microphone usually does NOT work in WSL** (no default audio input device), so
  `DEEPTALK_AUDIO=mic` will fail to capture. **Use a WAV file instead** on WSL.
- Open `http://localhost:8000/` from your Windows browser — WSL2 forwards localhost.

**Transcribe a 16 kHz mono WAV through the real model (recommended first run on WSL):**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
DEEPTALK_STT=nemotron DEEPTALK_AUDIO=file DEEPTALK_AUDIO_FILE=/path/16k_mono.wav \
  DEEPTALK_SEARCH_PROVIDER=anthropic \
  uv run python -m deeptalk.server
```

**Live microphone (Linux desktop, not WSL):**
```bash
DEEPTALK_STT=nemotron DEEPTALK_AUDIO=mic DEEPTALK_SEARCH_PROVIDER=anthropic \
  uv run python -m deeptalk.server
```

> If nemotron returns empty/garbled text on first run, the NeMo cache-aware streaming
> API or chunk size needs tuning — adjust `chunk_ms` / `att_context_size` in
> `src/deeptalk/stt/nemo_recognizer.py`. This is the one component not yet validated
> on hardware.

### Speaker diarization + session wiki

Diarization runs **after** the meeting (don't co-run nemotron + VibeVoice on a 6 GB
card — they won't both fit in VRAM). Point it at a recorded WAV:

```bash
DEEPTALK_DIARIZE=vibevoice DEEPTALK_RECORDING=/path/meeting.wav \
  uv run python -m deeptalk.server
# then build the wiki + diarized transcript:
curl -X POST localhost:8000/finalize -H 'content-type: application/json' -d '{"session_id":"demo"}'
```
In the browser, the **"Build wiki"** button does the same.

## Using the app

- **Talk** (or replay/transcribe) → questions/debates/plans in the conversation
  auto-produce answer / pros-cons / plan cards.
- **Ask box** — type a question to trigger a search manually.
- **Click a transcript line** — searches that line (tap-to-fire).
- **Build wiki** — summarizes the session into topics / decisions / action items.

## Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | liveness `{"status":"ok"}` |
| `GET /` | the UI (after `npm run build`) |
| `WS /ws/transcript?session_id=` | live transcript stream |
| `WS /ws/artifacts?session_id=` | live agent cards stream |
| `POST /ask` `{session_id, query}` | run the search agent manually |
| `POST /finalize` `{session_id}` | build the wiki (+ diarize a recording if configured) |
| `GET /wiki?session_id=` | the session wiki |

## Configuration (environment variables)

| Variable | Default | Meaning |
|----------|---------|---------|
| `DEEPTALK_STT` | `fake` | `fake` (fixture replay) or `nemotron` (real STT, GPU) |
| `DEEPTALK_AUDIO` | `file` | `file` or `mic` (when STT=nemotron). **mic unavailable on WSL** |
| `DEEPTALK_AUDIO_FILE` | — | path to a 16 kHz mono WAV (when AUDIO=file) |
| `DEEPTALK_SEARCH_PROVIDER` | `fake` | `fake` or `anthropic` (real agents — needs `ANTHROPIC_API_KEY`) |
| `DEEPTALK_ANTHROPIC_MODEL` | `claude-sonnet-4-6` | model for cloud agents (override if the alias errors) |
| `DEEPTALK_INTENT` | `heuristic` | `heuristic` (free) or `llm` (smarter; uses the provider) |
| `DEEPTALK_DIARIZE` | `off` | `off` or `vibevoice` (post-session diarization, GPU) |
| `DEEPTALK_RECORDING` | — | path to a recorded WAV to diarize on `/finalize` |
| `DEEPTALK_MAX_AGENT_CALLS` | `50` | per-session agent-call cap (`-1` = unlimited) |
| `DEEPTALK_AGENT_TIMEOUT` | `30` | per-agent timeout in seconds |
| `DEEPTALK_SESSION_ID` | `demo` | session id |
| `DEEPTALK_DB` | `deeptalk-demo.db` | SQLite path |
| `DEEPTALK_FIXTURE` | bundled sample | fixture path (when STT=fake) |
| `DEEPTALK_HOST` / `DEEPTALK_PORT` | `127.0.0.1` / `8000` | bind address |
| `ANTHROPIC_API_KEY` | — | required when `DEEPTALK_SEARCH_PROVIDER=anthropic` |

## UI dev mode (hot reload)

```bash
cd ui
VITE_WS_BASE=ws://127.0.0.1:8000 npm run dev   # Vite dev server on :5173
# run the Python server separately
```

## Tests

```bash
uv run pytest -q     # Python backend (130 tests)
cd ui && npm test    # UI (Vitest, 29 tests)
```

## Known gaps

- **nemotron** is wired but not yet validated on real hardware — the first GPU run may
  need NeMo-API / chunk-size tuning (see note above).
- **Auto-recording the live mic** for diarization isn't wired yet — diarization needs
  `DEEPTALK_RECORDING` pointed at an externally recorded WAV for now.
- The **mockup/diagram agent** (Phase 8) is optional and not built.
