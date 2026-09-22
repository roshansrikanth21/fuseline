import { render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { useElementWidth } from './useElementSize'

// A component that renders something else first and only later the element being measured:
// exactly the shape that broke the timeline chart when a plain ref was used.
function Probe({ showBox }: { showBox: boolean }) {
  const [ref, width] = useElementWidth<HTMLDivElement>(900)
  return showBox ? (
    <div ref={ref} data-testid="box">
      {width}
    </div>
  ) : (
    <p>empty</p>
  )
}

describe('useElementWidth', () => {
  it('measures an element that mounts after the first render', () => {
    const observers: { cb: () => void; target: Element | null }[] = []
    vi.stubGlobal(
      'ResizeObserver',
      class {
        entry: { cb: () => void; target: Element | null } = { cb: () => {}, target: null }
        constructor(cb: () => void) {
          this.entry.cb = cb
          observers.push(this.entry)
        }
        observe(target: Element) {
          this.entry.target = target
        }
        disconnect() {}
      },
    )
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ width: 1186 } as DOMRect)

    const { rerender } = render(<Probe showBox={false} />)
    expect(screen.queryByTestId('box')).toBeNull()

    rerender(<Probe showBox />)
    expect(screen.getByTestId('box')).toHaveTextContent('1186')
    expect(observers.some((o) => o.target === screen.getByTestId('box'))).toBe(true)
    vi.unstubAllGlobals()
  })

  it('keeps the fallback width when nothing can be measured', () => {
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ width: 0 } as DOMRect)
    function Wrapper() {
      const [on] = useState(true)
      return <Probe showBox={on} />
    }
    render(<Wrapper />)
    expect(screen.getByTestId('box')).toHaveTextContent('900')
  })
})
