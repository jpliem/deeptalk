# DeepTalk Phase 3B — Ask Box + Artifact Cards (UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the search agent's answers in the React UI. Add an ask box that POSTs to `/ask`, a `useArtifacts` hook that streams artifacts over `/ws/artifacts`, and `ArtifactCard`s that show the answer + citations (or an error). Lay them out next to the live transcript.

**Architecture:** `AskBox` triggers `postAsk()` (HTTP POST `/ask`). The backend runs the search and publishes the resulting `Artifact` on the artifact bus; `useArtifacts` (a WebSocket hook mirroring `useTranscript`) receives it live and accumulates the list, which `App` renders as `ArtifactCard`s. All UI logic is unit-tested with Vitest using a mocked WebSocket and a mocked `fetch` — no backend needed for tests.

**Tech Stack:** Vite 5, React 18, TypeScript 5, Vitest 2 + @testing-library/react (already set up in `ui/` from Phase 2B).

---

## Roadmap context

Plan 3B completes spec §15 phase 3 (Model Router + first agent end-to-end, now visible in the UI). Phase 3A (router + search agent + `/ask` + `/ws/artifacts`) is on `main`. Next is Phase 4 (intent detector + orchestrator: auto-fire agents from the transcript + dedup).

## File Structure (Phase 3B)

```
deeptalk/ui/src/
  types.ts                       # MODIFY: add Citation, Artifact
  ws.ts                          # MODIFY: generalize to wsUrl(path, sessionId, base?)
  ask.ts                         # NEW: postAsk + resolveHttpBase
  useArtifacts.ts                # NEW: WebSocket hook for /ws/artifacts
  ArtifactCard.tsx               # NEW: renders a search artifact
  AskBox.tsx                     # NEW: query input + submit
  App.tsx                        # MODIFY: two-pane layout (transcript + insights)
  styles.css                     # MODIFY: card + ask-box + layout styles
  __tests__/
    ask.test.ts                  # NEW
    useArtifacts.test.tsx        # NEW
    ArtifactCard.test.tsx        # NEW
    AskBox.test.tsx              # NEW
    ws.test.ts                   # MODIFY: keep existing + test wsUrl
```

All commands run from `ui/` (`cd ui && ...`).

---

### Task 1: Types + generalized ws helper + ask helper

**Files:**
- Modify: `ui/src/types.ts`
- Modify: `ui/src/ws.ts`
- Create: `ui/src/ask.ts`
- Modify: `ui/src/__tests__/ws.test.ts`
- Create: `ui/src/__tests__/ask.test.ts`

- [ ] **Step 1: Append to `ui/src/types.ts`** (keep the existing `TranscriptEvent`):

```ts
export interface Citation {
  title: string
  url: string
}

export interface SearchPayload {
  answer?: string
  citations?: Citation[]
  model?: string
}

export interface Artifact {
  id: string
  session_id: string
  agent: string
  status: 'done' | 'error'
  title: string
  payload: SearchPayload
  created_at: number
  latency_ms: number | null
  error: string | null
}
```

- [ ] **Step 2: Update `ui/src/__tests__/ws.test.ts`** — replace its contents with:

```ts
import { describe, it, expect } from 'vitest'
import { resolveWsUrl, wsUrl } from '../ws'

describe('wsUrl', () => {
  it('builds an arbitrary ws path with session', () => {
    expect(wsUrl('/ws/artifacts', 'demo', 'ws://x')).toBe(
      'ws://x/ws/artifacts?session_id=demo',
    )
  })
  it('url-encodes the session id', () => {
    expect(wsUrl('/ws/transcript', 'a b', 'ws://x')).toBe(
      'ws://x/ws/transcript?session_id=a%20b',
    )
  })
})

describe('resolveWsUrl (transcript back-compat)', () => {
  it('builds the transcript url from an explicit base', () => {
    expect(resolveWsUrl('demo', 'ws://127.0.0.1:8000')).toBe(
      'ws://127.0.0.1:8000/ws/transcript?session_id=demo',
    )
  })
})
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/ws.test.ts`
Expected: FAIL — `wsUrl` is not exported yet.

- [ ] **Step 4: Update `ui/src/ws.ts`** — replace its contents with:

```ts
export function wsUrl(path: string, sessionId: string, base?: string): string {
  const root =
    base ??
    (import.meta.env.VITE_WS_BASE as string | undefined) ??
    `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
  return `${root}${path}?session_id=${encodeURIComponent(sessionId)}`
}

export function resolveWsUrl(sessionId: string, base?: string): string {
  return wsUrl('/ws/transcript', sessionId, base)
}
```

- [ ] **Step 5: Write the failing ask test** — `ui/src/__tests__/ask.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postAsk, resolveHttpBase } from '../ask'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('resolveHttpBase', () => {
  it('uses the explicit base when given', () => {
    expect(resolveHttpBase('http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000')
  })
})

describe('postAsk', () => {
  it('POSTs session_id and query and returns json', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'x1', status: 'done' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await postAsk('demo', 'what is rust', 'http://h')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('http://h/ask')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ session_id: 'demo', query: 'what is rust' })
    expect(result).toEqual({ id: 'x1', status: 'done' })
  })

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    await expect(postAsk('demo', 'q', 'http://h')).rejects.toThrow('503')
  })
})
```

- [ ] **Step 6: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/ask.test.ts`
Expected: FAIL — cannot resolve `../ask`.

- [ ] **Step 7: Create `ui/src/ask.ts`**

```ts
export function resolveHttpBase(base?: string): string {
  return (
    base ??
    (import.meta.env.VITE_HTTP_BASE as string | undefined) ??
    window.location.origin
  )
}

export interface AskResult {
  id: string
  status: string
}

export async function postAsk(
  sessionId: string,
  query: string,
  base?: string,
): Promise<AskResult> {
  const res = await fetch(`${resolveHttpBase(base)}/ask`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, query }),
  })
  if (!res.ok) {
    throw new Error(`ask failed: ${res.status}`)
  }
  return res.json() as Promise<AskResult>
}
```

- [ ] **Step 8: Run both test files**

Run: `cd ui && npx vitest run src/__tests__/ws.test.ts src/__tests__/ask.test.ts`
Expected: PASS (ws 3 + ask 3).

- [ ] **Step 9: Commit**

```bash
git add ui/src/types.ts ui/src/ws.ts ui/src/ask.ts ui/src/__tests__/ws.test.ts ui/src/__tests__/ask.test.ts
git commit -m "feat(ui): add Artifact types, generalized wsUrl, postAsk helper"
```

---

### Task 2: useArtifacts hook

**Files:**
- Create: `ui/src/useArtifacts.ts`
- Test: `ui/src/__tests__/useArtifacts.test.tsx`

- [ ] **Step 1: Write the failing test** — `ui/src/__tests__/useArtifacts.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useArtifacts } from '../useArtifacts'

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

function sendArtifact(sock: FakeWebSocket, partial: Record<string, unknown>) {
  const art = {
    id: 'a1',
    session_id: 'demo',
    agent: 'search',
    status: 'done',
    title: 'q',
    payload: { answer: 'A', citations: [] },
    created_at: 0,
    latency_ms: null,
    error: null,
    ...partial,
  }
  act(() => sock.onmessage?.({ data: JSON.stringify(art) }))
}

describe('useArtifacts', () => {
  it('connects to the artifacts ws path', () => {
    renderHook(() => useArtifacts('demo', 'ws://x'))
    expect(FakeWebSocket.instances[0].url).toBe('ws://x/ws/artifacts?session_id=demo')
  })

  it('accumulates incoming artifacts', async () => {
    const { result } = renderHook(() => useArtifacts('demo', 'ws://x'))
    const sock = FakeWebSocket.instances[0]
    sendArtifact(sock, { id: 'a1' })
    sendArtifact(sock, { id: 'a2' })
    await waitFor(() => expect(result.current).toHaveLength(2))
    expect(result.current.map((a) => a.id)).toEqual(['a1', 'a2'])
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/useArtifacts.test.tsx`
Expected: FAIL — cannot resolve `../useArtifacts`.

- [ ] **Step 3: Create `ui/src/useArtifacts.ts`**

```ts
import { useEffect, useState } from 'react'
import type { Artifact } from './types'
import { wsUrl } from './ws'

export function useArtifacts(sessionId: string, wsBase?: string): Artifact[] {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])

  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/artifacts', sessionId, wsBase))
    ws.onmessage = (ev: MessageEvent) => {
      const data = JSON.parse(ev.data) as Artifact
      setArtifacts((prev) => [...prev, data])
    }
    return () => ws.close()
  }, [sessionId, wsBase])

  return artifacts
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/useArtifacts.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ui/src/useArtifacts.ts ui/src/__tests__/useArtifacts.test.tsx
git commit -m "feat(ui): add useArtifacts WebSocket hook"
```

---

### Task 3: ArtifactCard component

**Files:**
- Create: `ui/src/ArtifactCard.tsx`
- Test: `ui/src/__tests__/ArtifactCard.test.tsx`

- [ ] **Step 1: Write the failing test** — `ui/src/__tests__/ArtifactCard.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ArtifactCard } from '../ArtifactCard'
import type { Artifact } from '../types'

function art(over: Partial<Artifact> = {}): Artifact {
  return {
    id: 'a1',
    session_id: 'demo',
    agent: 'search',
    status: 'done',
    title: 'what is rust',
    payload: { answer: 'Rust is a systems language', citations: [{ title: 'Rust', url: 'https://rust-lang.org' }] },
    created_at: 0,
    latency_ms: null,
    error: null,
    ...over,
  }
}

describe('ArtifactCard', () => {
  it('renders the query title and answer', () => {
    render(<ArtifactCard artifact={art()} />)
    expect(screen.getByText('what is rust')).toBeInTheDocument()
    expect(screen.getByText('Rust is a systems language')).toBeInTheDocument()
  })

  it('renders citations as links', () => {
    render(<ArtifactCard artifact={art()} />)
    const link = screen.getByRole('link', { name: 'Rust' })
    expect(link).toHaveAttribute('href', 'https://rust-lang.org')
  })

  it('shows the agent badge', () => {
    render(<ArtifactCard artifact={art()} />)
    expect(screen.getByText('search')).toBeInTheDocument()
  })

  it('renders an error state', () => {
    const { container } = render(
      <ArtifactCard artifact={art({ status: 'error', payload: {}, error: 'api down' })} />,
    )
    expect(screen.getByText('api down')).toBeInTheDocument()
    expect(container.querySelector('.card.error')).toBeTruthy()
  })
}
)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/ArtifactCard.test.tsx`
Expected: FAIL — cannot resolve `../ArtifactCard`.

- [ ] **Step 3: Create `ui/src/ArtifactCard.tsx`**

```tsx
import type { Artifact } from './types'

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const isError = artifact.status === 'error'
  return (
    <article className={`card ${isError ? 'error' : ''}`}>
      <header className="card-head">
        <span className="badge">{artifact.agent}</span>
        <h3 className="card-title">{artifact.title}</h3>
      </header>
      {isError ? (
        <p className="card-error">{artifact.error ?? 'Something went wrong'}</p>
      ) : (
        <>
          {artifact.payload.answer && <p className="card-answer">{artifact.payload.answer}</p>}
          {artifact.payload.citations && artifact.payload.citations.length > 0 && (
            <ul className="card-sources">
              {artifact.payload.citations.map((c, i) => (
                <li key={i}>
                  <a href={c.url} target="_blank" rel="noopener noreferrer">
                    {c.title}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </article>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/ArtifactCard.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add ui/src/ArtifactCard.tsx ui/src/__tests__/ArtifactCard.test.tsx
git commit -m "feat(ui): add ArtifactCard component"
```

---

### Task 4: AskBox component

**Files:**
- Create: `ui/src/AskBox.tsx`
- Test: `ui/src/__tests__/AskBox.test.tsx`

`AskBox` is presentational: it takes `onAsk(query)` and a `pending` flag. `App` wires it
to `postAsk`.

- [ ] **Step 1: Write the failing test** — `ui/src/__tests__/AskBox.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AskBox } from '../AskBox'

describe('AskBox', () => {
  it('calls onAsk with the typed query on submit', async () => {
    const onAsk = vi.fn().mockResolvedValue(undefined)
    render(<AskBox onAsk={onAsk} pending={false} />)
    await userEvent.type(screen.getByPlaceholderText(/ask/i), 'what is rust')
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))
    expect(onAsk).toHaveBeenCalledWith('what is rust')
  })

  it('does not call onAsk for an empty query', async () => {
    const onAsk = vi.fn()
    render(<AskBox onAsk={onAsk} pending={false} />)
    await userEvent.click(screen.getByRole('button', { name: /ask/i }))
    expect(onAsk).not.toHaveBeenCalled()
  })

  it('disables the button while pending', () => {
    render(<AskBox onAsk={vi.fn()} pending={true} />)
    expect(screen.getByRole('button', { name: /asking/i })).toBeDisabled()
  })
})
```

- [ ] **Step 2: Add the test dependency `@testing-library/user-event`**

Run: `cd ui && npm install -D @testing-library/user-event@^14.5.2`

- [ ] **Step 3: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/AskBox.test.tsx`
Expected: FAIL — cannot resolve `../AskBox`.

- [ ] **Step 4: Create `ui/src/AskBox.tsx`**

```tsx
import { useState, type FormEvent } from 'react'

export function AskBox({
  onAsk,
  pending,
}: {
  onAsk: (query: string) => void | Promise<void>
  pending: boolean
}) {
  const [query, setQuery] = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || pending) {
      return
    }
    await onAsk(trimmed)
    setQuery('')
  }

  return (
    <form className="ask-box" onSubmit={handleSubmit}>
      <input
        className="ask-input"
        placeholder="Ask the meeting assistant…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={pending}
      />
      <button className="ask-button" type="submit" disabled={pending}>
        {pending ? 'Asking…' : 'Ask'}
      </button>
    </form>
  )
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/AskBox.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add ui/package.json ui/package-lock.json ui/src/AskBox.tsx ui/src/__tests__/AskBox.test.tsx
git commit -m "feat(ui): add AskBox component"
```

---

### Task 5: App layout integration + styles

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/styles.css`

- [ ] **Step 1: Replace `ui/src/App.tsx`** with:

```tsx
import { useState } from 'react'
import { useTranscript } from './useTranscript'
import { useArtifacts } from './useArtifacts'
import { TranscriptPane } from './TranscriptPane'
import { ArtifactCard } from './ArtifactCard'
import { AskBox } from './AskBox'
import { postAsk } from './ask'

const SESSION_ID =
  new URLSearchParams(window.location.search).get('session') ?? 'demo'

export default function App() {
  const events = useTranscript(SESSION_ID)
  const artifacts = useArtifacts(SESSION_ID)
  const [pending, setPending] = useState(false)

  async function handleAsk(query: string) {
    setPending(true)
    try {
      await postAsk(SESSION_ID, query)
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="app">
      <header className="app-header">
        <h1>DeepTalk</h1>
        <span className="session">session · {SESSION_ID}</span>
      </header>
      <div className="panes">
        <section className="pane">
          <h2 className="pane-title">Transcript</h2>
          <TranscriptPane events={events} />
        </section>
        <section className="pane">
          <h2 className="pane-title">Insights</h2>
          <AskBox onAsk={handleAsk} pending={pending} />
          <div className="cards">
            {artifacts.length === 0 && (
              <p className="cards-empty">Ask a question to get a sourced answer…</p>
            )}
            {artifacts.map((a) => (
              <ArtifactCard key={a.id} artifact={a} />
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
```

- [ ] **Step 2: Append to `ui/src/styles.css`** (layout + ask box + cards):

```css
.panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  align-items: start;
}

@media (max-width: 48rem) {
  .panes { grid-template-columns: 1fr; }
}

.pane-title {
  margin: 0 0 0.75rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.ask-box {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.ask-input {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 0.6rem 0.8rem;
  font: inherit;
}

.ask-input:focus {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.ask-button {
  background: var(--accent);
  color: var(--bg);
  border: none;
  border-radius: 0.5rem;
  padding: 0 1rem;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.ask-button:disabled { opacity: 0.5; cursor: default; }

.cards { display: flex; flex-direction: column; gap: 0.75rem; }

.cards-empty {
  color: var(--muted);
  font-family: var(--mono);
  font-size: 0.85rem;
}

.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.6rem;
  padding: 0.9rem 1rem;
  animation: rise 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.card.error { border-color: oklch(55% 0.18 25); }

.card-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.badge {
  font-family: var(--mono);
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--bg);
  background: var(--accent);
  padding: 0.1rem 0.4rem;
  border-radius: 0.3rem;
}

.card-title { margin: 0; font-size: 0.95rem; }
.card-answer { margin: 0.25rem 0 0.6rem; line-height: 1.55; }
.card-error { margin: 0.25rem 0 0; color: oklch(72% 0.16 25); }

.card-sources {
  margin: 0;
  padding-left: 1rem;
  font-size: 0.85rem;
}

.card-sources a { color: var(--accent); }

@media (prefers-reduced-motion: reduce) {
  .card { animation: none; }
}
```

- [ ] **Step 3: Typecheck, test, build**

Run:
```bash
cd ui && npm run typecheck && npm test && npm run build
```
Expected: typecheck clean; all Vitest tests pass (Phase 2B's 8 + ws extra + ask 3 + useArtifacts 2 + ArtifactCard 4 + AskBox 3); `dist/` built. If typecheck flags an unused import, fix minimally and report.

- [ ] **Step 4: Backend smoke (cards appear from a real /ask via fake provider)**

```bash
cd .. && rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-3b.log 2>&1 &
SERVER_PID=$!
sleep 6
curl -s -X POST http://127.0.0.1:8000/ask -H 'content-type: application/json' -d '{"session_id":"demo","query":"what is rust"}'
echo
# the artifact is now stored; confirm /ws/artifacts backlog would serve it:
uv run python -c "from deeptalk.artifacts.store import ArtifactStore; a=ArtifactStore('deeptalk-demo.db').all_artifacts('demo'); print(len(a), a[0].status if a else '-')"
kill $SERVER_PID 2>/dev/null
```
Expected: `/ask` returns `{"id":...,"status":"done"}`; the python check prints `1 done`. Paste `/tmp/deeptalk-3b.log` tail on failure.

- [ ] **Step 5: Commit**

```bash
git add ui/src/App.tsx ui/src/styles.css
git commit -m "feat(ui): two-pane layout with ask box and artifact cards"
```

---

## Self-Review

**Spec coverage (Phase 3B):** Completes spec §15 phase 3 — the search agent's answers now render as cards driven by `/ws/artifacts`, triggered by an ask box hitting `/ask`. This is the §7 Dashboard's second surface (artifact cards) alongside the transcript pane. Auto-firing from the transcript is Phase 4 — not a gap.

**Placeholder scan:** No TBD/TODO. Every file has complete content; every step has an exact command + expected result.

**Type consistency:** UI `Artifact`/`Citation`/`SearchPayload` (types.ts) mirror the backend `Artifact.to_dict()` shape (id, session_id, agent, status, title, payload{answer,citations,model}, created_at, latency_ms, error). `wsUrl(path, sessionId, base?)` is used by `useArtifacts` (`/ws/artifacts`) and by `resolveWsUrl` (`/ws/transcript`, back-compat preserved so Phase 2B's `useTranscript` is untouched). `postAsk(sessionId, query, base?)` body `{session_id, query}` matches the backend `AskRequest`. `AskBox` props (`onAsk`, `pending`) match `App`'s usage; `ArtifactCard` `{artifact}` prop matches.

**Behavior:** `App` posts via `postAsk`; the artifact arrives over `/ws/artifacts` (published by `run_search` during `/ask`), so cards render live. `pending` disables the box during the request.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase3b-ask-cards-ui.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
