import { useEffect, useState } from 'react'

/**
 * Track an element's width via ResizeObserver. Returns a *callback ref*, so measuring starts
 * whenever the element actually mounts, even if the component rendered something else first
 * (an empty state, say). Falls back to `initial` when there is no layout (tests, hidden tabs).
 */
export function useElementWidth<T extends HTMLElement>(initial = 800): [(el: T | null) => void, number] {
  const [el, setEl] = useState<T | null>(null)
  const [width, setWidth] = useState(initial)

  useEffect(() => {
    if (!el) return
    const measure = () => {
      const w = Math.floor(el.getBoundingClientRect().width)
      if (w > 0) setWidth(w)
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(el)
    return () => observer.disconnect()
  }, [el])

  return [setEl, width]
}
