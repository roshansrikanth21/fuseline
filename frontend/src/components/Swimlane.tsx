import type { TimelineEvent } from '../api/client'

const LANE_ORDER = ['location', 'browsing', 'app_usage', 'plaso'] as const

const LANE_COLOR: Record<string, string> = {
  location: 'var(--lane-location)',
  browsing: 'var(--lane-browsing)',
  app_usage: 'var(--lane-app)',
  plaso: 'var(--lane-plaso)',
}

type Props = {
  events: TimelineEvent[]
  selectedId: string | null
  highlightIds: Set<string> | null
  onSelect: (event: TimelineEvent) => void
}

function parseMs(ts: string): number {
  return Date.parse(ts)
}

function formatRange(min: number, max: number): string {
  const opts: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  }
  const a = new Date(min).toLocaleString('en-GB', opts)
  const b = new Date(max).toLocaleString('en-GB', opts)
  return `${a} → ${b} UTC`
}

/** Stack overlapping marks so clicks aren't stolen. */
function laneOffsets(events: TimelineEvent[]): Map<string, number> {
  const sorted = [...events].sort((a, b) => parseMs(a.ts_utc) - parseMs(b.ts_utc))
  const offsets = new Map<string, number>()
  let cluster: TimelineEvent[] = []
  const flush = () => {
    cluster.forEach((ev, i) => offsets.set(ev.id, i % 3))
    cluster = []
  }
  for (const ev of sorted) {
    if (cluster.length === 0) {
      cluster.push(ev)
      continue
    }
    const prev = cluster[cluster.length - 1]
    if (Math.abs(parseMs(ev.ts_utc) - parseMs(prev.ts_utc)) < 90_000) {
      cluster.push(ev)
    } else {
      flush()
      cluster.push(ev)
    }
  }
  flush()
  return offsets
}

export function Swimlane({ events, selectedId, highlightIds, onSelect }: Props) {
  if (events.length === 0) {
    return (
      <div className="empty">
        No events in view. Go to Acquire and upload artifacts or load sample evidence.
      </div>
    )
  }

  const times = events.map((e) => parseMs(e.ts_utc)).filter((n) => !Number.isNaN(n))
  const min = Math.min(...times)
  const max = Math.max(...times)
  const span = Math.max(max - min, 60_000)

  const bySource = new Map<string, TimelineEvent[]>()
  for (const src of LANE_ORDER) bySource.set(src, [])
  for (const ev of events) {
    const key = LANE_ORDER.includes(ev.source as (typeof LANE_ORDER)[number])
      ? ev.source
      : 'plaso'
    const list = bySource.get(key) ?? []
    list.push(ev)
    bySource.set(key, list)
  }

  const activeLanes = LANE_ORDER.filter((s) => (bySource.get(s) ?? []).length > 0)

  return (
    <div className="lanes">
      <div className="mono muted" style={{ marginBottom: '0.35rem' }}>
        {formatRange(min, max)}
      </div>
      {activeLanes.map((source) => {
        const laneEvents = bySource.get(source) ?? []
        const offsets = laneOffsets(laneEvents)
        return (
          <div className="lane" key={source}>
            <div className="lane-head">
              <span>{source}</span>
              <span>{laneEvents.length}</span>
            </div>
            <div className="lane-track">
              {laneEvents.map((ev) => {
                const t = parseMs(ev.ts_utc)
                const pct = ((t - min) / span) * 100
                const dim = highlightIds != null && !highlightIds.has(ev.id)
                const selected = selectedId === ev.id
                const stack = offsets.get(ev.id) ?? 0
                return (
                  <button
                    key={ev.id}
                    type="button"
                    title={`${ev.ts_utc} — ${ev.title}`}
                    aria-label={`${ev.source} ${ev.title} at ${ev.ts_utc}`}
                    className={`event-mark${selected ? ' selected' : ''}${dim ? ' dim' : ''}`}
                    style={{
                      left: `${pct}%`,
                      top: `${8 + stack * 14}px`,
                      background: LANE_COLOR[source] ?? 'var(--ink)',
                    }}
                    onClick={() => onSelect(ev)}
                  />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
