# DeepTalk

Real-time meeting assistant. DeepTalk listens to a discussion, transcribes it live,
and (in later phases) runs AI agents that surface search answers, pros/cons, plans,
and mockups onto a live dashboard — then builds a session wiki.

This repo currently implements **Phase 1** (transcript spine) and **Phase 2**
(live audio → STT + transcript UI). See `docs/superpowers/specs` and
`docs/superpowers/plans` for the design and roadmap.

## Architecture (single box)

```
mic → STT (nemotron, live)  →  transcript store (SQLite, source of truth)
                              →  event bus  →  WebSocket  →  React UI
```

Audio stays on the machine. Cloud agents (later phases) receive text only. The STT
layer is swappable behind one interface: a fixture replayer (`fake`) for dev on any
machine, and NeMo nemotron (`nemotron`) on an NVIDIA GPU.

## Requirements

- Python 3.12 + [uv](https://docs.astral.sh/uv/)
- Node.js 18+ + npm (for the UI)
- For real speech-to-text: an NVIDIA GPU (CUDA) — the `[gpu]` extra (Linux only)

## Quickstart (dev, no GPU)

Runs the fixture-replay demo and the live transcript UI on any machine.

```bash
# 1. Python deps
uv sync

# 2. Build the UI
cd ui && npm install && npm run build && cd ..

# 3. Run the server (replays a sample meeting fixture)
uv run python -m deeptalk.server

# 4. Open the UI
#    http://127.0.0.1:8000/        (transcript appears live)
#    http://127.0.0.1:8000/health  -> {"status":"ok"}
```

### UI dev mode (hot reload)

```bash
cd ui
VITE_WS_BASE=ws://127.0.0.1:8000 npm run dev   # Vite dev server on :5173
# run the Python server separately (step 3 above)
```

## Real speech-to-text (on the NVIDIA box)

```bash
git pull
uv sync --extra gpu                 # installs torch + nemo_toolkit (Linux/CUDA)
cd ui && npm install && npm run build && cd ..

# live microphone:
DEEPTALK_STT=nemotron DEEPTALK_AUDIO=mic uv run python -m deeptalk.server

# or transcribe a 16 kHz mono WAV file:
DEEPTALK_STT=nemotron DEEPTALK_AUDIO=file DEEPTALK_AUDIO_FILE=/path/to/audio.wav \
  uv run python -m deeptalk.server
```

> Note: cache-aware streaming models expect chunks aligned to the encoder's
> streaming step. If transcription is empty or errors on first run, tune `chunk_ms`
> / `att_context_size` in `src/deeptalk/stt/nemo_recognizer.py`.

## Configuration (environment variables)

| Variable | Default | Meaning |
|----------|---------|---------|
| `DEEPTALK_STT` | `fake` | `fake` (fixture replay) or `nemotron` (real STT) |
| `DEEPTALK_AUDIO` | `file` | `file` or `mic` (used when STT=nemotron) |
| `DEEPTALK_AUDIO_FILE` | — | path to a 16 kHz mono WAV (when AUDIO=file) |
| `DEEPTALK_SESSION_ID` | `demo` | session id for the transcript |
| `DEEPTALK_DB` | `deeptalk-demo.db` | SQLite path |
| `DEEPTALK_FIXTURE` | bundled sample | fixture path (when STT=fake) |
| `DEEPTALK_HOST` | `127.0.0.1` | bind host |
| `DEEPTALK_PORT` | `8000` | bind port |

## Tests

```bash
uv run pytest -q          # Python backend
cd ui && npm test         # UI (Vitest)
```
