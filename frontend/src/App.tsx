import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import { AcquirePage } from './pages/Acquire'
import { CasesPage } from './pages/Cases'
import { ReportPage } from './pages/Report'
import { TimelinePage } from './pages/Timeline'

const STORAGE_KEY = 'fuseline.activeCase'

export default function App() {
  const [activeCaseId, setActiveCaseId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY)
    } catch {
      return null
    }
  })
  const [caseLabel, setCaseLabel] = useState<string | null>(null)
  const [apiOk, setApiOk] = useState<boolean | null>(null)

  useEffect(() => {
    try {
      if (activeCaseId) localStorage.setItem(STORAGE_KEY, activeCaseId)
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }, [activeCaseId])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        await api.health()
        if (!cancelled) setApiOk(true)
      } catch {
        if (!cancelled) setApiOk(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!activeCaseId) {
      setCaseLabel(null)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const c = await api.getCase(activeCaseId)
        if (!cancelled) setCaseLabel(c.name)
      } catch {
        if (!cancelled) {
          setCaseLabel(null)
          setActiveCaseId(null)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [activeCaseId])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-name">Fuseline</div>
          <div className="brand-sub">Mobile forensic timeline</div>
        </div>
        <nav className="nav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : undefined)}>
            Cases
          </NavLink>
          <NavLink to="/acquire" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            Acquire
          </NavLink>
          <NavLink to="/timeline" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            Timeline
          </NavLink>
          <NavLink to="/report" className={({ isActive }) => (isActive ? 'active' : undefined)}>
            Report
          </NavLink>
        </nav>
        <div className="case-chip" title={activeCaseId ?? undefined}>
          {apiOk === false ? 'API offline' : caseLabel ? `case · ${caseLabel}` : 'no case selected'}
        </div>
      </header>
      <main className="main">
        {apiOk === false ? (
          <div className="error-box" style={{ marginBottom: '1rem' }}>
            Backend unreachable. Start it with <span className="mono">scripts/run_dev.ps1</span> or{' '}
            <span className="mono">uvicorn app.main:app --reload --app-dir backend</span>.
          </div>
        ) : null}
        <Routes>
          <Route
            path="/"
            element={<CasesPage activeCaseId={activeCaseId} onSelectCase={setActiveCaseId} />}
          />
          <Route path="/acquire" element={<AcquirePage caseId={activeCaseId} />} />
          <Route path="/timeline" element={<TimelinePage caseId={activeCaseId} />} />
          <Route path="/report" element={<ReportPage caseId={activeCaseId} />} />
        </Routes>
      </main>
    </div>
  )
}