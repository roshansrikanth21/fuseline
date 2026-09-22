import { useMemo, useState } from 'react'
import type { LocationPoint, Session } from '../api/client'
import { useElementWidth } from '../hooks/useElementSize'
import { boundsOf, formatCoord, gridValues, makeProjection, scaleBar } from '../lib/geo'
import { formatDateTime } from '../lib/time'

const HEIGHT = 320
const MAX_GAP_FLOOR_MS = 15 * 60_000

type Props = {
  points: LocationPoint[]
  total: number
  selectedId: string | null
  highlightIds: Set<string> | null
  activeSession: Session | null
  onSelectPoint: (id: string) => void
  timeZone: string
}

/** Offline track view: points drawn on a scaled graticule, no tile server involved. */
export function MapPanel({ points, total, selectedId, highlightIds, activeSession, onSelectPoint, timeZone }: Props) {
  const [wrapRef, width] = useElementWidth<HTMLDivElement>(360)
  const [hover, setHover] = useState<LocationPoint | null>(null)

  const projection = useMemo(() => {
    const bounds = boundsOf(points)
    return bounds ? makeProjection(bounds, width, HEIGHT, 28) : null
  }, [points, width])

  const segments = useMemo(() => {
    if (!projection || points.length === 0) return [] as string[]
    const gaps = points.slice(1).map((p, i) => p.ts_ms - points[i].ts_ms).sort((a, b) => a - b)
    const median = gaps.length ? gaps[gaps.length >> 1] : 0
    const maxGap = Math.max(MAX_GAP_FLOOR_MS, median * 10)
    const paths: string[] = []
    let d = ''
    points.forEach((p, i) => {
      const cmd = `${projection.x(p.lon).toFixed(1)} ${projection.y(p.lat).toFixed(1)}`
      if (i === 0 || p.ts_ms - points[i - 1].ts_ms > maxGap) {
        if (d) paths.push(d)
        d = `M${cmd}`
      } else d += `L${cmd}`
    })
    if (d) paths.push(d)
    return paths
  }, [points, projection])

  if (points.length === 0 || !projection) {
    return <div className="empty compact">No location fixes in the current view.</div>
  }

  const t0 = points[0].ts_ms
  const tSpan = Math.max(points[points.length - 1].ts_ms - t0, 1)
  const bar = scaleBar(projection.metresPerPixel, 110)
  const lats = gridValues(projection.bounds.minLat, projection.bounds.maxLat, 4)
  const lons = gridValues(projection.bounds.minLon, projection.bounds.maxLon, 5)
  const sessionCircle =
    activeSession && activeSession.centroid_lat !== null && activeSession.centroid_lon !== null
      ? {
          x: projection.x(activeSession.centroid_lon),
          y: projection.y(activeSession.centroid_lat),
          r: Math.max((activeSession.radius_m ?? 0) / projection.metresPerPixel, 8),
        }
      : null

  function nearest(clientX: number, clientY: number, el: SVGSVGElement): LocationPoint | null {
    const rect = el.getBoundingClientRect()
    const x = clientX - rect.left
    const y = clientY - rect.top
    let best: LocationPoint | null = null
    let bestD = 12 * 12
    for (const p of points) {
      const dx = projection!.x(p.lon) - x
      const dy = projection!.y(p.lat) - y
      const d = dx * dx + dy * dy
      if (d < bestD) {
        best = p
        bestD = d
      }
    }
    return best
  }

  return (
    <div ref={wrapRef} className="map">
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label={`Location track with ${points.length} fixes`}
        onPointerMove={(e) => setHover(nearest(e.clientX, e.clientY, e.currentTarget))}
        onPointerLeave={() => setHover(null)}
        onClick={(e) => {
          const p = nearest(e.clientX, e.clientY, e.currentTarget)
          if (p) onSelectPoint(p.id)
        }}
      >
        <rect width={width} height={HEIGHT} className="map-bg" />
        {lats.map((v) => (
          <g key={`lat${v}`}>
            <line x1={0} x2={width} y1={projection.y(v)} y2={projection.y(v)} className="map-grid" />
            <text x={4} y={projection.y(v) - 3} className="map-grid-label">
              {v.toFixed(3)}°
            </text>
          </g>
        ))}
        {lons.map((v) => (
          <g key={`lon${v}`}>
            <line x1={projection.x(v)} x2={projection.x(v)} y1={0} y2={HEIGHT} className="map-grid" />
            <text x={projection.x(v) + 3} y={HEIGHT - 4} className="map-grid-label">
              {v.toFixed(3)}°
            </text>
          </g>
        ))}

        {sessionCircle ? (
          <circle cx={sessionCircle.x} cy={sessionCircle.y} r={sessionCircle.r} className="map-session" />
        ) : null}
        {segments.map((d, i) => (
          <path key={i} d={d} className="map-track" />
        ))}

        {points.map((p) => {
          const lit = highlightIds?.has(p.id) ?? false
          const selected = p.id === selectedId
          const frac = ((p.ts_ms - t0) / tSpan) * 100
          return (
            <circle
              key={p.id}
              cx={projection.x(p.lon)}
              cy={projection.y(p.lat)}
              r={selected ? 6 : lit ? 5 : 3.2}
              style={{ fill: `color-mix(in srgb, var(--map-a), var(--map-b) ${frac.toFixed(0)}%)` }}
              className={`map-point${lit ? ' lit' : ''}${selected ? ' selected' : ''}${highlightIds && !lit ? ' dim' : ''}`}
            />
          )
        })}

        <g transform={`translate(${width - 22},22)`} className="map-north">
          <path d="M0 -12 L5 4 L0 0 L-5 4 Z" />
          <text y={18} textAnchor="middle">
            N
          </text>
        </g>
        <g transform={`translate(12,${HEIGHT - 26})`}>
          <line x1={0} x2={bar.pixels} y1={0} y2={0} className="map-scale" />
          <line x1={0} x2={0} y1={-4} y2={4} className="map-scale" />
          <line x1={bar.pixels} x2={bar.pixels} y1={-4} y2={4} className="map-scale" />
          <text x={0} y={-8} className="map-scale-label">
            {bar.label}
          </text>
        </g>
      </svg>

      {hover ? (
        <div
          className="chart-tip"
          style={{
            left: Math.min(projection.x(hover.lon) + 12, width - 220),
            top: Math.max(projection.y(hover.lat) - 56, 0),
          }}
          role="tooltip"
        >
          <div className="mono">{formatDateTime(hover.ts_ms, timeZone, true)}</div>
          <div className="mono muted">
            {formatCoord(hover.lat, 'N', 'S')}, {formatCoord(hover.lon, 'E', 'W')}
          </div>
        </div>
      ) : null}

      <div className="map-legend">
        <span className="mono muted">{formatDateTime(t0, timeZone)}</span>
        <span className="map-ramp" aria-hidden="true" />
        <span className="mono muted">{formatDateTime(points[points.length - 1].ts_ms, timeZone)}</span>
      </div>
      <p className="muted small">
        {points.length === total ? `${total} fixes` : `${points.length} of ${total} fixes (evenly sampled)`} · gaps
        over ~15 min are not joined · drawn offline
      </p>
    </div>
  )
}
