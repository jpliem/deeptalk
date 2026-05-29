import { describe, it, expect } from 'vitest'
import { resolveWsUrl, wsUrl } from '../ws'

describe('wsUrl', () => {
  it('builds an arbitrary ws path with session', () => {
    expect(wsUrl('/ws/artifacts', 'demo', 'ws://x')).toBe(
      'ws://x/ws/artifacts?session_id=demo',
    )
  })
  it('url-encodes the session id', () => {
    expect(wsUrl('/ws/transcript', 'a b', 'ws://x')).toBe(
      'ws://x/ws/transcript?session_id=a%20b',
    )
  })
})

describe('resolveWsUrl (transcript back-compat)', () => {
  it('builds the transcript url from an explicit base', () => {
    expect(resolveWsUrl('demo', 'ws://127.0.0.1:8000')).toBe(
      'ws://127.0.0.1:8000/ws/transcript?session_id=demo',
    )
  })
})
