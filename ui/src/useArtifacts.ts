import { useEffect, useState } from 'react'
import type { Artifact } from './types'
import { wsUrl } from './ws'

export function useArtifacts(sessionId: string, wsBase?: string): Artifact[] {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])

  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/artifacts', sessionId, wsBase))
    ws.onmessage = (ev: MessageEvent) => {
      const data = JSON.parse(ev.data) as Artifact
      setArtifacts((prev) => {
        const idx = prev.findIndex((a) => a.id === data.id)
        if (idx === -1) return [...prev, data]
        const next = [...prev]
        next[idx] = data
        return next
      })
    }
    return () => ws.close()
  }, [sessionId, wsBase])

  return artifacts
}
