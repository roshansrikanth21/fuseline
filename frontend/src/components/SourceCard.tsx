import { useState } from 'react'
import type { ReactNode } from 'react'
import type { Artifact } from '../api/client'
import { formatBytes, formatCount } from '../lib/format'
import { formatDateTime } from '../lib/time'
import { CopyButton } from './CopyButton'

type Props = {
  source: string
  label: string
  help: string
  artifacts: Artifact[]
  totalEvents: number
  integrityBySource?: Map<string, 'ok' | 'modified' | 'missing'>
  dragOver: boolean
  onDragOver: () => void
  onDragLeave: () => void
  onDrop: (files: File[]) => void
  onChoose: (files: File[]) => void
  disabled: boolean
  children?: ReactNode
}

/** One evidence category: status, a quick-drop target scoped to this source, and its files as a small tree. */
export function SourceCard({
  source,
  label,
  help,
  artifacts,
  totalEvents,
  integrityBySource,
  dragOver,
  onDragOver,
  onDragLeave,
  onDrop,
  onChoose,
  disabled,
  children,
}: Props) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="source-card">
      <div className="source-card-head">
        <span className={`dot ${source}`} aria-hidden="true" />
        <div className="source-card-title">
          <h3>{label}</h3>
          <p className="muted small">{help}</p>
        </div>
        <div className="source-card-status">
          {artifacts.length > 0 ? (
            <span className="mono small">
              {artifacts.length} file{artifacts.length === 1 ? '' : 's'} · {formatCount(totalEvents)} events
            </span>
          ) : (
            <span className="muted small">Not yet acquired</span>
          )}
        </div>
      </div>

      <div className="source-card-actions">
        <div
          className={`dropzone compact${dragOver ? ' active' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            onDragOver()
          }}
          onDragLeave={onDragLeave}
          onDrop={(e) => {
            e.preventDefault()
            onDrop(Array.from(e.dataTransfer.files))
          }}
        >
          <span className="muted small">Drop file, or</span>
          <label className="btn secondary small file-btn">
            Choose…
            <input
              type="file"
              disabled={disabled}
              onChange={(e) => {
                onChoose(Array.from(e.target.files ?? []))
                e.target.value = ''
              }}
            />
          </label>
        </div>
        {children}
      </div>

      {artifacts.length > 0 ? (
        <div className="source-tree">
          <button
            type="button"
            className="source-tree-toggle"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
          >
            <span className={`tree-caret${expanded ? ' open' : ''}`} aria-hidden="true" />
            files
          </button>
          {expanded ? (
            <ul className="source-tree-list">
              {artifacts.map((a) => {
                const status = integrityBySource?.get(a.id)
                return (
                  <li key={a.id} className="source-tree-item">
                    <span className="tree-branch" aria-hidden="true" />
                    <div className="source-tree-row">
                      <div className="cell-title">{a.original_name}</div>
                      <div className="cell-sub mono">
                        {a.parser} · {formatBytes(a.size_bytes)} · {formatDateTime(Date.parse(a.ingested_at))}
                        {a.skipped_rows > 0 ? (
                          <span className="warn-text" title={a.notes.join('\n')}>
                            {' '}
                            · {formatCount(a.skipped_rows)} rows skipped
                          </span>
                        ) : null}
                      </div>
                      <div className="cell-sub mono hash-row">
                        {a.sha256}
                        <CopyButton value={a.sha256} />
                        {status ? <span className={`sev sev-${status === 'ok' ? 'pass' : 'fail'}`}> {status}</span> : null}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
