import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { type Artifact, type Finding, type IngestResult, type IntegrityResult, type Meta, api } from '../api/client'
import { Callout } from '../components/Callout'
import { CopyButton } from '../components/CopyButton'
import { FindingsTable } from '../components/FindingsTable'
import { NoCase } from '../components/NoCase'
import { SourceChip } from '../components/SourceChip'
import { formatBytes, formatCount } from '../lib/format'
import { formatDateTime } from '../lib/time'
import { useCase } from '../state/CaseContext'

const HINTS = [
  { value: 'auto', label: 'Auto-detect (recommended)' },
  { value: 'browsing', label: 'Browsing history' },
  { value: 'app_usage', label: 'App usage' },
  { value: 'location', label: 'Location' },
  { value: 'plaso', label: 'Plaso timeline' },
]

type QueueItem = {
  id: string
  name: string
  size: number
  status: 'queued' | 'uploading' | 'done' | 'error'
  progress: number
  result?: IngestResult
  error?: string
}

export function AcquirePage() {
  const { caseId, refreshCase } = useCase()
  if (!caseId) return <NoCase title="Acquire" />
  return <Acquire key={caseId} caseId={caseId} onChanged={refreshCase} />
}

function Acquire({ caseId, onChanged }: { caseId: string; onChanged: () => Promise<void> }) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [meta, setMeta] = useState<Meta | null>(null)
  const [hint, setHint] = useState('auto')
  const [dragOver, setDragOver] = useState(false)
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [demoBusy, setDemoBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [integrity, setIntegrity] = useState<IntegrityResult | null>(null)
  const [verifying, setVerifying] = useState(false)

  const pending = useRef<{ id: string; file: File; hint: string }[]>([])
  const draining = useRef(false)

  const refresh = useCallback(async () => {
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
    api
      .meta()
      .then(setMeta)
      .catch(() => undefined)
  }, [refresh])

  const patch = (id: string, change: Partial<QueueItem>) =>
    setQueue((items) => items.map((it) => (it.id === id ? { ...it, ...change } : it)))

  const drain = useCallback(async () => {
    if (draining.current) return
    draining.current = true
    try {
      while (pending.current.length > 0) {
        const next = pending.current.shift()
        if (!next) break
        patch(next.id, { status: 'uploading', progress: 0 })
        try {
          const result = await api.upload(caseId, next.file, next.hint, (p) => patch(next.id, { progress: p }))
          patch(next.id, { status: 'done', progress: 1, result })
        } catch (err) {
          patch(next.id, { status: 'error', error: err instanceof Error ? err.message : 'Upload failed' })
        }
      }
    } finally {
      draining.current = false
      setIntegrity(null)
      await refresh()
      await onChanged()
    }
  }, [caseId, refresh, onChanged])

  function enqueue(files: File[]) {
    if (files.length === 0) return
    setMessage(null)
    setError(null)
    const limit = meta?.max_upload_bytes ?? Number.POSITIVE_INFINITY
    const items: QueueItem[] = files.map((file) => ({
      id: crypto.randomUUID(),
      name: file.name,
      size: file.size,
      status: file.size > limit ? 'error' : 'queued',
      progress: 0,
      error: file.size > limit ? `Larger than the ${formatBytes(limit)} upload limit.` : undefined,
    }))
    setQueue((prev) => [...items, ...prev])
    files.forEach((file, i) => {
      if (items[i].status === 'queued') pending.current.push({ id: items[i].id, file, hint })
    })
    void drain()
  }

  async function loadDemo() {
    setDemoBusy(true)
    setError(null)
    setMessage(null)
    try {
      const result = await api.loadDemo(caseId)
      setMessage(
        result.events_added === 0
          ? 'The sample pack is already loaded in this case (same SHA-256 hashes) — nothing added.'
          : `Loaded sample evidence: ${result.events_added} events from ${result.artifacts.length} artifacts, ${result.sessions_rebuilt} proximity sessions.`,
      )
      setIntegrity(null)
      await refresh()
      await onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Demo load failed')
    } finally {
      setDemoBusy(false)
    }
  }

  async function verify() {
    setVerifying(true)
    setError(null)
    try {
      setIntegrity(await api.verify(caseId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setVerifying(false)
    }
  }

  const integrityById = new Map(integrity?.artifacts.map((a) => [a.artifact_id, a.status]) ?? [])
  const busy = queue.some((q) => q.status === 'uploading' || q.status === 'queued') || demoBusy

  return (
    <div className="stack">
      <section className="panel">
        <h1>Acquire</h1>
        <p className="muted">
          Add evidence files. Each is hashed (SHA-256), stored read-only, parsed, and normalised to UTC. Files are
          recognised by their <strong>content</strong>, never their name.
        </p>

        <div className="row wrap-gap">
          <label className="inline-field">
            Source hint
            <select value={hint} onChange={(e) => setHint(e.target.value)} disabled={busy}>
              {HINTS.map((h) => (
                <option key={h.value} value={h.value}>
                  {h.label}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn amber" disabled={busy} onClick={() => void loadDemo()}>
            {demoBusy ? 'Loading…' : 'Load sample evidence'}
          </button>
        </div>

        <div
          className={`dropzone${dragOver ? ' active' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            enqueue(Array.from(e.dataTransfer.files))
          }}
        >
          <p>
            <strong>Drop artifacts here</strong>, or
          </p>
          <label className="btn secondary file-btn">
            Choose files…
            <input
              type="file"
              multiple
              onChange={(e) => {
                enqueue(Array.from(e.target.files ?? []))
                e.target.value = ''
              }}
            />
          </label>
          {meta ? (
            <p className="muted small">Up to {formatBytes(meta.max_upload_bytes)} per file. Multiple files upload one at a time.</p>
          ) : null}
        </div>

        {meta ? (
          <details className="formats">
            <summary>Supported formats</summary>
            <ul>
              {meta.formats.map((f) => (
                <li key={f.parser}>
                  <SourceChip source={f.source} /> {f.label}
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        {message ? <Callout tone="pass">{message}</Callout> : null}
        {error ? <div className="error-box">{error}</div> : null}

        {queue.length > 0 ? (
          <ul className="queue" aria-label="Upload results">
            {queue.map((item) => (
              <li key={item.id} className={`queue-item ${item.status}`}>
                <div className="queue-main">
                  <span className="queue-name">{item.name}</span>
                  <span className="mono muted">{formatBytes(item.size)}</span>
                </div>
                <div className="queue-status">
                  {item.status === 'queued' ? <span className="muted">Waiting…</span> : null}
                  {item.status === 'uploading' ? (
                    <progress value={item.progress} max={1} aria-label={`Uploading ${item.name}`} />
                  ) : null}
                  {item.status === 'error' ? <span className="bad-text">{item.error}</span> : null}
                  {item.status === 'done' && item.result ? <QueueResult result={item.result} /> : null}
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>Artifact inventory</h2>
            <p className="muted small">Hashes are recorded at acquisition; verification re-hashes the stored copies.</p>
          </div>
          <button
            type="button"
            className="btn secondary small"
            disabled={verifying || artifacts.length === 0}
            onClick={() => void verify()}
          >
            {verifying ? 'Verifying…' : 'Verify integrity'}
          </button>
        </div>

        {integrity ? (
          integrity.ok ? (
            <Callout tone="pass" title="Integrity verified">
              All {integrity.artifacts.length} stored artifacts match the hashes recorded at acquisition, and the audit
              chain is intact.
            </Callout>
          ) : (
            <Callout tone="fail" title="Integrity check failed">
              {integrity.artifacts.filter((a) => a.status !== 'ok').length > 0
                ? 'One or more stored evidence copies no longer match their recorded hash. '
                : ''}
              {!integrity.audit_chain_ok ? `The audit log was altered (first bad entry #${integrity.audit_first_bad_entry}).` : ''}
            </Callout>
          )
        ) : null}

        {artifacts.length === 0 ? (
          <div className="empty">No artifacts yet.</div>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">Artifact</th>
                  <th scope="col">Type</th>
                  <th scope="col" className="num">
                    Events
                  </th>
                  <th scope="col" className="num">
                    Skipped
                  </th>
                  <th scope="col">SHA-256</th>
                  <th scope="col">Acquired (UTC)</th>
                  {integrity ? <th scope="col">Integrity</th> : null}
                </tr>
              </thead>
              <tbody>
                {artifacts.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <div className="cell-title">{a.original_name}</div>
                      <div className="cell-sub mono">
                        {a.parser} · {formatBytes(a.size_bytes)}
                      </div>
                    </td>
                    <td>
                      <SourceChip source={a.source_type} />
                    </td>
                    <td className="num">{formatCount(a.row_count)}</td>
                    <td className="num" title={a.notes.join('\n')}>
                      {a.skipped_rows > 0 ? <span className="warn-text">{formatCount(a.skipped_rows)}</span> : 0}
                    </td>
                    <td>
                      <span className="mono hash">{a.sha256}</span> <CopyButton value={a.sha256} />
                    </td>
                    <td className="mono nowrap">{formatDateTime(Date.parse(a.ingested_at))}</td>
                    {integrity ? (
                      <td>
                        <span className={`sev sev-${integrityById.get(a.id) === 'ok' ? 'pass' : 'fail'}`}>
                          {integrityById.get(a.id) ?? '—'}
                        </span>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Validation snapshot</h2>
        <FindingsTable findings={findings} empty="Validation runs after ingest." />
        <div className="row">
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

function QueueResult({ result }: { result: IngestResult }) {
  if (result.duplicate) {
    return (
      <span className="muted">
        Already in this case (identical SHA-256 to <strong>{result.artifact.original_name}</strong>) — nothing added.
      </span>
    )
  }
  const a = result.artifact
  return (
    <div>
      <span className="ok-text">
        Ingested as <SourceChip source={a.source_type} /> · {formatCount(result.events_added)} events
        {a.skipped_rows > 0 ? ` · ${formatCount(a.skipped_rows)} rows skipped` : ''}
      </span>
      {a.notes.map((n) => (
        <div key={n} className="cell-sub warn-text">
          {n}
        </div>
      ))}
    </div>
  )
}
