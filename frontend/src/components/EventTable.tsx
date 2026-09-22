import { useRef } from 'react'
import type { KeyboardEvent } from 'react'
import type { TimelineEvent } from '../api/client'
import { formatCount } from '../lib/format'
import { formatDateTime } from '../lib/time'
import { SourceChip } from './SourceChip'

type Props = {
  events: TimelineEvent[]
  total: number
  hasMore: boolean
  loading: boolean
  selectedId: string | null
  highlightIds: Set<string> | null
  timeZone: string
  onSelect: (event: TimelineEvent) => void
  onLoadMore: () => void
  emptyText?: string
}

export function EventTable({
  events,
  total,
  hasMore,
  loading,
  selectedId,
  highlightIds,
  timeZone,
  onSelect,
  onLoadMore,
  emptyText = 'No events match the current filters and time window.',
}: Props) {
  const bodyRef = useRef<HTMLTableSectionElement>(null)

  function onRowKey(e: KeyboardEvent<HTMLTableRowElement>, event: TimelineEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSelect(event)
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const sibling = e.key === 'ArrowDown' ? e.currentTarget.nextElementSibling : e.currentTarget.previousElementSibling
      ;(sibling as HTMLElement | null)?.focus()
    }
  }

  if (events.length === 0) return <div className="empty">{loading ? 'Loading events…' : emptyText}</div>

  return (
    <div>
      <div className="table-scroll" role="region" aria-label="Events in view" tabIndex={-1}>
        <table className="data selectable">
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Source</th>
              <th scope="col">Event</th>
            </tr>
          </thead>
          <tbody ref={bodyRef}>
            {events.map((ev) => {
              const lit = highlightIds?.has(ev.id)
              return (
                <tr
                  key={ev.id}
                  tabIndex={0}
                  aria-selected={selectedId === ev.id}
                  className={`${selectedId === ev.id ? 'row-selected' : ''}${lit ? ' row-lit' : ''}`}
                  onClick={() => onSelect(ev)}
                  onKeyDown={(e) => onRowKey(e, ev)}
                >
                  <td className="mono nowrap">
                    {formatDateTime(ev.ts_ms, timeZone)}
                    {ev.ts_basis === 'assumed' ? (
                      <span className="warn-text" title={`Assumed local time (${ev.tz_assumed})`}>
                        {' '}
                        ~
                      </span>
                    ) : null}
                  </td>
                  <td>
                    <SourceChip source={ev.source} />
                  </td>
                  <td>
                    <div className="cell-title">{ev.title}</div>
                    {ev.domain && ev.domain !== ev.title ? <div className="cell-sub mono">{ev.domain}</div> : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="table-foot">
        <span className="mono muted">
          {formatCount(events.length)} of {formatCount(total)} in view
        </span>
        {hasMore ? (
          <button type="button" className="btn secondary small" onClick={onLoadMore} disabled={loading}>
            {loading ? 'Loading…' : 'Load more'}
          </button>
        ) : null}
      </div>
    </div>
  )
}
