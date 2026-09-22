import { useCallback, useEffect, useState } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'
const STORAGE_KEY = 'fuseline.theme'

function readPreference(): ThemePreference {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

const query = () => (typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-color-scheme: dark)') : null)

export function useTheme(): { preference: ThemePreference; resolved: 'light' | 'dark'; cycle: () => void } {
  const [preference, setPreference] = useState<ThemePreference>(readPreference)
  const [systemDark, setSystemDark] = useState(() => query()?.matches ?? false)

  useEffect(() => {
    const mq = query()
    if (!mq) return
    const onChange = () => setSystemDark(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', resolved)
  }, [resolved])

  const cycle = useCallback(() => {
    setPreference((current) => {
      const next: ThemePreference = current === 'system' ? 'dark' : current === 'dark' ? 'light' : 'system'
      try {
        if (next === 'system') localStorage.removeItem(STORAGE_KEY)
        else localStorage.setItem(STORAGE_KEY, next)
      } catch {
        /* storage unavailable */
      }
      return next
    })
  }, [])

  return { preference, resolved, cycle }
}
