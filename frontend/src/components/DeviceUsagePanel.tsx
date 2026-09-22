import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { type AdbDevice, type IngestResult, ApiError, api } from '../api/client'
import { formatCount } from '../lib/format'

type Props = {
  caseId: string
  onImported: (result: IngestResult) => void
}

const POLL_MS = 2000

/**
 * "Plug in your phone" flow for app usage: polls for an ADB-connected device and, once one is
 * authorised, pulls `dumpsys usagestats` and ingests it through the normal pipeline. Everything
 * else (browsing, location) still needs the manual steps — a browser genuinely cannot reach a
 * USB device's private app data without root, so this never pretends otherwise.
 */
export function DeviceUsagePanel({ caseId, onImported }: Props) {
  const [open, setOpen] = useState(false)
  const [devices, setDevices] = useState<AdbDevice[] | null>(null)
  const [adbMissing, setAdbMissing] = useState<string | null>(null)
  const [pulling, setPulling] = useState(false)
  const [result, setResult] = useState<IngestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    const poll = async () => {
      try {
        const found = await api.devices()
        if (cancelled) return
        setDevices(found)
        setAdbMissing(null)
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 503) setAdbMissing(err.message)
        else setDevices([])
      }
      if (!cancelled) timer.current = setTimeout(poll, POLL_MS)
    }
    void poll()
    return () => {
      cancelled = true
      clearTimeout(timer.current)
    }
  }, [open])

  async function pull(serial: string) {
    setPulling(true)
    setError(null)
    setResult(null)
    try {
      const r = await api.pullDeviceAppUsage(caseId, serial)
      setResult(r)
      onImported(r)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pull failed')
    } finally {
      setPulling(false)
    }
  }

  if (!open) {
    return (
      <button type="button" className="btn secondary small" onClick={() => setOpen(true)}>
        Detect device…
      </button>
    )
  }

  const ready = devices?.find((d) => d.ready)

  return (
    <div className="device-panel">
      <div className="device-panel-head">
        <span className="scan-dot" aria-hidden="true" />
        <span className="mono small">{adbMissing ? 'adb unavailable' : 'Watching for a connected phone…'}</span>
        <button type="button" className="btn ghost small" onClick={() => setOpen(false)}>
          Close
        </button>
      </div>

      {adbMissing ? (
        <p className="muted small">{adbMissing}</p>
      ) : devices === null ? (
        <p className="muted small">Checking…</p>
      ) : devices.length === 0 ? (
        <p className="muted small">
          No device detected. Plug your phone in via USB with debugging enabled — see the setup steps below.
        </p>
      ) : (
        <ul className="device-list">
          {devices.map((d) => (
            <li key={d.serial} className="device-row">
              <span className={`sev ${d.ready ? 'sev-pass' : 'sev-warn'}`}>{d.state}</span>
              <span className="mono">{d.model ?? d.serial}</span>
              {!d.ready ? (
                <span className="muted small">Accept the USB debugging prompt on the phone screen.</span>
              ) : pulling ? (
                <span className="scan-bar" aria-label="Reading usage stats" />
              ) : (
                <button type="button" className="btn accent small" onClick={() => void pull(d.serial)}>
                  Pull app usage
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {error ? <div className="error-box">{error}</div> : null}
      {result ? (
        <p className="ok-text small">
          {result.duplicate ? (
            'Already pulled from this device (same data) — nothing added.'
          ) : (
            <>
              Imported {formatCount(result.events_added)} app-usage events. Open{' '}
              <Link to="/timeline">Timeline</Link> to inspect them (Acquire only lists the evidence file + hash).
            </>
          )}
        </p>
      ) : null}

      {!ready ? (
        <details className="formats">
          <summary>Phone not showing up?</summary>
          <ol>
            <li>
              Fuseline bundles <span className="mono">adb</span> under{" "}
              <span className="mono">tools/platform-tools/</span> (run{" "}
              <span className="mono">python scripts/ensure_platform_tools.py</span> once if missing)
            </li>
            <li>Settings → About phone → tap &quot;Build number&quot; 7 times to unlock Developer options</li>
            <li>Settings → Developer options → turn on USB debugging</li>
            <li>Connect via USB and accept the authorisation prompt on the phone screen</li>
            <li>Only app usage is pulled live; browsing and location still need uploaded files</li>
          </ol>
        </details>
      ) : null}
    </div>
  )
}
