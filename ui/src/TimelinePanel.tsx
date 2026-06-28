import { useMemo, useState } from 'react'
import type { TimelineEntry } from './types'

function fmtTime(ts: number): string {
  const m = Math.floor(ts / 60)
  const s = Math.floor(ts % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ─── Dot View ───────────────────────────────────────────

function DotView({
  entries,
  onJump,
}: {
  entries: TimelineEntry[]
  onJump?: (ts: number) => void
}) {
  return (
    <div className="timeline-dots">
      {entries.map((e, i) => (
        <div
          key={e.id}
          className={`timeline-dot-entry${i === entries.length - 1 ? ' last' : ''}`}
          onClick={onJump ? () => onJump(e.start_ts) : undefined}
        >
          <div className="timeline-dot-line">
            <div className="timeline-dot" />
            {i < entries.length - 1 && <div className="timeline-line" />}
          </div>
          <div className="timeline-dot-body">
            <div className="timeline-dot-label">{e.label}</div>
            <div className="timeline-dot-time">{fmtTime(e.start_ts)}</div>
            <div className="timeline-dot-summary">{e.summary}</div>
            {e.decisions.length > 0 && (
              <div className="timeline-dot-items">
                {e.decisions.map((d, j) => (
                  <div key={j} className="timeline-decision">✓ {d}</div>
                ))}
              </div>
            )}
            {e.action_items.length > 0 && (
              <div className="timeline-dot-items">
                {e.action_items.map((a, j) => (
                  <div key={j} className="timeline-action">☐ {a}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Swimlane View ──────────────────────────────────────

function SwimlaneView({
  entries,
  maxTs,
  onJump,
}: {
  entries: TimelineEntry[]
  maxTs: number
  onJump?: (ts: number) => void
}) {
  const total = maxTs || 1

  return (
    <div className="timeline-swimlane">
      {/* Time axis */}
      <div className="timeline-swim-axis">
        <span>0:00</span>
        <span>{fmtTime(total)}</span>
      </div>

      {/* Bars */}
      <div className="timeline-swim-bars">
        {entries.map((e) => {
          const leftPct = (e.start_ts / total) * 100
          const widthPct = Math.max(
            ((e.end_ts - e.start_ts) / total) * 100,
            2,
          )
          return (
            <div
              key={e.id}
              className="timeline-swim-bar"
              onClick={onJump ? () => onJump(e.start_ts) : undefined}
            >
              <div className="timeline-swim-label">{e.label}</div>
              <div className="timeline-swim-track">
                <div
                  className="timeline-swim-fill"
                  style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                  title={`${e.label}: ${fmtTime(e.start_ts)} — ${fmtTime(e.end_ts)}`}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Main Panel ─────────────────────────────────────────

export function TimelinePanel({
  entries,
  onJumpToTime,
}: {
  entries: TimelineEntry[]
  onJumpToTime?: (ts: number) => void
}) {
  const [view, setView] = useState<'dots' | 'swimlane'>('dots')

  const maxTs = useMemo(
    () => entries.reduce((m, e) => Math.max(m, e.end_ts), 0),
    [entries],
  )

  const hasItems = entries.length > 0

  return (
    <div className="sidebar-section">
      <div className="sidebar-section-title">Timeline</div>

      {hasItems && (
        <div className="timeline-tabs">
          <button
            className={`timeline-tab${view === 'dots' ? ' active' : ''}`}
            onClick={() => setView('dots')}
          >
            Dots
          </button>
          <button
            className={`timeline-tab${view === 'swimlane' ? ' active' : ''}`}
            onClick={() => setView('swimlane')}
          >
            Swimlane
          </button>
        </div>
      )}

      {!hasItems && (
        <div className="timeline-empty">
          Transcript events will appear here as the meeting progresses.
        </div>
      )}

      {hasItems && view === 'dots' && (
        <DotView entries={entries} onJump={onJumpToTime} />
      )}

      {hasItems && view === 'swimlane' && (
        <SwimlaneView
          entries={entries}
          maxTs={maxTs}
          onJump={onJumpToTime}
        />
      )}
    </div>
  )
}
