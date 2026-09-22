import type { Session } from '../api/client'
import { formatDateTime, formatDuration } from '../lib/time'
import { SourceChip } from './SourceChip'

type Props = {
  session: Session
  active: boolean
  timeZone: string
  onSelect: (session: Session) => void
}

export function SessionCard({ session, active, timeZone, onSelect }: Props) {
  const start = Date.parse(session.start_utc)
  const end = Date.parse(session.end_utc)
  return (
    <button
      type="button"
      className={`session-card${active ? ' active' : ''}`}
      aria-pressed={active}
      onClick={() => onSelect(session)}
    >
      <div className="session-top">
        <span className="score">score {session.score.toFixed(2)}</span>
        <span className="mono muted">
          {session.event_count} events · {formatDuration(end - start)}
        </span>
      </div>
      <div className="session-summary">{session.summary}</div>
      <div className="row tight">
        {session.sources.map((s) => (
          <SourceChip key={s} source={s} />
        ))}
      </div>
      <div className="mono muted session-time">
        {formatDateTime(start, timeZone)} → {formatDateTime(end, timeZone).slice(11)}
        {session.radius_m !== null ? ` · ±${Math.round(session.radius_m)} m` : ''}
      </div>
    </button>
  )
}
