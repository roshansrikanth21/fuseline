/** Time helpers shared by the chart, tables and drawer. All instants are epoch milliseconds. */

export type Range = { start: number; end: number }

export const SECOND = 1000
export const MINUTE = 60 * SECOND
export const HOUR = 60 * MINUTE
export const DAY = 24 * HOUR

export const MIN_SPAN_MS = SECOND

export function clamp(value: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, value))
}

const formatterCache = new Map<string, Intl.DateTimeFormat>()

function formatter(timeZone: string, options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = `${timeZone}|${JSON.stringify(options)}`
  let f = formatterCache.get(key)
  if (!f) {
    f = new Intl.DateTimeFormat('en-GB', { timeZone, hourCycle: 'h23', ...options })
    formatterCache.set(key, f)
  }
  return f
}

export function isValidTimeZone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat('en-GB', { timeZone: tz })
    return true
  } catch {
    return false
  }
}

/** Offset of `timeZone` from UTC at instant `ms`, in milliseconds (east of UTC is positive). */
export function tzOffsetMs(ms: number, timeZone: string): number {
  if (timeZone === 'UTC') return 0
  const parts = formatter(timeZone, {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
  }).formatToParts(new Date(Math.floor(ms / 1000) * 1000))
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0)
  const asUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour') % 24, get('minute'), get('second'))
  return asUtc - Math.floor(ms / 1000) * 1000
}

/** `2024-06-15 10:00:00` (plus `.mmm` when `withMs`) in the given zone. */
export function formatDateTime(ms: number, timeZone = 'UTC', withMs = false): string {
  const p = formatter(timeZone, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(new Date(ms))
  const g = (t: string) => p.find((x) => x.type === t)?.value ?? ''
  const base = `${g('year')}-${g('month')}-${g('day')} ${g('hour')}:${g('minute')}:${g('second')}`
  return withMs ? `${base}.${String(((ms % 1000) + 1000) % 1000).padStart(3, '0')}` : base
}

export function formatTimeOfDay(ms: number, timeZone = 'UTC', withSeconds = true): string {
  return formatter(timeZone, {
    hour: '2-digit',
    minute: '2-digit',
    ...(withSeconds ? { second: '2-digit' } : {}),
  }).format(new Date(ms))
}

export function zoneLabel(timeZone: string): string {
  if (timeZone === 'UTC') return 'UTC'
  const off = tzOffsetMs(Date.now(), timeZone) / MINUTE
  const sign = off < 0 ? '-' : '+'
  const abs = Math.abs(off)
  const hh = String(Math.floor(abs / 60)).padStart(2, '0')
  const mm = String(abs % 60).padStart(2, '0')
  return `${timeZone} (UTC${sign}${hh}:${mm})`
}

export function formatDuration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, '0')}s`
  const h = Math.floor(m / 60)
  if (h < 48) return `${h}h ${String(m % 60).padStart(2, '0')}m`
  return `${Math.floor(h / 24)}d ${h % 24}h`
}

export type Tick = { t: number; label: string; major: boolean }

const STEPS = [
  SECOND, 2 * SECOND, 5 * SECOND, 10 * SECOND, 15 * SECOND, 30 * SECOND,
  MINUTE, 2 * MINUTE, 5 * MINUTE, 10 * MINUTE, 15 * MINUTE, 30 * MINUTE,
  HOUR, 2 * HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR,
  DAY, 2 * DAY, 7 * DAY, 14 * DAY, 30 * DAY, 90 * DAY, 365 * DAY,
] // prettier-ignore

/** Round tick positions covering `range`, aligned to wall-clock boundaries in `timeZone`. */
export function niceTicks(range: Range, maxTicks: number, timeZone = 'UTC'): Tick[] {
  const span = Math.max(range.end - range.start, 1)
  const step = STEPS.find((s) => span / s <= maxTicks) ?? STEPS[STEPS.length - 1]
  const offset = tzOffsetMs((range.start + range.end) / 2, timeZone)
  const first = Math.ceil((range.start + offset) / step) * step - offset
  const ticks: Tick[] = []
  for (let t = first; t <= range.end && ticks.length < maxTicks * 2; t += step) {
    const local = t + offset
    const midnight = ((local % DAY) + DAY) % DAY === 0
    let label: string
    if (step >= DAY) label = formatter(timeZone, { day: '2-digit', month: 'short' }).format(new Date(t))
    else if (midnight) label = formatter(timeZone, { day: '2-digit', month: 'short' }).format(new Date(t))
    else label = formatTimeOfDay(t, timeZone, step < MINUTE)
    ticks.push({ t, label, major: midnight || step >= DAY })
  }
  return ticks
}

/** Scale `range` by `factor` (<1 zooms in) keeping the instant at `anchor` fixed on screen. */
export function zoomRange(range: Range, factor: number, anchor: number, bounds: Range): Range {
  const fullSpan = bounds.end - bounds.start
  const span = clamp((range.end - range.start) * factor, Math.min(MIN_SPAN_MS, fullSpan), fullSpan)
  const ratio = (anchor - range.start) / Math.max(range.end - range.start, 1)
  return shiftInto({ start: anchor - ratio * span, end: anchor - ratio * span + span }, bounds)
}

export function panRange(range: Range, deltaMs: number, bounds: Range): Range {
  return shiftInto({ start: range.start + deltaMs, end: range.end + deltaMs }, bounds)
}

/** Slide `range` (keeping its width) so it sits inside `bounds`. */
export function shiftInto(range: Range, bounds: Range): Range {
  const width = range.end - range.start
  if (width >= bounds.end - bounds.start) return { ...bounds }
  const start = clamp(range.start, bounds.start, bounds.end - width)
  return { start, end: start + width }
}

/** Widen `[start, end]` by `padRatio` of its span on each side (at least `minPad` ms). */
export function padRange(start: number, end: number, padRatio = 0.35, minPad = 30 * SECOND): Range {
  const pad = Math.max((end - start) * padRatio, minPad)
  return { start: start - pad, end: end + pad }
}

export function rangesEqual(a: Range, b: Range, epsilonMs = 1): boolean {
  return Math.abs(a.start - b.start) <= epsilonMs && Math.abs(a.end - b.end) <= epsilonMs
}

/** Binary-search the index in `sorted` (ascending) whose value is closest to `value`. */
export function nearestIndex(sorted: number[], value: number): number {
  if (sorted.length === 0) return -1
  let lo = 0
  let hi = sorted.length - 1
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (sorted[mid] < value) lo = mid + 1
    else hi = mid
  }
  if (lo > 0 && Math.abs(sorted[lo - 1] - value) <= Math.abs(sorted[lo] - value)) return lo - 1
  return lo
}
