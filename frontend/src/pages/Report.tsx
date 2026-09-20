import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ReportSummary } from '../api/client'
import { SourceChip } from '../components/SourceChip'

type Props = {
  caseId: string | null
}

async function downloadExport(url: string, filename: string): Promise<void> {
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(`Export failed (${res.status})`)
  }
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objectUrl)
}

export function ReportPage({ caseId }: Props) {
  const [report, setReport] = useState<ReportSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!caseId) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.report(caseId)
      setReport(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load report')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    void load()
  }, [load])

  async function onExport(kind: 'html' | 'csv' | 'json') {
    if (!caseId) return
    setExporting(kind)
    setError(null)
    try {
      if (kind === 'html') {
        window.open(`/api/cases/${caseId}/report/html`, '_blank', 'noopener,noreferrer')
        return
      }
      await downloadExport(
        `/api/cases/${caseId}/report/${kind}`,
        `fuseline_${caseId.slice(0, 8)}.${kind}`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setExporting(null)
    }
  }

  if (!caseId) {
    return (
      <section className="panel">
        <h1>Report</h1>
        <div className="empty">
          No active case. <Link to="/">Open a case</Link>
        </div>
      </section>
    )
  }

  return (
    <div className="stack">
      <section className="panel">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Report</h1>
            <p className="muted">Validation findings and examiner exports.</p>
          </div>
          <div className="row">
            <button type="button" className="btn secondary" disabled={loading} onClick={() => void load()}>
              {loading ? 'Loading…' : 'Refresh'}
            </button>
            <button
              type="button"
              className="btn secondary"
              disabled={!!exporting}
              onClick={() => void onExport('html')}
            >
              HTML
            </button>
            <button
              type="button"
              className="btn secondary"
              disabled={!!exporting}
              onClick={() => void onExport('csv')}
            >
              {exporting === 'csv' ? 'CSV…' : 'CSV'}
            </button>
            <button type="button" className="btn" disabled={!!exporting} onClick={() => void onExport('json')}>
              {exporting === 'json' ? 'JSON…' : 'JSON'}
            </button>
          </div>
        </div>

        {error ? <div className="error-box" style={{ marginTop: '0.75rem' }}>{error}</div> : null}

        {report ? (
          <>
            <div className="stat-row" style={{ marginTop: '1rem' }}>
              <div className="stat">
                <div className="n">{report.event_count}</div>
                <div className="l">Events</div>
              </div>
              <div className="stat">
                <div className="n">{report.artifacts.length}</div>
                <div className="l">Artifacts</div>
              </div>
              <div className="stat">
                <div className="n">{report.session_count}</div>
                <div className="l">Sessions</div>
              </div>
            </div>

            <div className="row" style={{ marginTop: '0.75rem' }}>
              {Object.entries(report.source_counts).map(([src, n]) => (
                <span key={src} className="row">
                  <SourceChip source={src} />
                  <span className="mono muted">{n}</span>
                </span>
              ))}
            </div>
          </>
        ) : null}
      </section>

      <section className="panel">
        <h2>Validation</h2>
        {!report || report.findings.length === 0 ? (
          <div className="empty">No findings yet. Acquire evidence first.</div>
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
              {report.findings.map((f) => (
                <tr key={f.id}>
                  <td className={`sev-${f.severity}`}>{f.severity}</td>
                  <td className="mono">{f.code}</td>
                  <td>{f.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <h2>Top proximity sessions</h2>
        {!report || report.sessions.length === 0 ? (
          <div className="empty">No correlated sessions.</div>
        ) : (
          <table className="data">
            <thead>
              <tr>
                <th>Score</th>
                <th>Sources</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {report.sessions.slice(0, 10).map((s) => (
                <tr key={s.id}>
                  <td className="mono">{s.score.toFixed(2)}</td>
                  <td>
                    <div className="row">
                      {s.sources.map((src) => (
                        <SourceChip key={src} source={src} />
                      ))}
                    </div>
                  </td>
                  <td>{s.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
