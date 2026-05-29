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
