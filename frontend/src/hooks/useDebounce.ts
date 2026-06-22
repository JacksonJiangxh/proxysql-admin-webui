import { useState, useEffect } from 'react'

/**
 * useDebounce - Delays updating a value until after a specified delay.
 * Used to reduce expensive operations (API calls, filtering) triggered by
 * rapid user input (e.g. search fields, typeahead).
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}
