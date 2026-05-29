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
