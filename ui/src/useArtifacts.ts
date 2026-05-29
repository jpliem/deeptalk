import { useEffect, useState } from 'react'
import type { Artifact } from './types'
import { wsUrl } from './ws'

export function useArtifacts(sessionId: string, wsBase?: string): Artifact[] {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])

  useEffect(() => {
    const ws = new WebSocket(wsUrl('/ws/artifacts', sessionId, wsBase))
    ws.onmessage = (ev: MessageEvent) => {
      const data = JSON.parse(ev.data) as Artifact
      setArtifacts((prev) => [...prev, data])
    }
    return () => ws.close()
  }, [sessionId, wsBase])

  return artifacts
}
