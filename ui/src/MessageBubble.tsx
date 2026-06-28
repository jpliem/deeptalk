import type { TranscriptEvent } from './types'

export function MessageBubble({
  event,
  onClick,
}: {
  event: TranscriptEvent
  onClick?: (text: string) => void
}) {
  const cls = [
    'message',
    'transcript',
    event.is_final ? '' : 'interim',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={cls}
      data-ts={event.ts}
      onClick={onClick ? () => onClick(event.text) : undefined}
    >
      {event.speaker != null && (
        <span className="speaker-badge">Speaker {event.speaker}</span>
      )}
      <div className="message-content">{event.text}</div>
    </div>
  )
}
