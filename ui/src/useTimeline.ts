import { useEffect, useState } from 'react'
import type { TimelineEntry } from './types'
import { wsUrl } from './ws'

export function useTimeline(sessionId: string, wsBase?: string): TimelineEntry[] {
  const [entries, setEntries] = useState<TimelineEntry[]>([])

  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/timeline', sessionId, wsBase))
    ws.onmessage = (ev: MessageEvent) => {
      const data = JSON.parse(ev.data)
      // Backlog sends individual TimelineEntry objects (flat).
      // Live bus events send TimelineEvent with { entries: [...], updated_ids: [...] }.
      if (data.entries) {
        setEntries(data.entries)
      } else if (data.id && data.topic_id) {
        // Individual entry from backlog
        setEntries((prev) => {
          const exists = prev.find((e) => e.id === data.id)
          if (exists) return prev
          return [...prev, data as TimelineEntry]
        })
      }
    }
    return () => ws.close()
  }, [sessionId, wsBase])

  return entries
}
