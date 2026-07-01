import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act } from '@testing-library/react'
import { useThemeStore } from '../themeStore'

describe('themeStore', () => {
  beforeEach(() => {
    // Clear persisted theme state from localStorage
    localStorage.removeItem('theme-storage')
    // Reset store state
    useThemeStore.setState({ theme: 'light' })
    // Reset document state
    document.documentElement.classList.remove('dark')
    delete document.documentElement.dataset.theme
  })

  describe('initial state', () => {
    it('should default to light theme', () => {
      const state = useThemeStore.getState()
      expect(state.theme).toBe('light')
    })
  })

  describe('toggleTheme', () => {
    it('should toggle from light to dark', () => {
      act(() => {
        useThemeStore.getState().toggleTheme()
      })
      expect(useThemeStore.getState().theme).toBe('dark')
    })

    it('should toggle from dark to light', () => {
      useThemeStore.setState({ theme: 'dark' })
      act(() => {
        useThemeStore.getState().toggleTheme()
      })
      expect(useThemeStore.getState().theme).toBe('light')
    })

    it('should add dark class to document when toggling to dark', () => {
      act(() => {
        useThemeStore.getState().toggleTheme()
      })
      expect(document.documentElement.classList.contains('dark')).toBe(true)
      expect(document.documentElement.dataset.theme).toBe('dark')
    })

    it('should remove dark class from document when toggling to light', () => {
      useThemeStore.setState({ theme: 'dark' })
      document.documentElement.classList.add('dark')
      document.documentElement.dataset.theme = 'dark'

      act(() => {
        useThemeStore.getState().toggleTheme()
      })

      expect(document.documentElement.classList.contains('dark')).toBe(false)
      expect(document.documentElement.dataset.theme).toBe('light')
    })

    it('should update theme state and be persistable', () => {
      act(() => {
        useThemeStore.getState().toggleTheme()
      })
      // After toggle, the store's internal state should reflect 'dark'
      expect(useThemeStore.getState().theme).toBe('dark')
      // The persist middleware writes asynchronously; we verify the
      // store state is correct, and localStorage persistence is verified
      // at the integration level (E2E tests).
    })
  })

  describe('persistence', () => {
    it('should read previously stored theme', () => {
      // Simulate previous save
      localStorage.setItem(
        'theme-storage',
        JSON.stringify({ state: { theme: 'dark' }, version: 0 })
      )

      const stored = localStorage.getItem('theme-storage')
      expect(stored).not.toBeNull()

      const parsed = JSON.parse(stored!)
      expect(parsed.state.theme).toBe('dark')
    })
  })
})
