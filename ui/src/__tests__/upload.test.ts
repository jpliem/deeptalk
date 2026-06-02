import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postUpload } from '../upload'

beforeEach(() => vi.restoreAllMocks())

describe('postUpload', () => {
  it('POSTs the file as multipart to /upload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ events: 3 }) })
    vi.stubGlobal('fetch', fetchMock)
    const file = new File([new Uint8Array([1, 2, 3])], 'clip.wav', { type: 'audio/wav' })
    const out = await postUpload('demo', file, 'http://h')
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('http://h/upload?session_id=demo')
    expect(opts.method).toBe('POST')
    expect(opts.body).toBeInstanceOf(FormData)
    expect(out).toEqual({ events: 3 })
  })

  it('throws on non-ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    const file = new File([new Uint8Array([1])], 'c.wav')
    await expect(postUpload('demo', file, 'http://h')).rejects.toThrow('500')
  })
})
