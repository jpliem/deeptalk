import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postAsk, resolveHttpBase } from '../ask'

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('resolveHttpBase', () => {
  it('uses the explicit base when given', () => {
    expect(resolveHttpBase('http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000')
  })
})

describe('postAsk', () => {
  it('POSTs session_id and query and returns json', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'x1', status: 'done' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await postAsk('demo', 'what is rust', 'http://h')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('http://h/ask')
    expect(opts.method).toBe('POST')
    expect(JSON.parse(opts.body)).toEqual({ session_id: 'demo', query: 'what is rust' })
    expect(result).toEqual({ id: 'x1', status: 'done' })
  })

  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    await expect(postAsk('demo', 'q', 'http://h')).rejects.toThrow('503')
  })
})
