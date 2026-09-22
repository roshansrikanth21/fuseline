import { describe, expect, it } from 'vitest'
import {
  DAY,
  HOUR,
  MINUTE,
  SECOND,
  formatDateTime,
  formatDuration,
  isValidTimeZone,
  nearestIndex,
  niceTicks,
  padRange,
  panRange,
  shiftInto,
  tzOffsetMs,
  zoneLabel,
  zoomRange,
} from './time'

const JUNE_15 = Date.UTC(2024, 5, 15, 10, 0, 0)

describe('time zones', () => {
  it('computes offsets, including half-hour zones and DST', () => {
    expect(tzOffsetMs(JUNE_15, 'UTC')).toBe(0)
    expect(tzOffsetMs(JUNE_15, 'Asia/Kolkata')).toBe(5.5 * HOUR)
    expect(tzOffsetMs(JUNE_15, 'America/New_York')).toBe(-4 * HOUR) // EDT
    expect(tzOffsetMs(Date.UTC(2024, 0, 15), 'America/New_York')).toBe(-5 * HOUR) // EST
  })

  it('formats instants in a zone', () => {
    expect(formatDateTime(JUNE_15)).toBe('2024-06-15 10:00:00')
    expect(formatDateTime(JUNE_15, 'Asia/Kolkata')).toBe('2024-06-15 15:30:00')
    expect(formatDateTime(JUNE_15 + 123, 'UTC', true)).toBe('2024-06-15 10:00:00.123')
  })

  it('validates zone names and labels them', () => {
    expect(isValidTimeZone('Asia/Kolkata')).toBe(true)
    expect(isValidTimeZone('Mars/Base')).toBe(false)
    expect(zoneLabel('UTC')).toBe('UTC')
    expect(zoneLabel('Asia/Kolkata')).toBe('Asia/Kolkata (UTC+05:30)')
  })
})

describe('formatDuration', () => {
  it('picks a readable unit', () => {
    expect(formatDuration(45 * SECOND)).toBe('45s')
    expect(formatDuration(3 * MINUTE + 5 * SECOND)).toBe('3m 05s')
    expect(formatDuration(2 * HOUR + 30 * MINUTE)).toBe('2h 30m')
    expect(formatDuration(3 * DAY + 4 * HOUR)).toBe('3d 4h')
  })
})

describe('niceTicks', () => {
  it('produces round, bounded ticks inside the range', () => {
    const range = { start: JUNE_15, end: JUNE_15 + 2 * HOUR }
    const ticks = niceTicks(range, 8)
    expect(ticks.length).toBeGreaterThan(2)
    expect(ticks.length).toBeLessThanOrEqual(16)
    for (const t of ticks) {
      expect(t.t).toBeGreaterThanOrEqual(range.start)
      expect(t.t).toBeLessThanOrEqual(range.end)
      expect(t.t % (15 * MINUTE)).toBe(0)
    }
    expect(ticks[0].label).toMatch(/^\d{2}:\d{2}$/)
  })

  it('aligns to local wall-clock boundaries in another zone', () => {
    const ticks = niceTicks({ start: JUNE_15, end: JUNE_15 + 2 * HOUR }, 8, 'Asia/Kolkata')
    for (const t of ticks) expect((t.t + 5.5 * HOUR) % (15 * MINUTE)).toBe(0)
  })

  it('marks midnight as a major tick with a date label', () => {
    const midnight = Date.UTC(2024, 5, 16)
    const ticks = niceTicks({ start: midnight - 6 * HOUR, end: midnight + 6 * HOUR }, 8)
    const tick = ticks.find((t) => t.t === midnight)
    expect(tick?.major).toBe(true)
    expect(tick?.label).toBe('16 Jun')
  })

  it('switches to seconds for tiny spans and dates for huge ones', () => {
    expect(niceTicks({ start: JUNE_15, end: JUNE_15 + 20 * SECOND }, 8)[0].label).toMatch(/^\d{2}:\d{2}:\d{2}$/)
    const wide = niceTicks({ start: JUNE_15, end: JUNE_15 + 400 * DAY }, 8)
    expect(wide.length).toBeLessThanOrEqual(16)
    expect(wide.every((t) => t.major)).toBe(true)
  })
})

describe('view maths', () => {
  const bounds = { start: 0, end: 1000 * SECOND }

  it('zooms about an anchor, keeping it fixed on screen', () => {
    const view = { start: 100 * SECOND, end: 300 * SECOND }
    const anchor = 150 * SECOND // 25% across
    const zoomed = zoomRange(view, 0.5, anchor, bounds)
    expect(zoomed.end - zoomed.start).toBe(100 * SECOND)
    expect((anchor - zoomed.start) / (zoomed.end - zoomed.start)).toBeCloseTo(0.25)
  })

  it('never zooms out past the data or in past one second', () => {
    expect(zoomRange({ start: 0, end: 900 * SECOND }, 10, 450 * SECOND, bounds)).toEqual(bounds)
    const tight = zoomRange({ start: 0, end: 10 * SECOND }, 0.0001, 5 * SECOND, bounds)
    expect(tight.end - tight.start).toBe(SECOND)
  })

  it('pans but stays inside the bounds', () => {
    const view = { start: 100 * SECOND, end: 200 * SECOND }
    expect(panRange(view, 50 * SECOND, bounds)).toEqual({ start: 150 * SECOND, end: 250 * SECOND })
    expect(panRange(view, -500 * SECOND, bounds)).toEqual({ start: 0, end: 100 * SECOND })
    expect(panRange(view, 5000 * SECOND, bounds)).toEqual({ start: 900 * SECOND, end: 1000 * SECOND })
  })

  it('shiftInto returns the bounds when the range is wider than them', () => {
    expect(shiftInto({ start: -10, end: 5000 * SECOND }, bounds)).toEqual(bounds)
  })

  it('pads a range by a ratio with a floor', () => {
    expect(padRange(1000 * SECOND, 1100 * SECOND, 0.5)).toEqual({ start: 950 * SECOND, end: 1150 * SECOND })
    const floor = padRange(1000 * SECOND, 1001 * SECOND)
    expect(floor.start).toBe(1000 * SECOND - 30 * SECOND)
  })
})

describe('nearestIndex', () => {
  const values = [10, 20, 40, 80]
  it('finds the closest value', () => {
    expect(nearestIndex(values, 0)).toBe(0)
    expect(nearestIndex(values, 26)).toBe(1)
    expect(nearestIndex(values, 31)).toBe(2)
    expect(nearestIndex(values, 1000)).toBe(3)
    expect(nearestIndex([], 5)).toBe(-1)
  })
})
