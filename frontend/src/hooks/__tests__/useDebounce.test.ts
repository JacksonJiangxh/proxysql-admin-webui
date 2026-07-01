import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebounce } from '../useDebounce'

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should return initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('hello', 500))
    expect(result.current).toBe('hello')
  })

  it('should not update value before delay', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'initial', delay: 500 } }
    )

    rerender({ value: 'updated', delay: 500 })

    // Before timer fires, value should still be the initial one
    expect(result.current).toBe('initial')

    // Advance time by less than delay
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(result.current).toBe('initial')
  })

  it('should update value after delay', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'initial', delay: 500 } }
    )

    rerender({ value: 'updated', delay: 500 })

    act(() => {
      vi.advanceTimersByTime(500)
    })

    expect(result.current).toBe('updated')
  })

  it('should reset timer when value changes within delay', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'a', delay: 300 } }
    )

    // Start typing...
    rerender({ value: 'ab', delay: 300 })
    act(() => {
      vi.advanceTimersByTime(200) // not enough time
    })

    rerender({ value: 'abc', delay: 300 })
    act(() => {
      vi.advanceTimersByTime(200) // still not enough
    })

    // 'ab' timer was cancelled; 'abc' timer hasn't fired yet
    expect(result.current).toBe('a')

    // Now let 'abc' timer fire
    act(() => {
      vi.advanceTimersByTime(100) // 200 + 100 = 300 since last rerender
    })
    expect(result.current).toBe('abc')
  })

  it('should cleanup timer on unmount', () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')

    const { unmount, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'test', delay: 500 } }
    )

    rerender({ value: 'new value', delay: 500 })
    unmount()

    // The cleanup should have been called (clearTimeout for the pending timer)
    expect(clearTimeoutSpy).toHaveBeenCalled()

    clearTimeoutSpy.mockRestore()
  })

  it('should handle delay changes', () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: 'a', delay: 1000 } }
    )

    rerender({ value: 'ab', delay: 200 })

    act(() => {
      vi.advanceTimersByTime(200)
    })

    expect(result.current).toBe('ab')
  })
})
