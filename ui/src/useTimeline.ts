import { useCallback, useState } from 'react'
import type { TimelineEntry } from './types'
import { useWebSocket } from './useWebSocket'

interface TimelineEventMsg {
  entries?: TimelineEntry[]
  id?: string
  topic_id?: string
}

export function useTimeline(sessionId: string, wsBase?: string): TimelineEntry[] {
  const [entries, setEntries] = useState<TimelineEntry[]>([])

  const onMessage = useCallback((data: TimelineEventMsg) => {
    if (data.entries) {
      setEntries(data.entries)
    } else if (data.id && data.topic_id) {
      setEntries((prev) => {
        const exists = prev.find((e) => e.id === data.id)
        if (exists) return prev
        return [...prev, data as TimelineEntry]
      })
    }
  }, [])

  useWebSocket<TimelineEventMsg>('/ws/timeline', sessionId, onMessage, wsBase)

  return entries
}
