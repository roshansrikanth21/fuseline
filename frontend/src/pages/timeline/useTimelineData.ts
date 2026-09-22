import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  type Artifact,
  type Finding,
  type LocationsResponse,
  type Overview,
  type Session,
  type TimelineEvent,
  api,
} from '../../api/client'
import { useDebounced } from '../../hooks/useDebounced'
import { type Range, padRange, rangesEqual } from '../../lib/time'

export const PAGE_SIZE = 1000
/** Up to this many events in the window are drawn individually; beyond it the chart shows density. */
export const MARK_LIMIT = 1000

export type Filters = {
  /** `null` = no source filter; an empty array = nothing selected. */
  sources: string[] | null
  q: string
}

type PageState = {
  token: number
  events: TimelineEvent[]
  total: number
  hasMore: boolean
  /** The time window this page was loaded for, so "load more" continues the same query. */
  window: { start?: number; end?: number }
}

const EMPTY_PAGE: PageState = { token: 0, events: [], total: 0, hasMore: false, window: {} }
const EMPTY_OVERVIEW: Overview = { origin_ms: 0, bucket_ms: 60_000, bucket_count: 0, total: 0, series: {} }

const isAbort = (e: unknown) => e instanceof DOMException && e.name === 'AbortError'
const message = (e: unknown) => (e instanceof Error ? e.message : 'Request failed')

export function useTimelineData(caseId: string, filters: Filters) {
  const sourceParam = filters.sources === null ? undefined : filters.sources.join(',')
  const nothingSelected = filters.sources !== null && filters.sources.length === 0
  const q = filters.q

  const [nonce, setNonce] = useState(0)
  const [overview, setOverview] = useState<Overview | null>(null)
  const [density, setDensity] = useState<Overview | null>(null)
  const [page, setPage] = useState<PageState>(EMPTY_PAGE)
  const [locations, setLocations] = useState<LocationsResponse | null>(null)
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({})
  const [sessions, setSessions] = useState<Session[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [view, setViewState] = useState<Range | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Read once (lazily, not on every render) as the placeholder window's anchor before the
  // real overview has loaded — calling Date.now() directly inside the memo below would make
  // it an impure render-phase call.
  const mountedAtRef = useRef<number>(undefined)
  mountedAtRef.current ??= Date.now()

  const bounds = useMemo<Range>(() => {
    if (!overview || overview.total === 0) {
      const now = mountedAtRef.current!
      return { start: now - 3_600_000, end: now }
    }
    return padRange(overview.origin_ms, overview.origin_ms + overview.bucket_ms * overview.bucket_count, 0.01, 30_000)
  }, [overview])

  const effectiveView = view ?? bounds
  // Only user-driven zoom/pan is debounced; the un-zoomed view follows `bounds` immediately, so a
  // fresh overview never triggers a fetch for a stale placeholder window.
  const settledView = useDebounced(view, 180)
  const queryView = settledView ?? bounds
  // Whether the *settled* view is narrower than the whole case (drives what is fetched).
  const windowed = settledView !== null

  // Case-level data that does not depend on filters or the visible window.
  useEffect(() => {
    let cancelled = false
    Promise.all([api.sessions(caseId), api.listArtifacts(caseId), api.validation(caseId)])
      .then(([s, a, f]) => {
        if (cancelled) return
        setSessions(s)
        setArtifacts(a)
        setFindings(f)
      })
      .catch((e) => !cancelled && setError(message(e)))
    return () => {
      cancelled = true
    }
  }, [caseId, nonce])

  // Whole-case density for the brush; also fixes the extent of the time axis.
  useEffect(() => {
    if (nothingSelected) {
      setOverview(EMPTY_OVERVIEW)
      return
    }
    const ctl = new AbortController()
    api
      .overview(caseId, { source: sourceParam, q, buckets: 240 }, ctl.signal)
      .then((o) => {
        setOverview(o)
        setError(null)
      })
      .catch((e) => !isAbort(e) && setError(message(e)))
    return () => ctl.abort()
  }, [caseId, sourceParam, q, nothingSelected, nonce])

  // Events, window density and location fixes for the visible window.
  const overviewReady = overview !== null
  useEffect(() => {
    if (!overviewReady) return
    if (nothingSelected) {
      setPage(EMPTY_PAGE)
      setDensity(null)
      return
    }
    const ctl = new AbortController()
    const range = windowed ? { start: Math.floor(queryView.start), end: Math.ceil(queryView.end) } : {}
    const common = { source: sourceParam, q, ...range }
    setLoading(true)
    Promise.all([
      api.timeline(caseId, { ...common, limit: PAGE_SIZE }, ctl.signal),
      windowed ? api.overview(caseId, { ...common, buckets: 300 }, ctl.signal) : Promise.resolve(null),
      api.locations(caseId, { ...range, maxPoints: 1500 }, ctl.signal),
    ])
      .then(([tl, dens, loc]) => {
        setPage((prev) => ({
          token: prev.token + 1,
          events: tl.events,
          total: tl.total,
          hasMore: tl.has_more,
          window: range,
        }))
        setSourceCounts(tl.sources)
        setDensity(dens)
        setLocations(loc)
        setError(null)
      })
      .catch((e) => !isAbort(e) && setError(message(e)))
      .finally(() => {
        if (!ctl.signal.aborted) setLoading(false)
      })
    return () => ctl.abort()
  }, [caseId, overviewReady, sourceParam, q, nothingSelected, windowed, queryView.start, queryView.end, nonce])

  const setView = useCallback(
    (range: Range | null) => {
      setViewState(range === null || rangesEqual(range, bounds) ? null : range)
    },
    [bounds],
  )

  const loadMore = useCallback(() => {
    if (loadingMore || !page.hasMore) return
    const token = page.token
    setLoadingMore(true)
    api
      .timeline(caseId, { source: sourceParam, q, ...page.window, offset: page.events.length, limit: PAGE_SIZE })
      .then((tl) =>
        setPage((prev) =>
          prev.token === token ? { ...prev, events: [...prev.events, ...tl.events], hasMore: tl.has_more } : prev,
        ),
      )
      .catch((e) => setError(message(e)))
      .finally(() => setLoadingMore(false))
  }, [caseId, sourceParam, q, page, loadingMore])

  const marks = page.total <= MARK_LIMIT && page.events.length === page.total ? page.events : null
  const refresh = useCallback(() => setNonce((n) => n + 1), [])

  return {
    ready: overview !== null,
    loading,
    loadingMore,
    error,
    bounds,
    view: effectiveView,
    isZoomed: view !== null,
    setView,
    overview,
    density: windowed && density ? density : overview,
    events: page.events,
    total: page.total,
    hasMore: page.hasMore,
    loadMore,
    marks,
    sourceCounts,
    sessions,
    artifacts,
    findings,
    locations,
    refresh,
  }
}

export type TimelineData = ReturnType<typeof useTimelineData>
