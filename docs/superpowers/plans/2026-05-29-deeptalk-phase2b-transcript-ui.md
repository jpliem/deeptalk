# DeepTalk Phase 2B — Transcript UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Vite + React + TypeScript single-page UI that connects to `/ws/transcript` and renders the live transcript in real time, served as a static build by the existing FastAPI app. Plus a `README.md` documenting how to run everything.

**Architecture:** A small React app (`ui/`) with a `useTranscript` hook that opens a WebSocket to the FastAPI endpoint and accumulates `TranscriptEvent`s; a `TranscriptPane` renders them. The built static bundle (`ui/dist`) is mounted by `create_app` at `/` (after the API routes, so `/health` and `/ws/transcript` are not shadowed). All UI logic is unit-tested with Vitest + Testing Library using a mocked WebSocket — no running backend needed for tests.

**Tech Stack:** Vite 5, React 18, TypeScript 5, Vitest 2 + @testing-library/react + jsdom (UI); FastAPI `StaticFiles` (serving). Node/npm required on the dev machine.

---

## Roadmap context

Plan 2B of the Phase 2 pair (spec §15 phase 2). Phase 2A (live STT backend) is on `main`. This plan adds the visible UI + project README. After this, the spec's §15 phase 3 (Model Router + first agent) is next.

## File Structure (Phase 2B)

```
deeptalk/
  README.md                          # NEW: usage/run instructions
  ui/
    package.json                     # NEW
    tsconfig.json                    # NEW
    vite.config.ts                   # NEW (includes vitest config)
    index.html                       # NEW
    test/setup.ts                    # NEW
    src/
      main.tsx                       # NEW (rewired in Task 5)
      types.ts                       # NEW
      ws.ts                          # NEW
      useTranscript.ts               # NEW
      TranscriptPane.tsx             # NEW
      App.tsx                        # NEW
      styles.css                     # NEW
      __tests__/
        ws.test.ts                   # NEW
        useTranscript.test.tsx       # NEW
        TranscriptPane.test.tsx      # NEW
  src/deeptalk/server/app.py         # MODIFY: create_app gains ui_dir, mounts StaticFiles
  src/deeptalk/server/__main__.py    # MODIFY: pass ui/dist if built
  tests/test_static_ui.py            # NEW (python)
```

`node_modules/` and `dist/` are already in the repo `.gitignore`, so the built bundle is not committed — it is produced with `npm run build` on each machine (documented in the README).

---

### Task 1: Scaffold the Vite + React + TS app

**Files:** all under `ui/` (configs + minimal entry).

- [ ] **Step 1: Create `ui/package.json`**

```json
{
  "name": "deeptalk-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "test": "vitest run --passWithNoTests"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.8",
    "@testing-library/react": "^16.0.1",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.0",
    "typescript": "^5.6.2",
    "vite": "^5.4.6",
    "vitest": "^2.1.1"
  }
}
```

- [ ] **Step 2: Create `ui/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "test"]
}
```

- [ ] **Step 3: Create `ui/vite.config.ts`**

```ts
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist' },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.ts'],
  },
})
```

- [ ] **Step 4: Create `ui/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>DeepTalk</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `ui/test/setup.ts`**

```ts
import '@testing-library/jest-dom'
```

- [ ] **Step 6: Create a minimal `ui/src/main.tsx`** (rewired to use `App` in Task 5)

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <h1>DeepTalk</h1>
  </React.StrictMode>,
)
```

- [ ] **Step 7: Install and verify build + test harness**

Run (from `ui/`):
```bash
cd ui && npm install && npm run build && npm test
```
Expected: `npm install` succeeds; `npm run build` writes `dist/index.html` and assets; `npm test` exits 0 (`--passWithNoTests`, no tests yet). If `cd` is awkward in your tool, run `npm --prefix ui install` etc.

- [ ] **Step 8: Commit**

```bash
git add ui/package.json ui/package-lock.json ui/tsconfig.json ui/vite.config.ts ui/index.html ui/test/setup.ts ui/src/main.tsx
git commit -m "chore: scaffold Vite React TS UI"
```

---

### Task 2: Types + WebSocket URL helper

**Files:**
- Create: `ui/src/types.ts`
- Create: `ui/src/ws.ts`
- Test: `ui/src/__tests__/ws.test.ts`

- [ ] **Step 1: Write the failing test** — `ui/src/__tests__/ws.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { resolveWsUrl } from '../ws'

describe('resolveWsUrl', () => {
  it('builds the url from an explicit base', () => {
    expect(resolveWsUrl('demo', 'ws://127.0.0.1:8000')).toBe(
      'ws://127.0.0.1:8000/ws/transcript?session_id=demo',
    )
  })

  it('url-encodes the session id', () => {
    expect(resolveWsUrl('a b', 'ws://x')).toBe(
      'ws://x/ws/transcript?session_id=a%20b',
    )
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/ws.test.ts`
Expected: FAIL — cannot resolve `../ws`.

- [ ] **Step 3: Create `ui/src/types.ts`**

```ts
export interface TranscriptEvent {
  session_id: string
  ts: number
  text: string
  is_final: boolean
  source: 'live' | 'diarized'
  speaker: number | null
  span_id: string | null
}
```

- [ ] **Step 4: Create `ui/src/ws.ts`**

```ts
export function resolveWsUrl(sessionId: string, base?: string): string {
  const root =
    base ??
    (import.meta.env.VITE_WS_BASE as string | undefined) ??
    `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
  return `${root}/ws/transcript?session_id=${encodeURIComponent(sessionId)}`
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/ws.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add ui/src/types.ts ui/src/ws.ts ui/src/__tests__/ws.test.ts
git commit -m "feat(ui): add TranscriptEvent type and WebSocket URL helper"
```

---

### Task 3: useTranscript hook

**Files:**
- Create: `ui/src/useTranscript.ts`
- Test: `ui/src/__tests__/useTranscript.test.tsx`

- [ ] **Step 1: Write the failing test** — `ui/src/__tests__/useTranscript.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useTranscript } from '../useTranscript'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  onmessage: ((ev: { data: string }) => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }
  close() {}
}

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
})

function send(sock: FakeWebSocket, partial: Record<string, unknown>) {
  const ev = {
    session_id: 'demo',
    ts: 0,
    text: 'hi',
    is_final: true,
    source: 'live',
    speaker: null,
    span_id: null,
    ...partial,
  }
  act(() => sock.onmessage?.({ data: JSON.stringify(ev) }))
}

describe('useTranscript', () => {
  it('opens a socket to the resolved url', () => {
    renderHook(() => useTranscript('demo', 'ws://x'))
    expect(FakeWebSocket.instances[0].url).toBe(
      'ws://x/ws/transcript?session_id=demo',
    )
  })

  it('appends incoming events in order', async () => {
    const { result } = renderHook(() => useTranscript('demo', 'ws://x'))
    const sock = FakeWebSocket.instances[0]
    send(sock, { text: 'first' })
    send(sock, { text: 'second' })
    await waitFor(() => expect(result.current).toHaveLength(2))
    expect(result.current.map((e) => e.text)).toEqual(['first', 'second'])
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/useTranscript.test.tsx`
Expected: FAIL — cannot resolve `../useTranscript`.

- [ ] **Step 3: Create `ui/src/useTranscript.ts`**

```ts
import { useEffect, useState } from 'react'
import type { TranscriptEvent } from './types'
import { resolveWsUrl } from './ws'

export function useTranscript(sessionId: string, wsBase?: string): TranscriptEvent[] {
  const [events, setEvents] = useState<TranscriptEvent[]>([])

  useEffect(() => {
    const ws = new WebSocket(resolveWsUrl(sessionId, wsBase))
    ws.onmessage = (ev: MessageEvent) => {
      const data = JSON.parse(ev.data) as TranscriptEvent
      setEvents((prev) => [...prev, data])
    }
    return () => ws.close()
  }, [sessionId, wsBase])

  return events
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/useTranscript.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ui/src/useTranscript.ts ui/src/__tests__/useTranscript.test.tsx
git commit -m "feat(ui): add useTranscript WebSocket hook"
```

---

### Task 4: TranscriptPane component

**Files:**
- Create: `ui/src/TranscriptPane.tsx`
- Test: `ui/src/__tests__/TranscriptPane.test.tsx`

- [ ] **Step 1: Write the failing test** — `ui/src/__tests__/TranscriptPane.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TranscriptPane } from '../TranscriptPane'
import type { TranscriptEvent } from '../types'

function ev(over: Partial<TranscriptEvent> = {}): TranscriptEvent {
  return {
    session_id: 's',
    ts: 0,
    text: 'hello',
    is_final: true,
    source: 'live',
    speaker: null,
    span_id: null,
    ...over,
  }
}

describe('TranscriptPane', () => {
  it('shows an empty state when there are no events', () => {
    render(<TranscriptPane events={[]} />)
    expect(screen.getByText('Listening…')).toBeInTheDocument()
  })

  it('renders event text', () => {
    render(<TranscriptPane events={[ev({ text: 'world' })]} />)
    expect(screen.getByText('world')).toBeInTheDocument()
  })

  it('shows a speaker chip when speaker is set', () => {
    render(<TranscriptPane events={[ev({ speaker: 2 })]} />)
    expect(screen.getByText('S2')).toBeInTheDocument()
  })

  it('marks interim (non-final) lines', () => {
    const { container } = render(<TranscriptPane events={[ev({ is_final: false })]} />)
    expect(container.querySelector('.line.interim')).toBeTruthy()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/TranscriptPane.test.tsx`
Expected: FAIL — cannot resolve `../TranscriptPane`.

- [ ] **Step 3: Create `ui/src/TranscriptPane.tsx`**

```tsx
import type { TranscriptEvent } from './types'

export function TranscriptPane({ events }: { events: TranscriptEvent[] }) {
  if (events.length === 0) {
    return <p className="transcript-empty">Listening…</p>
  }
  return (
    <ol className="transcript">
      {events.map((e, i) => (
        <li key={i} className={`line ${e.is_final ? 'final' : 'interim'}`}>
          {e.speaker != null && <span className="speaker">S{e.speaker}</span>}
          <span className="text">{e.text}</span>
        </li>
      ))}
    </ol>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/TranscriptPane.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add ui/src/TranscriptPane.tsx ui/src/__tests__/TranscriptPane.test.tsx
git commit -m "feat(ui): add TranscriptPane component"
```

---

### Task 5: App wiring + styles

**Files:**
- Create: `ui/src/App.tsx`
- Create: `ui/src/styles.css`
- Modify: `ui/src/main.tsx` (render `App`, import styles)

- [ ] **Step 1: Create `ui/src/App.tsx`**

```tsx
import { useTranscript } from './useTranscript'
import { TranscriptPane } from './TranscriptPane'

const SESSION_ID =
  new URLSearchParams(window.location.search).get('session') ?? 'demo'

export default function App() {
  const events = useTranscript(SESSION_ID)
  return (
    <main className="app">
      <header className="app-header">
        <h1>DeepTalk</h1>
        <span className="session">session · {SESSION_ID}</span>
      </header>
      <TranscriptPane events={events} />
    </main>
  )
}
```

- [ ] **Step 2: Create `ui/src/styles.css`** (intentional, not a template default — dark editorial transcript)

```css
:root {
  --bg: oklch(18% 0.01 260);
  --surface: oklch(23% 0.015 260);
  --text: oklch(94% 0.01 260);
  --muted: oklch(62% 0.02 260);
  --accent: oklch(72% 0.16 200);
  --line: oklch(30% 0.02 260);
  --font: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: ui-monospace, "SF Mono", "JetBrains Mono", monospace;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
}

.app {
  max-width: 56rem;
  margin: 0 auto;
  padding: 2rem 1.5rem 6rem;
}

.app-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
}

.app-header h1 {
  margin: 0;
  font-size: clamp(1.5rem, 1rem + 2vw, 2.25rem);
  letter-spacing: -0.02em;
}

.session {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 0.85rem;
}

.transcript-empty {
  color: var(--muted);
  font-family: var(--mono);
  padding: 3rem 0;
  text-align: center;
}

.transcript {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.line {
  display: flex;
  gap: 0.75rem;
  align-items: baseline;
  padding: 0.5rem 0.75rem;
  background: var(--surface);
  border-radius: 0.5rem;
  line-height: 1.5;
  animation: rise 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.line.interim { opacity: 0.55; }

.speaker {
  flex: none;
  font-family: var(--mono);
  font-size: 0.7rem;
  color: var(--bg);
  background: var(--accent);
  padding: 0.1rem 0.4rem;
  border-radius: 0.35rem;
}

.text { color: var(--text); }

@keyframes rise {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .line { animation: none; }
}
```

- [ ] **Step 3: Rewire `ui/src/main.tsx`** to exactly:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

- [ ] **Step 4: Typecheck, test, and build**

Run:
```bash
cd ui && npm run typecheck && npm test && npm run build
```
Expected: typecheck clean; all Vitest tests pass (ws + useTranscript + TranscriptPane = 8 tests); `dist/` produced.

- [ ] **Step 5: Commit**

```bash
git add ui/src/App.tsx ui/src/styles.css ui/src/main.tsx
git commit -m "feat(ui): wire App with transcript pane and styles"
```

---

### Task 6: Serve the UI from FastAPI

**Files:**
- Modify: `src/deeptalk/server/app.py`
- Test: `tests/test_static_ui.py`

- [ ] **Step 1: Write the failing test** — `tests/test_static_ui.py`:

```python
from fastapi.testclient import TestClient

from deeptalk.bus import EventBus
from deeptalk.server.app import create_app
from deeptalk.transcript.store import TranscriptStore


def _store(tmp_path):
    return TranscriptStore(str(tmp_path / "t.db"))


def test_serves_ui_index_when_dir_given(tmp_path):
    ui = tmp_path / "dist"
    ui.mkdir()
    (ui / "index.html").write_text("<h1>DeepTalk UI</h1>")
    app = create_app(store=_store(tmp_path), bus=EventBus(), ui_dir=str(ui))
    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert "DeepTalk UI" in root.text


def test_api_routes_not_shadowed_by_ui_mount(tmp_path):
    ui = tmp_path / "dist"
    ui.mkdir()
    (ui / "index.html").write_text("<h1>UI</h1>")
    app = create_app(store=_store(tmp_path), bus=EventBus(), ui_dir=str(ui))
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}


def test_no_ui_when_dir_missing(tmp_path):
    app = create_app(store=_store(tmp_path), bus=EventBus(), ui_dir=str(tmp_path / "nope"))
    client = TestClient(app)

    assert client.get("/").status_code == 404
    assert client.get("/health").status_code == 200
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_static_ui.py -v`
Expected: FAIL — `create_app()` has no `ui_dir` parameter.

- [ ] **Step 3: Update `src/deeptalk/server/app.py`**

Add these imports near the top (keep existing ones):
```python
from pathlib import Path

from fastapi.staticfiles import StaticFiles
```
Change the `create_app` signature from:
```python
def create_app(
    store: TranscriptStore,
    bus: EventBus,
    lifespan: Callable[[FastAPI], Any] | None = None,
) -> FastAPI:
```
to:
```python
def create_app(
    store: TranscriptStore,
    bus: EventBus,
    lifespan: Callable[[FastAPI], Any] | None = None,
    ui_dir: str | None = None,
) -> FastAPI:
```
Then, at the very END of the function body, immediately before `return app`, add:
```python
    # Mount the built UI LAST so /health and /ws/transcript take precedence.
    if ui_dir and Path(ui_dir).is_dir():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
```
Leave `stream_transcript`, `/health`, and the websocket route unchanged.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_static_ui.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Full suite**

Run: `uv run pytest -q`
Expected: all green (Phase 2A's 42 + these 3 = 45).

- [ ] **Step 6: Commit**

```bash
git add src/deeptalk/server/app.py tests/test_static_ui.py
git commit -m "feat: serve built UI as static files from create_app"
```

---

### Task 7: Entrypoint serves UI + README

**Files:**
- Modify: `src/deeptalk/server/__main__.py`
- Create: `README.md`

- [ ] **Step 1: Update `src/deeptalk/server/__main__.py`** to pass the built UI dir

Add this import with the others at the top:
```python
from pathlib import Path
```
In `main()`, change the line:
```python
    app = create_app(store=store, bus=bus, lifespan=lifespan)
```
to:
```python
    ui_dist = Path(__file__).resolve().parents[3] / "ui" / "dist"
    app = create_app(
        store=store,
        bus=bus,
        lifespan=lifespan,
        ui_dir=str(ui_dist) if ui_dist.is_dir() else None,
    )
```
Leave the rest of the file unchanged.

- [ ] **Step 2: Create `README.md`**

````markdown
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
````

- [ ] **Step 3: Full Python suite + UI tests + smoke**

Run:
```bash
uv run pytest -q
cd ui && npm test && npm run build && cd ..
```
Expected: Python all green; UI 8 tests pass; `ui/dist` built.

Then smoke the served UI:
```bash
rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-2b.log 2>&1 &
SERVER_PID=$!
sleep 6
curl -s http://127.0.0.1:8000/health
echo
curl -s http://127.0.0.1:8000/ | grep -o "<title>DeepTalk</title>" || echo "index not served"
kill $SERVER_PID 2>/dev/null
```
Expected: `{"status":"ok"}` and `<title>DeepTalk</title>` (the built index is served).
If `dist` was built, the root returns the app shell. Paste `/tmp/deeptalk-2b.log` tail on failure.

- [ ] **Step 4: Commit**

```bash
git add src/deeptalk/server/__main__.py README.md
git commit -m "feat: serve built UI from entrypoint; add README usage docs"
```

---

## Self-Review

**Spec coverage (Phase 2B):** Delivers the spec §7 Dashboard UI's first surface — the
live transcript pane — over the existing WebSocket, served by the existing app
(spec's single-box, localhost-web-app decision). Agent cards + wiki tabs are Phase 3+,
not gaps. README documents run/usage as requested.

**Placeholder scan:** No TBD/TODO. Every file has complete content; every step has an
exact command + expected result.

**Type consistency:** UI `TranscriptEvent` (types.ts) mirrors the backend dataclass
fields exactly (`session_id, ts, text, is_final, source, speaker, span_id`).
`resolveWsUrl(sessionId, base?)` is used identically by the ws test and
`useTranscript`. `useTranscript(sessionId, wsBase?)` signature matches its test and
`App` usage. `create_app(store, bus, lifespan=None, ui_dir=None)` is consistent
between Task 6's change, the entrypoint (Task 7), and the static tests. The endpoint
path `/ws/transcript?session_id=` matches the Phase 1 server route.

**Mount ordering:** StaticFiles is mounted at `/` only after `/health` and
`/ws/transcript` are registered, and the tests assert `/health` is not shadowed.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase2b-transcript-ui.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
