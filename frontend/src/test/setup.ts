/**
 * Vitest setup file — runs before each test file.
 *
 * Provides:
 *   • jsdom environment cleanup
 *   • Mock implementations for browser APIs not available in jsdom
 */

import { afterEach, vi, beforeAll } from 'vitest'

// ── Mock localStorage (declared at module scope for afterEach access) ──
let localStorageStore: Record<string, string> = {}

const mockLocalStorage = {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageStore[key] = value
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageStore[key]
  }),
  clear: vi.fn(() => {
    localStorageStore = {}
  }),
  get length() {
    return Object.keys(localStorageStore).length
  },
  key: vi.fn((index: number) => Object.keys(localStorageStore)[index] ?? null),
}

// ── Mock browser APIs (jsdom environment only) ──────────────────

beforeAll(() => {
  if (typeof window === 'undefined') return

  // Mock matchMedia (used by themeStore)
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })

  // Mock localStorage
  Object.defineProperty(window, 'localStorage', {
    value: mockLocalStorage,
    writable: true,
  })
})

// ── Cleanup after each test ────────────────────────────────────
// Reset both the underlying store and clear all mocks

afterEach(() => {
  // Clear underlying localStorage data
  localStorageStore = {}
  // Reset mock call history
  mockLocalStorage.getItem.mockClear()
  mockLocalStorage.setItem.mockClear()
  mockLocalStorage.removeItem.mockClear()
  mockLocalStorage.clear.mockClear()
  mockLocalStorage.key.mockClear()
  // Clear document.cookie
  if (typeof document !== 'undefined') {
    document.cookie = ''
  }
  // Clean up DOM classes added by theme toggle
  if (typeof document !== 'undefined') {
    document.documentElement.classList.remove('dark')
    delete document.documentElement.dataset.theme
  }
  // Clear all other mocks
  vi.clearAllMocks()
})
