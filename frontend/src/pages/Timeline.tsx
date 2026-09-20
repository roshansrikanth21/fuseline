import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Session, type TimelineEvent } from '../api/client'
import { EventDrawer } from '../components/EventDrawer'
import { SessionCard } from '../components/SessionCard'
import { SourceChip } from '../components/SourceChip'
import { Swimlane } from '../components/Swimlane'

type Props = {
  caseId: string | null
}

const SOURCES = ['location', 'browsing', 'app_usage', 'plaso'] as const

function shortTime(ts: string): string {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toLocaleString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  })
}

export function TimelinePage({ caseId }: Props) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({})
  const [enabled, setEnabled] = useState<Record<string, boolean>>({
    location: true,
    browsing: true,
    app_usage: true,
    plaso: true,
  })
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<TimelineEvent | null>(null)
  const [activeSession, setActiveSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!caseId) return
    setLoading(true)
    setError(null)
    try {
      const activeSources = SOURCES.filter((s) => enabled[s]).join(',')
      const [tl, sess] = await Promise.all([
        api.timeline(caseId, {
          source: activeSources || undefined,
          q: query.trim() || undefined,
        }),
        api.sessions(caseId),
      ])
      setEvents(tl.events)
      setSourceCounts(tl.sources)
      setSessions(sess)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load timeline')
    } finally {
      setLoading(false)
    }
  }, [caseId, enabled, query])

  useEffect(() => {
    void load()
  }, [load])

  const highlightIds = useMemo(() => {
    if (!activeSession) return null
    return new Set(activeSession.member_event_ids)
  }, [activeSession])

  const presentSources = SOURCES.filter((s) => (sourceCounts[s] ?? 0) > 0)
  const visibleSources = presentSources.length > 0 ? presentSources : [...SOURCES]

  const listEvents = useMemo(() => {
    if (!activeSession) return events
    const ids = new Set(activeSession.member_event_ids)
    return events.filter((e) => ids.has(e.id))
  }, [events, activeSession])

  if (!caseId) {
    return (
      <section className="panel">
        <h1>Timeline</h1>
        <div className="empty">
          No active case. <Link to="/">Create or open a case</Link>
        </div>
      </section>
    )
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Timeline</h1>
            <p className="muted">Swimlanes plus proximity sessions. Click a mark or a row to inspect.</p>
          </div>
          <button type="button" className="btn secondary" disabled={loading} onClick={() => void load()}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>

        <div className="row" style={{ marginTop: '0.75rem' }}>
          {visibleSources.map((s) => (
            <label key={s} className="check-label">
              <input
                type="checkbox"
                checked={enabled[s]}
                onChange={(e) => setEnabled((prev) => ({ ...prev, [s]: e.target.checked }))}
              />
              <SourceChip source={s} />
              <span className="mono muted">{sourceCounts[s] ?? 0}</span>
            </label>
          ))}
          <input
            type="search"
            placeholder="Filter title / package / url"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ flex: 1, minWidth: 180 }}
          />
        </div>

        {error ? <div className="error-box" style={{ marginTop: '0.75rem' }}>{error}</div> : null}

        <div className="timeline-layout" style={{ marginTop: '1rem' }}>
          <div>
            <Swimlane
              events={events}
              selectedId={selected?.id ?? null}
              highlightIds={highlightIds}
              onSelect={setSelected}
            />
            <EventDrawer event={selected} onClose={() => setSelected(null)} />

            <div style={{ marginTop: '1rem' }}>
              <h2 style={{ margin: '0 0 0.5rem' }}>
                {activeSession ? 'Session events' : 'Event list'}
              </h2>
              {listEvents.length === 0 ? (
                <div className="empty">No events match the current filters.</div>
              ) : (
                <div className="table-scroll">
                  <table className="data">
                    <thead>
                      <tr>
                        <th>UTC</th>
                        <th>Source</th>
                        <th>Title</th>
                      </tr>
                    </thead>
                    <tbody>
                      {listEvents.map((ev) => (
                        <tr
                          key={ev.id}
                          className={selected?.id === ev.id ? 'row-selected' : undefined}
                          style={{ cursor: 'pointer' }}
                          onClick={() => setSelected(ev)}
                        >
                          <td className="mono">{shortTime(ev.ts_utc)}</td>
                          <td>
                            <SourceChip source={ev.source} />
                          </td>
                          <td>{ev.title}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
          <aside className="stack">
            <h2 style={{ margin: 0 }}>Proximity sessions</h2>
            {sessions.length === 0 ? (
              <div className="empty">No multi-source clusters yet. Ingest at least two source types.</div>
            ) : (
              sessions.map((s) => (
                <SessionCard
                  key={s.id}
                  session={s}
                  active={activeSession?.id === s.id}
                  onSelect={(sess) => {
                    setActiveSession((prev) => (prev?.id === sess.id ? null : sess))
                  }}
                />
              ))
            )}
          </aside>
        </div>
      </section>
    </div>
  )
}
