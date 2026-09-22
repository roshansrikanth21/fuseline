import { fireEvent, render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { makeEvent } from '../test/fixtures'
import { EventTable } from './EventTable'

type Overrides = Partial<Pick<ComponentProps<typeof EventTable>, 'events' | 'total' | 'hasMore'>>

function setup(overrides: Overrides = {}) {
  const events = [makeEvent({ title: 'First' }), makeEvent({ title: 'Second' }), makeEvent({ title: 'Third' })]
  const onSelect = vi.fn()
  const onLoadMore = vi.fn()
  render(
    <EventTable
      events={events}
      total={3}
      hasMore={false}
      loading={false}
      selectedId={null}
      highlightIds={null}
      timeZone="UTC"
      onSelect={onSelect}
      onLoadMore={onLoadMore}
      {...overrides}
    />,
  )
  return { events, onSelect, onLoadMore }
}

describe('EventTable', () => {
  it('selects a row on click and with Enter or Space', () => {
    const { events, onSelect } = setup()
    fireEvent.click(screen.getByText('First'))
    fireEvent.keyDown(screen.getByText('Second').closest('tr')!, { key: 'Enter' })
    fireEvent.keyDown(screen.getByText('Third').closest('tr')!, { key: ' ' })
    expect(onSelect.mock.calls.map((c) => c[0])).toEqual(events)
  })

  it('moves focus between rows with the arrow keys', () => {
    setup()
    const rows = screen.getAllByRole('row').slice(1)
    rows[0].focus()
    fireEvent.keyDown(rows[0], { key: 'ArrowDown' })
    expect(rows[1]).toHaveFocus()
    fireEvent.keyDown(rows[1], { key: 'ArrowUp' })
    expect(rows[0]).toHaveFocus()
  })

  it('reports how many of the events in view are loaded and pages on demand', () => {
    const { onLoadMore } = setup({ total: 2500, hasMore: true })
    expect(screen.getByText('3 of 2,500 in view')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }))
    expect(onLoadMore).toHaveBeenCalledOnce()
  })

  it('hides "Load more" when everything is loaded', () => {
    setup()
    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull()
  })

  it('marks rows whose time was assumed', () => {
    setup({ events: [makeEvent({ title: 'Local', ts_basis: 'assumed', tz_assumed: 'Asia/Kolkata' })], total: 1 })
    expect(screen.getByTitle('Assumed local time (Asia/Kolkata)')).toBeInTheDocument()
  })

  it('explains an empty result, and shows loading state instead while fetching', () => {
    const { rerender } = render(
      <EventTable
        events={[]}
        total={0}
        hasMore={false}
        loading={false}
        selectedId={null}
        highlightIds={null}
        timeZone="UTC"
        onSelect={() => undefined}
        onLoadMore={() => undefined}
      />,
    )
    expect(screen.getByText(/No events match/)).toBeInTheDocument()
    rerender(
      <EventTable
        events={[]}
        total={0}
        hasMore={false}
        loading
        selectedId={null}
        highlightIds={null}
        timeZone="UTC"
        onSelect={() => undefined}
        onLoadMore={() => undefined}
      />,
    )
    expect(screen.getByText('Loading events…')).toBeInTheDocument()
  })
})
