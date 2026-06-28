import { useCallback, useState } from 'react'
import type { TranscriptEvent } from './types'
import { useWebSocket } from './useWebSocket'

export function useTranscript(sessionId: string, wsBase?: string): TranscriptEvent[] {
  const [events, setEvents] = useState<TranscriptEvent[]>([])

  const onMessage = useCallback((data: TranscriptEvent) => {
    setEvents((prev) => [...prev, data])
  }, [])

  useWebSocket<TranscriptEvent>('/ws/transcript', sessionId, onMessage, wsBase)

  return events
}
