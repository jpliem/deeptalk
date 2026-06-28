import { useCallback, useState } from 'react'
import type { Artifact } from './types'
import { useWebSocket } from './useWebSocket'

export function useArtifacts(sessionId: string, wsBase?: string): Artifact[] {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])

  const onMessage = useCallback((data: Artifact) => {
    setArtifacts((prev) => {
      const idx = prev.findIndex((a) => a.id === data.id)
      if (idx === -1) return [...prev, data]
      const next = [...prev]
      next[idx] = data
      return next
    })
  }, [])

  useWebSocket<Artifact>('/ws/artifacts', sessionId, onMessage, wsBase)

  return artifacts
}
