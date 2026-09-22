import { describe, expect, it } from 'vitest'
import { boundsOf, formatCoord, gridValues, haversineM, makeProjection, scaleBar } from './geo'

describe('haversine', () => {
  it('measures known distances', () => {
    expect(haversineM({ lat: 0, lon: 0 }, { lat: 0, lon: 0 })).toBe(0)
    // one degree of latitude is ~111.2 km
    expect(haversineM({ lat: 12, lon: 77 }, { lat: 13, lon: 77 })).toBeCloseTo(111_195, -2)
  })
})

describe('projection', () => {
  const points = [
    { lat: 12.97, lon: 77.59 },
    { lat: 12.98, lon: 77.61 },
  ]

  it('fits points inside the viewport with north up', () => {
    const bounds = boundsOf(points)!
    const p = makeProjection(bounds, 400, 300, 20)
    for (const pt of points) {
      expect(p.x(pt.lon)).toBeGreaterThanOrEqual(20 - 1e-6)
      expect(p.x(pt.lon)).toBeLessThanOrEqual(380 + 1e-6)
      expect(p.y(pt.lat)).toBeGreaterThanOrEqual(20 - 1e-6)
      expect(p.y(pt.lat)).toBeLessThanOrEqual(280 + 1e-6)
    }
    expect(p.y(12.98)).toBeLessThan(p.y(12.97)) // higher latitude is higher on screen
    expect(p.x(77.61)).toBeGreaterThan(p.x(77.59))
  })

  it('keeps distances isotropic: equal ground distance is equal on screen in x and y', () => {
    const p = makeProjection(boundsOf(points)!, 400, 400, 20)
    const north = Math.abs(p.y(13.0) - p.y(12.99))
    const dLon = 0.01 / Math.cos((12.99 * Math.PI) / 180)
    const east = Math.abs(p.x(77.6 + dLon) - p.x(77.6))
    expect(east).toBeCloseTo(north, 1)
  })

  it('does not explode for a single stationary point', () => {
    const b = boundsOf([{ lat: 12.9, lon: 77.5 }])!
    const p = makeProjection(b, 400, 300)
    expect(Number.isFinite(p.x(77.5))).toBe(true)
    expect(p.metresPerPixel).toBeGreaterThan(0.1)
    expect(p.x(77.5)).toBeCloseTo(200)
  })
})

describe('scale bar and grid', () => {
  it('chooses a 1-2-5 length that fits', () => {
    for (const mpp of [0.5, 3, 27, 900]) {
      const bar = scaleBar(mpp, 120)
      expect(bar.pixels).toBeLessThanOrEqual(120)
      expect(bar.pixels).toBeGreaterThan(120 / 5.1)
      expect(String(bar.metres)).toMatch(/^[125]0*$|^0\.[125]$/)
    }
    expect(scaleBar(40, 120).label).toBe('4 km'.replace('4', '2')) // 4800 m max -> 2 km
    expect(scaleBar(1, 120).label).toBe('100 m')
  })

  it('emits round grid values inside the range', () => {
    const values = gridValues(12.9701, 12.9799, 4)
    expect(values.length).toBeGreaterThan(0)
    expect(values.length).toBeLessThanOrEqual(6)
    for (const v of values) {
      expect(v).toBeGreaterThanOrEqual(12.9701)
      expect(v).toBeLessThanOrEqual(12.9799)
    }
    expect(gridValues(5, 5, 4)).toEqual([])
  })

  it('formats hemispheres', () => {
    expect(formatCoord(12.97, 'N', 'S')).toBe('12.97000° N')
    expect(formatCoord(-77.5, 'E', 'W', 2)).toBe('77.50° W')
  })
})
