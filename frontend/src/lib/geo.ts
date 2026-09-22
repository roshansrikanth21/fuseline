/** Offline map maths: the track view draws on plain SVG, so it works air-gapped. */

export type LatLon = { lat: number; lon: number }
export type Bounds = { minLat: number; maxLat: number; minLon: number; maxLon: number }

const EARTH_RADIUS_M = 6_371_008.8

export function haversineM(a: LatLon, b: LatLon): number {
  const rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad
  const dLon = (b.lon - a.lon) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_M * Math.asin(Math.min(1, Math.sqrt(h)))
}

export function boundsOf(points: LatLon[]): Bounds | null {
  if (points.length === 0) return null
  let minLat = Infinity
  let maxLat = -Infinity
  let minLon = Infinity
  let maxLon = -Infinity
  for (const p of points) {
    if (p.lat < minLat) minLat = p.lat
    if (p.lat > maxLat) maxLat = p.lat
    if (p.lon < minLon) minLon = p.lon
    if (p.lon > maxLon) maxLon = p.lon
  }
  return { minLat, maxLat, minLon, maxLon }
}

export type Projection = {
  x: (lon: number) => number
  y: (lat: number) => number
  /** Metres represented by one pixel (near the centre of the view). */
  metresPerPixel: number
  bounds: Bounds
}

/**
 * Equirectangular projection fitted into `width` x `height` with `padding` px margins.
 * Longitude is compressed by cos(latitude) so shapes and distances stay roughly true, and a
 * minimum extent stops a stationary device from being blown up to absurd zoom.
 */
export function makeProjection(
  bounds: Bounds,
  width: number,
  height: number,
  padding = 24,
  minSpanDeg = 0.0015,
): Projection {
  const midLat = (bounds.minLat + bounds.maxLat) / 2
  const midLon = (bounds.minLon + bounds.maxLon) / 2
  const cos = Math.max(Math.cos((midLat * Math.PI) / 180), 0.01)
  const latSpan = Math.max(bounds.maxLat - bounds.minLat, minSpanDeg)
  const lonSpan = Math.max(bounds.maxLon - bounds.minLon, minSpanDeg / cos)
  const usableW = Math.max(width - padding * 2, 1)
  const usableH = Math.max(height - padding * 2, 1)
  const scale = Math.min(usableW / (lonSpan * cos), usableH / latSpan) // px per degree of latitude
  const x = (lon: number) => width / 2 + (lon - midLon) * cos * scale
  const y = (lat: number) => height / 2 - (lat - midLat) * scale
  const metresPerDegree = (Math.PI / 180) * EARTH_RADIUS_M
  return {
    x,
    y,
    metresPerPixel: metresPerDegree / scale,
    bounds: {
      minLat: midLat - height / 2 / scale,
      maxLat: midLat + height / 2 / scale,
      minLon: midLon - width / 2 / (cos * scale),
      maxLon: midLon + width / 2 / (cos * scale),
    },
  }
}

/** Largest "1-2-5" length in metres that fits within `maxPixels`, with its pixel width and label. */
export function scaleBar(metresPerPixel: number, maxPixels: number): { metres: number; pixels: number; label: string } {
  const maxMetres = metresPerPixel * maxPixels
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(maxMetres, 0.1)))
  const metres = [5, 2, 1].map((m) => m * magnitude).find((m) => m <= maxMetres) ?? magnitude
  const label = metres >= 1000 ? `${metres / 1000} km` : `${metres} m`
  return { metres, pixels: metres / metresPerPixel, label }
}

/** Round grid-line values (degrees) inside [lo, hi], at most `maxLines` of them. */
export function gridValues(lo: number, hi: number, maxLines: number): number[] {
  const span = hi - lo
  if (!(span > 0)) return []
  const rough = span / maxLines
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? magnitude * 10
  const values: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) values.push(Number(v.toFixed(8)))
  return values
}

export function formatCoord(value: number, positive: string, negative: string, digits = 5): string {
  return `${Math.abs(value).toFixed(digits)}° ${value >= 0 ? positive : negative}`
}
