import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, type Case } from '../api/client'

const STORAGE_KEY = 'fuseline.activeCase'

type CaseContextValue = {
  caseId: string | null
  activeCase: Case | null
  selectCase: (id: string | null) => void
  /** Re-read the active case (counts, timezone) after something changed it. */
  refreshCase: () => Promise<void>
}

const CaseContext = createContext<CaseContextValue | null>(null)

function readStored(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function CaseProvider({ children }: { children: ReactNode }) {
  const [caseId, setCaseId] = useState<string | null>(readStored)
  const [activeCase, setActiveCase] = useState<Case | null>(null)

  const selectCase = useCallback((id: string | null) => {
    setCaseId(id)
    if (id === null) setActiveCase(null)
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id)
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* storage unavailable */
    }
  }, [])

  const refreshCase = useCallback(async () => {
    if (!caseId) return
    try {
      setActiveCase(await api.getCase(caseId))
    } catch {
      selectCase(null)
    }
  }, [caseId, selectCase])

  useEffect(() => {
    if (!caseId) return
    let cancelled = false
    api
      .getCase(caseId)
      .then((c) => {
        if (!cancelled) setActiveCase(c)
      })
      .catch(() => {
        if (!cancelled) selectCase(null)
      })
    return () => {
      cancelled = true
    }
  }, [caseId, selectCase])

  const value = useMemo(
    () => ({ caseId, activeCase, selectCase, refreshCase }),
    [caseId, activeCase, selectCase, refreshCase],
  )
  return <CaseContext.Provider value={value}>{children}</CaseContext.Provider>
}

export function useCase(): CaseContextValue {
  const ctx = useContext(CaseContext)
  if (!ctx) throw new Error('useCase must be used inside <CaseProvider>')
  return ctx
}
