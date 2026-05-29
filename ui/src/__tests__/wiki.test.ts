import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postFinalize, getWiki } from '../wiki'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('postFinalize', () => {
  it('POSTs the session_id to /finalize', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)
    await postFinalize('demo', 'http://h')
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('http://h/finalize')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ session_id: 'demo' })
  })
})

describe('getWiki', () => {
  it('returns the wiki json on 200', async () => {
    const wiki = { session_id: 'demo', topics: ['t'], decisions: ['d'], action_items: ['a'], created_at: 0 }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => wiki }))
    const got = await getWiki('demo', 'http://h')
    expect(got).toEqual(wiki)
  })

  it('returns null on 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    expect(await getWiki('demo', 'http://h')).toBeNull()
  })
})
