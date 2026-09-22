import { fireEvent, render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Overview } from '../api/client'
import { makeEvent, makeSession } from '../test/fixtures'
import { TimelineChart } from './TimelineChart'

const WIDTH = 1000
const LABEL_W = 92
const PLOT_W = WIDTH - LABEL_W - 14
const view = { start: 0, end: 1_000_000 }

/** x coordinate (in the SVG) of time `t` for the fixed view above. */
const xAt = (t: number) => LABEL_W + (t / (view.end - view.start)) * PLOT_W
const LANE_Y = 30 + 20 // inside the first lane

type Props = ComponentProps<typeof TimelineChart>
type Overrides = Partial<Omit<Props, 'onViewChange' | 'onSelectEvent' | 'onSelectSession'>>

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ width: WIDTH, left: 0, top: 0 } as DOMRect)
  vi.spyOn(SVGElement.prototype, 'getBoundingClientRect').mockReturnValue({ width: WIDTH, left: 0, top: 0 } as DOMRect)
})

afterEach(() => {
  vi.restoreAllMocks()
})

function renderChart(overrides: Overrides = {}) {
  const events = [
    makeEvent({ title: 'early', ts_ms: 100_000 }),
    makeEvent({ title: 'middle', ts_ms: 500_000 }),
    makeEvent({ title: 'late', ts_ms: 900_000 }),
  ]
  const onViewChange = vi.fn()
  const onSelectEvent = vi.fn()
  const onSelectSession = vi.fn()
  const utils = render(
    <TimelineChart
      view={view}
      bounds={view}
      lanes={['browsing']}
      density={null}
      marks={events}
      sessions={[]}
      activeSessionId={null}
      highlightIds={null}
      selectedId={null}
      timeZone="UTC"
      onViewChange={onViewChange}
      onSelectEvent={onSelectEvent}
      onSelectSession={onSelectSession}
      {...overrides}
    />,
  )
  const svg = utils.container.querySelector('svg.chart-svg') as SVGSVGElement
  return { ...utils, svg, events, onViewChange, onSelectEvent, onSelectSession }
}

function click(svg: SVGSVGElement, x: number, y = LANE_Y) {
  fireEvent.pointerDown(svg, { clientX: x, clientY: y, button: 0, pointerId: 1 })
  fireEvent.pointerUp(svg, { clientX: x, clientY: y, button: 0, pointerId: 1 })
}

describe('TimelineChart', () => {
  it('selects the mark under the pointer', () => {
    const { svg, events, onSelectEvent } = renderChart()
    click(svg, xAt(500_000))
    expect(onSelectEvent).toHaveBeenCalledWith(events[1])
  })

  it('picks the nearest mark within a few pixels, but not one further away', () => {
    const { svg, events, onSelectEvent } = renderChart()
    click(svg, xAt(900_000) + 5)
    expect(onSelectEvent).toHaveBeenCalledWith(events[2])
    onSelectEvent.mockClear()
    click(svg, xAt(700_000)) // nothing near here
    expect(onSelectEvent).not.toHaveBeenCalled()
  })

  it('does not treat a drag as a click, and pans instead', () => {
    const { svg, onSelectEvent, onViewChange } = renderChart({ view: { start: 200_000, end: 600_000 } })
    fireEvent.pointerDown(svg, { clientX: 400, clientY: LANE_Y, button: 0, pointerId: 1 })
    fireEvent.pointerMove(svg, { clientX: 300, clientY: LANE_Y, pointerId: 1 })
    fireEvent.pointerUp(svg, { clientX: 300, clientY: LANE_Y, button: 0, pointerId: 1 })
    expect(onSelectEvent).not.toHaveBeenCalled()
    expect(onViewChange).toHaveBeenCalled()
    const panned = onViewChange.mock.calls.at(-1)?.[0]
    expect(panned.start).toBeGreaterThan(200_000) // dragged left => later times
    expect(panned.end - panned.start).toBeCloseTo(400_000)
  })

  it('selects a session when clicking a band with no mark under the pointer', () => {
    const session = makeSession({ start_utc: new Date(600_000).toISOString(), end_utc: new Date(800_000).toISOString() })
    const { svg, onSelectSession } = renderChart({ sessions: [session] })
    click(svg, xAt(700_000))
    expect(onSelectSession).toHaveBeenCalledWith(session)
  })

  it('zooms and pans from the keyboard, and resets', () => {
    const { onViewChange } = renderChart({ view: { start: 200_000, end: 600_000 } })
    const chart = screen.getByRole('group', { name: 'Timeline chart' })
    fireEvent.keyDown(chart, { key: '+' })
    const zoomedIn = onViewChange.mock.calls.at(-1)?.[0]
    expect(zoomedIn.end - zoomedIn.start).toBeLessThan(400_000)
    fireEvent.keyDown(chart, { key: 'ArrowRight' })
    expect(onViewChange.mock.calls.at(-1)?.[0].start).toBeGreaterThan(200_000)
    fireEvent.keyDown(chart, { key: '0' })
    expect(onViewChange.mock.calls.at(-1)?.[0]).toEqual(view)
  })

  it('shows a tooltip with the event title when hovering a mark', () => {
    const { svg } = renderChart()
    fireEvent.pointerMove(svg, { clientX: xAt(100_000), clientY: LANE_Y, pointerId: 1 })
    expect(screen.getByRole('tooltip')).toHaveTextContent('early')
  })

  it('draws density bars instead of marks when there are too many events', () => {
    const density: Overview = {
      origin_ms: 0,
      bucket_ms: 100_000,
      bucket_count: 10,
      total: 5000,
      series: {
        browsing: [
          [1, 40],
          [5, 400],
        ],
      },
    }
    const { container } = renderChart({ marks: null, density })
    expect(screen.getByText('density')).toBeInTheDocument()
    const bars = container.querySelectorAll('rect[opacity="0.85"]')
    expect(bars).toHaveLength(2)
    expect(Number(bars[1].getAttribute('height'))).toBeGreaterThan(Number(bars[0].getAttribute('height')))
  })

  it('counts only the events inside the window', () => {
    renderChart({ view: { start: 400_000, end: 600_000 } })
    expect(screen.getByText('1 in view')).toBeInTheDocument()
  })

  it('renders an empty state when no lane is enabled', () => {
    renderChart({ lanes: [] })
    expect(screen.getByText(/No events in view/)).toBeInTheDocument()
  })
})
