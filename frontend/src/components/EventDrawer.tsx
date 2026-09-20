import type { TimelineEvent } from '../api/client'
import { SourceChip } from './SourceChip'

type Props = {
  event: TimelineEvent | null
  onClose: () => void
}

export function EventDrawer({ event, onClose }: Props) {
  if (!event) {
    return (
      <div className="drawer muted">Select an event mark on a lane to inspect provenance.</div>
    )
  }

  return (
    <div className="drawer">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <div className="row">
          <SourceChip source={event.source} />
          <strong>{event.title}</strong>
        </div>
        <button type="button" className="btn secondary" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="stack" style={{ marginTop: '0.65rem' }}>
        <div className="mono">UTC {event.ts_utc}</div>
        <div className="mono muted">original {event.ts_original}</div>
        {event.package ? <div>package: {event.package}</div> : null}
        {event.url ? (
          <div>
            url: <a href={event.url}>{event.url}</a>
          </div>
        ) : null}
        {event.lat != null && event.lon != null ? (
          <div className="mono">
            lat {event.lat.toFixed(5)}, lon {event.lon.toFixed(5)}
          </div>
        ) : null}
        <pre>{JSON.stringify(event.detail, null, 2)}</pre>
      </div>
    </div>
  )
}