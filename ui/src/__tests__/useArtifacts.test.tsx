import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useArtifacts } from '../useArtifacts'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  onmessage: ((ev: { data: string }) => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }
  close() {}
}

beforeEach(() => {
  FakeWebSocket.instances = []
  vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
})

function sendArtifact(sock: FakeWebSocket, partial: Record<string, unknown>) {
  const art = {
    id: 'a1',
    session_id: 'demo',
    agent: 'search',
    status: 'done',
    title: 'q',
    payload: { answer: 'A', citations: [] },
    created_at: 0,
    latency_ms: null,
    error: null,
    ...partial,
  }
  act(() => sock.onmessage?.({ data: JSON.stringify(art) }))
}

describe('useArtifacts', () => {
  it('connects to the artifacts ws path', () => {
    renderHook(() => useArtifacts('demo', 'ws://x'))
    expect(FakeWebSocket.instances[0].url).toBe('ws://x/ws/artifacts?session_id=demo')
  })

  it('accumulates incoming artifacts', async () => {
    const { result } = renderHook(() => useArtifacts('demo', 'ws://x'))
    const sock = FakeWebSocket.instances[0]
    sendArtifact(sock, { id: 'a1' })
    sendArtifact(sock, { id: 'a2' })
    await waitFor(() => expect(result.current).toHaveLength(2))
    expect(result.current.map((a) => a.id)).toEqual(['a1', 'a2'])
  })

  it('replaces an artifact when a newer one with the same id arrives', async () => {
    const { result } = renderHook(() => useArtifacts('demo', 'ws://x'))
    const sock = FakeWebSocket.instances[0]
    sendArtifact(sock, { id: 'a1', status: 'pending', title: 'q' })
    sendArtifact(sock, { id: 'a1', status: 'done', title: 'q', payload: { answer: 'A' } })
    await waitFor(() => expect(result.current).toHaveLength(1))
    expect(result.current[0].status).toBe('done')
  })
})
