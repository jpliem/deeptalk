import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchReport } from '../report'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('fetchReport', () => {
  it('GETs /report with the session_id and returns markdown', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => '# Meeting Report — demo',
    })
    vi.stubGlobal('fetch', fetchMock)
    const md = await fetchReport('demo', 'http://h')
    expect(fetchMock.mock.calls[0][0]).toBe('http://h/report?session_id=demo')
    expect(md).toBe('# Meeting Report — demo')
  })

  it('throws a friendly error on 404', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    await expect(fetchReport('demo', 'http://h')).rejects.toThrow(
      'No transcript yet',
    )
  })

  it('throws on server error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    await expect(fetchReport('demo', 'http://h')).rejects.toThrow('report failed: 503')
  })
})
