import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, extractDetail } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  const fn = vi.fn().mockResolvedValue({ ok: true, status: 200, statusText: 'OK', ...response })
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('extractDetail', () => {
  it('prefers a string detail', () => {
    expect(extractDetail({ detail: 'Case not found' }, 'fallback')).toBe('Case not found')
  })

  it('flattens FastAPI validation errors into one readable line', () => {
    const body = {
      detail: [
        { loc: ['body', 'timezone'], msg: "Value error, Unknown timezone 'Mars/Base'." },
        { loc: ['body', 'name'], msg: 'String should have at least 1 character' },
      ],
    }
    expect(extractDetail(body, 'x')).toBe(
      "timezone: Unknown timezone 'Mars/Base'.; name: String should have at least 1 character",
    )
  })

  it('falls back when there is nothing usable', () => {
    expect(extractDetail(null, 'Bad Request')).toBe('Bad Request')
    expect(extractDetail({ detail: [] }, 'Bad Request')).toBe('Bad Request')
  })
})

describe('request handling', () => {
  it('returns parsed JSON', async () => {
    stubFetch({ json: async () => [{ id: 'a' }] })
    await expect(api.listCases()).resolves.toEqual([{ id: 'a' }])
  })

  it('throws ApiError with the server message and status', async () => {
    stubFetch({ ok: false, status: 400, statusText: 'Bad Request', json: async () => ({ detail: 'No parser recognised' }) })
    const err = await api.listCases().catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('No parser recognised')
    expect(err.status).toBe(400)
  })

  it('survives an error body that is not JSON', async () => {
    stubFetch({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => {
        throw new SyntaxError('x')
      },
    })
    await expect(api.listCases()).rejects.toThrow('Bad Gateway')
  })

  it('reports an unreachable backend clearly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.health()).rejects.toThrow(/Cannot reach the Fuseline API/)
  })

  it('lets aborts through untouched so callers can ignore them', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')))
    await expect(api.timeline('c1', {})).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('handles 204 responses', async () => {
    stubFetch({ status: 204, json: async () => Promise.reject(new Error('no body')) })
    await expect(api.deleteCase('c1')).resolves.toBeUndefined()
  })
})

describe('query building', () => {
  it('serialises time ranges as ISO strings and drops empty params', async () => {
    const fn = stubFetch({ json: async () => ({}) })
    await api.timeline('c1', {
      source: 'location,browsing',
      q: '',
      start: Date.UTC(2024, 5, 15, 10),
      end: Date.UTC(2024, 5, 15, 11),
      limit: 1000,
      offset: 0,
    })
    const url = new URL(fn.mock.calls[0][0] as string, 'http://x')
    expect(url.pathname).toBe('/api/cases/c1/timeline')
    expect(url.searchParams.get('start')).toBe('2024-06-15T10:00:00.000Z')
    expect(url.searchParams.get('end')).toBe('2024-06-15T11:00:00.000Z')
    expect(url.searchParams.get('source')).toBe('location,browsing')
    expect(url.searchParams.get('limit')).toBe('1000')
    expect(url.searchParams.get('offset')).toBe('0')
    expect(url.searchParams.has('q')).toBe(false)
  })

  it('sends correlation parameters when rebuilding sessions', async () => {
    const fn = stubFetch({ json: async () => [] })
    await api.rebuildSessions('c1', { window_seconds: 120, max_span_seconds: 900, min_sources: 3 })
    const [path, init] = fn.mock.calls[0]
    expect(path).toBe('/api/cases/c1/sessions/rebuild?window_seconds=120&max_span_seconds=900&min_sources=3')
    expect(init).toMatchObject({ method: 'POST' })
  })
})
