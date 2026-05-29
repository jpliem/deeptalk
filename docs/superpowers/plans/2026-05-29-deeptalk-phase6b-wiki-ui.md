# DeepTalk Phase 6B — Session Wiki UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the session wiki in the UI. A "Build wiki" button calls `POST /finalize`, then `GET /wiki`, and renders topics / decisions / action items.

**Architecture:** `wiki.ts` adds `postFinalize` + `getWiki` (reusing `resolveHttpBase`). `WikiPanel` takes an `onFinalize` callback, runs it on click, and renders the returned `Wiki` (or an empty state). `App` wires `onFinalize` to `postFinalize(session) → getWiki(session)` and mounts the panel full-width below the two panes. Vitest with mocked fetch / injected callback.

**Tech Stack:** React 18 + TypeScript + Vitest (existing `ui/`).

---

## Roadmap context

Phase 6B completes spec §15 phase 6: the wiki (built in 6A) is now visible. Phases 1–6A on `main`. Remaining: Phase 7 (GPU lease / error hardening), Phase 8 (mockup agent).

## File Structure (Phase 6B)

```
deeptalk/ui/src/
  types.ts                       # MODIFY: add Wiki interface
  wiki.ts                        # NEW: postFinalize + getWiki
  WikiPanel.tsx                  # NEW
  App.tsx                        # MODIFY: mount WikiPanel
  styles.css                     # MODIFY: wiki styles
  __tests__/
    wiki.test.ts                 # NEW
    WikiPanel.test.tsx           # NEW
```

All commands run from `ui/` (`cd ui && ...`).

---

### Task 1: Wiki type + fetch helpers

**Files:**
- Modify: `ui/src/types.ts`
- Create: `ui/src/wiki.ts`
- Test: `ui/src/__tests__/wiki.test.ts`

- [ ] **Step 1: Append to `ui/src/types.ts`**

```ts
export interface Wiki {
  session_id: string
  topics: string[]
  decisions: string[]
  action_items: string[]
  created_at: number
}
```

- [ ] **Step 2: Write the failing test** — `ui/src/__tests__/wiki.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postFinalize, getWiki } from '../wiki'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('postFinalize', () => {
  it('POSTs the session_id to /finalize', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)
    await postFinalize('demo', 'http://h')
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('http://h/finalize')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ session_id: 'demo' })
  })
})

describe('getWiki', () => {
  it('returns the wiki json on 200', async () => {
    const wiki = { session_id: 'demo', topics: ['t'], decisions: ['d'], action_items: ['a'], created_at: 0 }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => wiki }))
    const got = await getWiki('demo', 'http://h')
    expect(got).toEqual(wiki)
  })

  it('returns null on 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    expect(await getWiki('demo', 'http://h')).toBeNull()
  })
})
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/wiki.test.ts`
Expected: FAIL — cannot resolve `../wiki`.

- [ ] **Step 4: Create `ui/src/wiki.ts`**

```ts
import { resolveHttpBase } from './ask'
import type { Wiki } from './types'

export async function postFinalize(sessionId: string, base?: string): Promise<void> {
  const res = await fetch(`${resolveHttpBase(base)}/finalize`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!res.ok) {
    throw new Error(`finalize failed: ${res.status}`)
  }
}

export async function getWiki(sessionId: string, base?: string): Promise<Wiki | null> {
  const res = await fetch(
    `${resolveHttpBase(base)}/wiki?session_id=${encodeURIComponent(sessionId)}`,
  )
  if (res.status === 404) {
    return null
  }
  if (!res.ok) {
    throw new Error(`get wiki failed: ${res.status}`)
  }
  return res.json() as Promise<Wiki>
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/wiki.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add ui/src/types.ts ui/src/wiki.ts ui/src/__tests__/wiki.test.ts
git commit -m "feat(ui): add Wiki type and finalize/getWiki helpers"
```

---

### Task 2: WikiPanel component

**Files:**
- Create: `ui/src/WikiPanel.tsx`
- Test: `ui/src/__tests__/WikiPanel.test.tsx`

- [ ] **Step 1: Write the failing test** — `ui/src/__tests__/WikiPanel.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WikiPanel } from '../WikiPanel'
import type { Wiki } from '../types'

const wiki: Wiki = {
  session_id: 'demo',
  topics: ['database choice'],
  decisions: ['use postgres'],
  action_items: ['set up CI'],
  created_at: 0,
}

describe('WikiPanel', () => {
  it('shows an empty state before building', () => {
    render(<WikiPanel onFinalize={vi.fn().mockResolvedValue(null)} />)
    expect(screen.getByText(/build a wiki/i)).toBeInTheDocument()
  })

  it('builds and renders topics, decisions, action items', async () => {
    const onFinalize = vi.fn().mockResolvedValue(wiki)
    render(<WikiPanel onFinalize={onFinalize} />)
    await userEvent.click(screen.getByRole('button', { name: /build/i }))
    expect(onFinalize).toHaveBeenCalled()
    expect(await screen.findByText('database choice')).toBeInTheDocument()
    expect(screen.getByText('use postgres')).toBeInTheDocument()
    expect(screen.getByText('set up CI')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/WikiPanel.test.tsx`
Expected: FAIL — cannot resolve `../WikiPanel`.

- [ ] **Step 3: Create `ui/src/WikiPanel.tsx`**

```tsx
import { useState } from 'react'
import type { Wiki } from './types'

function Section({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) {
    return null
  }
  return (
    <div className="wiki-section">
      <h3>{label}</h3>
      <ul>
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </div>
  )
}

export function WikiPanel({ onFinalize }: { onFinalize: () => Promise<Wiki | null> }) {
  const [wiki, setWiki] = useState<Wiki | null>(null)
  const [building, setBuilding] = useState(false)

  async function build() {
    setBuilding(true)
    try {
      setWiki(await onFinalize())
    } finally {
      setBuilding(false)
    }
  }

  return (
    <section className="wiki">
      <div className="wiki-head">
        <h2 className="pane-title">Session Wiki</h2>
        <button className="ask-button" onClick={build} disabled={building}>
          {building ? 'Building…' : 'Build wiki'}
        </button>
      </div>
      {wiki ? (
        <div className="wiki-body">
          <Section label="Topics" items={wiki.topics} />
          <Section label="Decisions" items={wiki.decisions} />
          <Section label="Action items" items={wiki.action_items} />
        </div>
      ) : (
        <p className="cards-empty">Build a wiki to summarize the session…</p>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/WikiPanel.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ui/src/WikiPanel.tsx ui/src/__tests__/WikiPanel.test.tsx
git commit -m "feat(ui): add WikiPanel component"
```

---

### Task 3: App integration + styles

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/styles.css`

- [ ] **Step 1: Wire `WikiPanel` into `ui/src/App.tsx`**

Add imports (with the existing ones):
```tsx
import { WikiPanel } from './WikiPanel'
import { postFinalize, getWiki } from './wiki'
```
Add a handler inside the `App` component (after `handleAsk`):
```tsx
  async function handleFinalize() {
    await postFinalize(SESSION_ID)
    return getWiki(SESSION_ID)
  }
```
Mount the panel just before the closing `</main>` (after the `.panes` div):
```tsx
      <WikiPanel onFinalize={handleFinalize} />
```

- [ ] **Step 2: Append to `ui/src/styles.css`**

```css
.wiki {
  margin-top: 2rem;
  border-top: 1px solid var(--line);
  padding-top: 1.5rem;
}

.wiki-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.wiki-body {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.25rem;
}

@media (max-width: 48rem) {
  .wiki-body { grid-template-columns: 1fr; }
}

.wiki-section h3 {
  margin: 0 0 0.4rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
}

.wiki-section ul {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.9rem;
  line-height: 1.5;
}
```

- [ ] **Step 3: Typecheck, test, build**

Run:
```bash
cd ui && npm run typecheck && npm test && npm run build
```
Expected: typecheck clean; all UI tests pass (24 prior + wiki 3 + WikiPanel 2 = 29); `dist/` built.

- [ ] **Step 4: End-to-end smoke (build the wiki via the running server, default fake)**

```bash
cd .. && rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-6b.log 2>&1 &
SERVER_PID=$!
sleep 8
curl -s -X POST http://127.0.0.1:8000/finalize -H 'content-type: application/json' -d '{"session_id":"demo"}' ; echo
curl -s "http://127.0.0.1:8000/wiki?session_id=demo" ; echo
kill $SERVER_PID 2>/dev/null
```
Expected: finalize `{"status":"ok"}`; wiki JSON with topics/decisions/action_items (fake-stub values). The browser's "Build wiki" button drives exactly this. Paste `/tmp/deeptalk-6b.log` tail on failure.

- [ ] **Step 5: Commit**

```bash
git add ui/src/App.tsx ui/src/styles.css
git commit -m "feat(ui): mount session wiki panel with build button"
```

---

## Self-Review

**Spec coverage (Phase 6B):** The session wiki (built by 6A's `/finalize`) is now visible — a "Build wiki" button finalizes the session and renders topics / decisions / action items (§7 Dashboard wiki surface), completing spec §15 phase 6. Mockup agent is Phase 8 — not a gap.

**Placeholder scan:** No TBD/TODO. Every step has exact code + commands + expected output.

**Type consistency:** UI `Wiki` (types.ts) mirrors the backend `Wiki.to_dict()` (session_id, topics, decisions, action_items, created_at). `postFinalize(sessionId, base?)` body `{session_id}` matches the backend `FinalizeRequest`; `getWiki` hits `/wiki?session_id=` (the backend route) and maps 404→null. `WikiPanel`'s `onFinalize: () => Promise<Wiki | null>` matches `App`'s `handleFinalize` (`postFinalize` then `getWiki`). `resolveHttpBase` is reused from `ask.ts`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase6b-wiki-ui.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
