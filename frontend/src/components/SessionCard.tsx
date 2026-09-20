import type { Session } from '../api/client'
import { SourceChip } from './SourceChip'

type Props = {
  session: Session
  active: boolean
  onSelect: (session: Session) => void
}

export function SessionCard({ session, active, onSelect }: Props) {
  return (
    <button
      type="button"
      className={`session-card${active ? ' active' : ''}`}
      onClick={() => onSelect(session)}
      style={{ width: '100%', textAlign: 'left' }}
    >
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="score">score {session.score.toFixed(2)}</span>
        <span className="mono muted">{session.member_event_ids.length} events</span>
      </div>
      <div style={{ margin: '0.35rem 0' }}>{session.summary}</div>
      <div className="row">
        {session.sources.map((s) => (
          <SourceChip key={s} source={s} />
        ))}
      </div>
      <div className="mono muted" style={{ marginTop: '0.35rem' }}>
        {session.start_utc.slice(11, 19)} → {session.end_utc.slice(11, 19)}
      </div>
    </button>
  )
}