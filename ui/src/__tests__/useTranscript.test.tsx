import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useTranscript } from '../useTranscript'

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

function send(sock: FakeWebSocket, partial: Record<string, unknown>) {
  const ev = {
    session_id: 'demo',
    ts: 0,
    text: 'hi',
    is_final: true,
    source: 'live',
    speaker: null,
    span_id: null,
    ...partial,
  }
  act(() => sock.onmessage?.({ data: JSON.stringify(ev) }))
}

describe('useTranscript', () => {
  it('opens a socket to the resolved url', () => {
    renderHook(() => useTranscript('demo', 'ws://x'))
    expect(FakeWebSocket.instances[0].url).toBe(
      'ws://x/ws/transcript?session_id=demo',
    )
  })

  it('appends incoming events in order', async () => {
    const { result } = renderHook(() => useTranscript('demo', 'ws://x'))
    const sock = FakeWebSocket.instances[0]
    send(sock, { text: 'first' })
    send(sock, { text: 'second' })
    await waitFor(() => expect(result.current).toHaveLength(2))
    expect(result.current.map((e) => e.text)).toEqual(['first', 'second'])
  })
})
