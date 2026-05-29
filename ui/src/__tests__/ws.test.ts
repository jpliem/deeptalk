import { describe, it, expect } from 'vitest'
import { resolveWsUrl } from '../ws'

describe('resolveWsUrl', () => {
  it('builds the url from an explicit base', () => {
    expect(resolveWsUrl('demo', 'ws://127.0.0.1:8000')).toBe(
      'ws://127.0.0.1:8000/ws/transcript?session_id=demo',
    )
  })

  it('url-encodes the session id', () => {
    expect(resolveWsUrl('a b', 'ws://x')).toBe(
      'ws://x/ws/transcript?session_id=a%20b',
    )
  })
})
