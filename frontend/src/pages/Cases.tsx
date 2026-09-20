import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Case } from '../api/client'

type Props = {
  activeCaseId: string | null
  onSelectCase: (id: string | null) => void
}

export function CasesPage({ activeCaseId, onSelectCase }: Props) {
  const navigate = useNavigate()
  const [cases, setCases] = useState<Case[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [examiner, setExaminer] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [notes, setNotes] = useState('')
  const [creating, setCreating] = useState(false)

  async function refresh() {
    setLoading(true)
    setError(null)
    try {
      const list = await api.listCases()
      setCases(list)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cases')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    setError(null)
    try {
      const created = await api.createCase({
        name: name.trim(),
        examiner: examiner.trim(),
        timezone: timezone.trim() || 'UTC',
        notes: notes.trim(),
      })
      onSelectCase(created.id)
      setName('')
      setNotes('')
      await refresh()
      navigate('/acquire')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed')
    } finally {
      setCreating(false)
    }
  }

  async function onDelete(id: string) {
    if (!window.confirm('Delete this case and its local evidence copies?')) return
    try {
      await api.deleteCase(id)
      if (activeCaseId === id) onSelectCase(null)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  function openAcquire(id: string) {
    onSelectCase(id)
    navigate('/acquire')
  }

  return (
    <div className="stack">
      <section className="panel">
        <h1>Cases</h1>
        <p className="muted">
          Create a case, then acquire evidence. Each file is SHA-256 hashed into a UTC timeline.
        </p>
        <form className="stack" onSubmit={onCreate} style={{ marginTop: '1rem' }}>
          <div className="form-grid">
            <label>
              Case name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g. Device-A-2024-06"
              />
            </label>
            <label>
              Examiner
              <input value={examiner} onChange={(e) => setExaminer(e.target.value)} />
            </label>
            <label>
              Timezone assumption
              <input value={timezone} onChange={(e) => setTimezone(e.target.value)} />
            </label>
          </div>
          <label>
            Notes
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          </label>
          <div className="row">
            <button className="btn" type="submit" disabled={creating}>
              {creating ? 'Creating…' : 'Create & acquire'}
            </button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Case inventory</h2>
        {error ? <div className="error-box">{error}</div> : null}
        {loading ? <div className="muted">Loading cases…</div> : null}
        {!loading && cases.length === 0 ? (
          <div className="empty">No cases yet. Create one above to start acquisition.</div>
        ) : null}
        {cases.length > 0 ? (
          <table className="data">
            <thead>
              <tr>
                <th>Name</th>
                <th>Events</th>
                <th>Artifacts</th>
                <th>Sessions</th>
                <th>Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id} style={activeCaseId === c.id ? { background: 'var(--amber-soft)' } : undefined}>
                  <td>
                    <strong>{c.name}</strong>
                    <div className="mono muted">{c.id.slice(0, 8)}</div>
                  </td>
                  <td>{c.event_count}</td>
                  <td>{c.artifact_count}</td>
                  <td>{c.session_count}</td>
                  <td className="mono">{c.updated_at}</td>
                  <td>
                    <div className="row">
                      <button type="button" className="btn" onClick={() => openAcquire(c.id)}>
                        Open
                      </button>
                      <Link
                        className="btn secondary"
                        to="/timeline"
                        onClick={() => onSelectCase(c.id)}
                      >
                        Timeline
                      </Link>
                      <button type="button" className="btn secondary" onClick={() => void onDelete(c.id)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </div>
  )
}
