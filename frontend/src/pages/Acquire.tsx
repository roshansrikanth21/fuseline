import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Artifact, type Finding } from '../api/client'
import { SourceChip } from '../components/SourceChip'

type Props = {
  caseId: string | null
}

const HINTS = [
  { value: 'auto', label: 'Auto-detect' },
  { value: 'app_usage', label: 'App usage' },
  { value: 'browsing', label: 'Browsing / Chromium History' },
  { value: 'location', label: 'Location' },
  { value: 'plaso', label: 'Plaso L2TCSV / JSONL' },
]

export function AcquirePage({ caseId }: Props) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [hint, setHint] = useState('auto')
  const [dragOver, setDragOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!caseId) return
    try {
      const [arts, vals] = await Promise.all([api.listArtifacts(caseId), api.validation(caseId)])
      setArtifacts(arts)
      setFindings(vals)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load artifacts')
    }
  }, [caseId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function uploadFile(file: File) {
    if (!caseId) return
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const result = await api.upload(caseId, file, hint)
      setMessage(
        result.events_added === 0
          ? `Already ingested ${result.artifact.original_name} (same SHA-256); no new events.`
          : `Ingested ${result.artifact.original_name}: ${result.events_added} events, ${result.sessions_rebuilt} sessions.`,
      )
      setFindings(result.findings)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setBusy(false)
    }
  }

  async function loadDemo() {
    if (!caseId) return
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      const result = await api.loadDemo(caseId)
      setMessage(
        `Loaded sample evidence: ${result.events_added} events from ${result.artifacts.length} artifacts, ${result.sessions_rebuilt} proximity sessions.`,
      )
      setFindings(result.findings)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Demo load failed')
    } finally {
      setBusy(false)
    }
  }

  if (!caseId) {
    return (
      <section className="panel">
        <h1>Acquire</h1>
        <div className="empty">
          Select or create a case first. <Link to="/">Go to Cases</Link>
        </div>
      </section>
    )
  }

  return (
    <div className="stack">
      <section className="panel">
        <h1>Acquire</h1>
        <p className="muted">
          Upload location, browsing, and app-usage artifacts (or Plaso L2TCSV). Files are SHA-256 hashed on ingest.
        </p>
        <div className="row" style={{ marginTop: '0.75rem' }}>
          <button type="button" className="btn amber" disabled={busy} onClick={() => void loadDemo()}>
            {busy ? 'Working…' : 'Load sample evidence'}
          </button>
          <label style={{ minWidth: 200 }}>
            Source hint
            <select value={hint} onChange={(e) => setHint(e.target.value)} disabled={busy}>
              {HINTS.map((h) => (
                <option key={h.value} value={h.value}>
                  {h.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div
          className={`dropzone${dragOver ? ' active' : ''}`}
          style={{ marginTop: '1rem' }}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            const file = e.dataTransfer.files?.[0]
            if (file) void uploadFile(file)
          }}
        >
          <p>Drop an artifact here, or choose a file</p>
          <input
            type="file"
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void uploadFile(file)
              e.target.value = ''
            }}
          />
        </div>

        {message ? <p style={{ marginTop: '0.75rem' }}>{message}</p> : null}
        {error ? <div className="error-box" style={{ marginTop: '0.75rem' }}>{error}</div> : null}
      </section>

      <section className="panel">
        <h2>Artifact inventory</h2>
        {artifacts.length === 0 ? (
          <div className="empty">No artifacts yet.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Rows</th>
                <th>SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {artifacts.map((a) => (
                <tr key={a.id}>
                  <td>{a.original_name}</td>
                  <td>
                    <SourceChip source={a.source_type} />
                  </td>
                  <td>{a.row_count}</td>
                  <td className="mono">{a.sha256.slice(0, 16)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <h2>Validation snapshot</h2>
        {findings.length === 0 ? (
          <div className="empty">Validation runs after ingest.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Code</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.id}>
                  <td className={`sev-${f.severity}`}>{f.severity}</td>
                  <td className="mono">{f.code}</td>
                  <td>{f.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="row" style={{ marginTop: '0.75rem' }}>
          <Link className="btn" to="/timeline">
            Open timeline
          </Link>
          <Link className="btn secondary" to="/report">
            Open report
          </Link>
        </div>
      </section>
    </div>
  )
}