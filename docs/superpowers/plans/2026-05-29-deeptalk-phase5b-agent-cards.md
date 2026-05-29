# DeepTalk Phase 5B — Pros/Cons + Planning Cards (UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render pros/cons and planning artifacts in the UI. `ArtifactCard` already shows search answers + citations and errors; extend it to render `proscons` (pros / cons / recommendation) and `planning` (ordered steps) payloads, selected by `artifact.agent`.

**Architecture:** Widen the UI `ArtifactPayload` type to include the optional `pros`/`cons`/`recommendation`/`steps` fields the backend produces. `ArtifactCard` branches on `artifact.agent` (after the error check) to a small body renderer per agent; the existing search rendering stays the default. All component-tested with Vitest.

**Tech Stack:** React 18 + TypeScript + Vitest (existing `ui/`).

---

## Roadmap context

Phase 5B completes spec §15 phase 5: the pros/cons + planning agents from 5A now have visible cards. Phases 1–5A are on `main`. The mockup agent (Phase 8) and VibeVoice diarization + wiki (Phase 6) come later.

## File Structure (Phase 5B)

```
deeptalk/ui/src/
  types.ts                          # MODIFY: widen payload (pros/cons/recommendation/steps)
  ArtifactCard.tsx                  # MODIFY: render proscons + planning bodies
  styles.css                        # MODIFY: proscons grid + steps styles
  __tests__/ArtifactCard.test.tsx   # MODIFY: add proscons + planning tests
```

All commands run from `ui/` (`cd ui && ...`).

---

### Task 1: Widen payload type + multi-agent ArtifactCard

**Files:**
- Modify: `ui/src/types.ts`
- Modify: `ui/src/ArtifactCard.tsx`
- Modify: `ui/src/__tests__/ArtifactCard.test.tsx`

- [ ] **Step 1: Widen the payload type** — in `ui/src/types.ts`, replace the `SearchPayload` interface with a broader `ArtifactPayload` and point `Artifact.payload` at it:

Replace:
```ts
export interface SearchPayload {
  answer?: string
  citations?: Citation[]
  model?: string
}
```
with:
```ts
export interface ArtifactPayload {
  answer?: string
  citations?: Citation[]
  model?: string
  pros?: string[]
  cons?: string[]
  recommendation?: string
  steps?: string[]
}
```
And change the `Artifact` interface's `payload: SearchPayload` line to:
```ts
  payload: ArtifactPayload
```
(Keep the `Citation` interface and everything else unchanged. `SearchPayload` is only referenced by `Artifact`, so the rename is safe.)

- [ ] **Step 2: Add failing tests** — append inside the `describe('ArtifactCard', ...)` block in `ui/src/__tests__/ArtifactCard.test.tsx`:

```tsx
  it('renders pros, cons, and recommendation for a proscons artifact', () => {
    render(
      <ArtifactCard
        artifact={art({
          agent: 'proscons',
          title: 'kafka or rabbitmq',
          payload: { pros: ['fast'], cons: ['complex'], recommendation: 'use kafka' },
        })}
      />,
    )
    expect(screen.getByText('fast')).toBeInTheDocument()
    expect(screen.getByText('complex')).toBeInTheDocument()
    expect(screen.getByText(/use kafka/)).toBeInTheDocument()
  })

  it('renders ordered steps for a planning artifact', () => {
    render(
      <ArtifactCard
        artifact={art({ agent: 'planning', title: 'build auth', payload: { steps: ['one', 'two'] } })}
      />,
    )
    expect(screen.getByText('one')).toBeInTheDocument()
    expect(screen.getByText('two')).toBeInTheDocument()
  })
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd ui && npx vitest run src/__tests__/ArtifactCard.test.tsx`
Expected: FAIL — the new proscons/planning text is not rendered (current card only renders answer/citations).

- [ ] **Step 4: Rewrite `ui/src/ArtifactCard.tsx`**

```tsx
import type { Artifact } from './types'

function SearchBody({ a }: { a: Artifact }) {
  return (
    <>
      {a.payload.answer && <p className="card-answer">{a.payload.answer}</p>}
      {a.payload.citations && a.payload.citations.length > 0 && (
        <ul className="card-sources">
          {a.payload.citations.map((c, i) => (
            <li key={i}>
              <a href={c.url} target="_blank" rel="noopener noreferrer">
                {c.title}
              </a>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

function ProsConsBody({ a }: { a: Artifact }) {
  return (
    <>
      <div className="proscons">
        <div className="pros">
          <h4>Pros</h4>
          <ul>
            {(a.payload.pros ?? []).map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
        <div className="cons">
          <h4>Cons</h4>
          <ul>
            {(a.payload.cons ?? []).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      </div>
      {a.payload.recommendation && (
        <p className="card-reco">
          <strong>Recommendation:</strong> {a.payload.recommendation}
        </p>
      )}
    </>
  )
}

function PlanningBody({ a }: { a: Artifact }) {
  return (
    <ol className="card-steps">
      {(a.payload.steps ?? []).map((s, i) => (
        <li key={i}>{s}</li>
      ))}
    </ol>
  )
}

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
      ) : artifact.agent === 'proscons' ? (
        <ProsConsBody a={artifact} />
      ) : artifact.agent === 'planning' ? (
        <PlanningBody a={artifact} />
      ) : (
        <SearchBody a={artifact} />
      )}
    </article>
  )
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd ui && npx vitest run src/__tests__/ArtifactCard.test.tsx`
Expected: PASS (existing search/citation/badge/error tests + the 2 new ones).

- [ ] **Step 6: Commit**

```bash
git add ui/src/types.ts ui/src/ArtifactCard.tsx ui/src/__tests__/ArtifactCard.test.tsx
git commit -m "feat(ui): render pros/cons and planning artifact cards"
```

---

### Task 2: Card styles + build

**Files:**
- Modify: `ui/src/styles.css`

- [ ] **Step 1: Append to `ui/src/styles.css`**

```css
.proscons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin: 0.25rem 0 0.5rem;
}

.proscons h4 {
  margin: 0 0 0.3rem;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
}

.proscons .pros h4 { color: oklch(72% 0.15 150); }
.proscons .cons h4 { color: oklch(72% 0.16 25); }

.proscons ul,
.card-steps {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.9rem;
  line-height: 1.5;
}

.card-steps li { margin-bottom: 0.25rem; }

.card-reco {
  margin: 0.4rem 0 0;
  font-size: 0.9rem;
}

@media (max-width: 30rem) {
  .proscons { grid-template-columns: 1fr; }
}
```

- [ ] **Step 2: Typecheck, test, build**

Run:
```bash
cd ui && npm run typecheck && npm test && npm run build
```
Expected: typecheck clean; all UI tests pass; `dist/` built.

- [ ] **Step 3: Backend smoke — a proscons card payload exists end-to-end (default fake)**

```bash
cd .. && rm -f deeptalk-demo.db
uv run python -m deeptalk.server > /tmp/deeptalk-5b.log 2>&1 &
SERVER_PID=$!
sleep 8
uv run python -c "from deeptalk.artifacts.store import ArtifactStore; a=ArtifactStore('deeptalk-demo.db').all_artifacts('demo'); print([(x.agent, x.status, list(x.payload.keys())) for x in a])"
kill $SERVER_PID 2>/dev/null
```
Expected: a proscons artifact whose payload has `pros`/`cons`/`recommendation` keys, e.g. `[('proscons', 'done', ['pros', 'cons', 'recommendation'])]`. (The card for it now renders in the browser.) Paste `/tmp/deeptalk-5b.log` tail on failure.

- [ ] **Step 4: Commit**

```bash
git add ui/src/styles.css
git commit -m "style(ui): pros/cons grid and planning step styles"
```

---

## Self-Review

**Spec coverage (Phase 5B):** The pros/cons + planning agents (5A) now render as distinct cards (§7 Dashboard), completing spec §15 phase 5. The mockup card is Phase 8 — not a gap.

**Placeholder scan:** No TBD/TODO. Every step has exact code + commands + expected output.

**Type consistency:** `ArtifactPayload` (types.ts) carries the union of all agent payload fields (`answer/citations/model` for search, `pros/cons/recommendation` for proscons, `steps` for planning) — matching the backend `build_payload` outputs in `agents/proscons.py` and `agents/planning.py`. `ArtifactCard` branches on `artifact.agent` values (`proscons`/`planning`/else-search) that match the backend `AGENT` constants and the dispatch map. The existing `Artifact` interface and `useArtifacts`/`App` are unchanged (payload widened, not renamed in a breaking way for consumers).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-deeptalk-phase5b-agent-cards.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, continuous execution.

**2. Inline Execution** — executing-plans with checkpoints.

Which approach?
