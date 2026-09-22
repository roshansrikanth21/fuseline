import { useEffect, useState } from 'react'
import { type CorrelationParams, api } from '../api/client'

const DEFAULTS: CorrelationParams = { window_seconds: 300, max_span_seconds: 1800, min_sources: 2 }

type Props = {
  caseId: string
  onRebuilt: () => void
}

export function CorrelationSettings({ caseId, onRebuilt }: Props) {
  const [saved, setSaved] = useState<CorrelationParams>(DEFAULTS)
  const [draft, setDraft] = useState<CorrelationParams>(DEFAULTS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .correlationParams(caseId)
      .then((p) => {
        if (!cancelled) {
          setSaved(p)
          setDraft(p)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [caseId])

  const dirty = JSON.stringify(draft) !== JSON.stringify(saved)

  async function rebuild(params: CorrelationParams) {
    setBusy(true)
    setError(null)
    try {
      await api.rebuildSessions(caseId, params)
      setSaved(params)
      setDraft(params)
      onRebuilt()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rebuild failed')
    } finally {
      setBusy(false)
    }
  }

  const num = (v: string, min: number, max: number, fallback: number) => {
    const n = Number.parseInt(v, 10)
    return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback
  }

  return (
    <form
      className="correlation"
      onSubmit={(e) => {
        e.preventDefault()
        void rebuild(draft)
      }}
    >
      <p className="muted small">
        Events chain into a session while each is within the <strong>window</strong> of the previous one. A session
        needs at least <strong>min sources</strong> and is split at its widest pauses once longer than{' '}
        <strong>max length</strong>.
      </p>
      <div className="form-grid tight-grid">
        <label>
          Window (seconds)
          <input
            type="number"
            min={1}
            max={3600}
            value={draft.window_seconds}
            onChange={(e) => setDraft({ ...draft, window_seconds: num(e.target.value, 1, 3600, saved.window_seconds) })}
          />
        </label>
        <label>
          Max length (seconds)
          <input
            type="number"
            min={30}
            max={86400}
            value={draft.max_span_seconds}
            onChange={(e) =>
              setDraft({ ...draft, max_span_seconds: num(e.target.value, 30, 86400, saved.max_span_seconds) })
            }
          />
        </label>
        <label>
          Min sources
          <select
            value={draft.min_sources}
            onChange={(e) => setDraft({ ...draft, min_sources: Number(e.target.value) })}
          >
            <option value={2}>2</option>
            <option value={3}>3</option>
            <option value={4}>4</option>
          </select>
        </label>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      <div className="row">
        <button type="submit" className="btn small" disabled={busy || !dirty}>
          {busy ? 'Rebuilding…' : 'Rebuild sessions'}
        </button>
        <button
          type="button"
          className="btn secondary small"
          disabled={busy || JSON.stringify(saved) === JSON.stringify(DEFAULTS)}
          onClick={() => void rebuild(DEFAULTS)}
        >
          Reset to defaults
        </button>
      </div>
    </form>
  )
}
