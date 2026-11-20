import { act, renderHook } from '@testing-library/react'
import { useDebounced } from './queries'

describe('useDebounced', () => {
  beforeEach(() => vi.useFakeTimers()); afterEach(() => vi.useRealTimers())
  it('delivers the latest value after the delay', () => {
    const { result, rerender } = renderHook(({ v }) => useDebounced(v, 300), { initialProps: { v: 1 } })
    rerender({ v: 2 }); expect(result.current).toBe(1); act(() => { vi.advanceTimersByTime(300) }); expect(result.current).toBe(2)
  })
  it('does not starve when callers pass a fresh object every render (regression: calculator never recalculated)', () => {
    const { result, rerender } = renderHook(({ n }) => useDebounced({ width: n }, 300), { initialProps: { n: 800 } })
    rerender({ n: 1200 })
    for (let i = 0; i < 5; i++) { act(() => { vi.advanceTimersByTime(100) }); rerender({ n: 1200 }) } // re-renders with a new object but identical content
    act(() => { vi.advanceTimersByTime(300) }); expect(result.current).toEqual({ width: 1200 })
  })
})
