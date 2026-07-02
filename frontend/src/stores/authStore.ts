import { create } from 'zustand'
import { apiClient } from '../api/client'

interface User {
  id: number
  username: string
  role: string
  email: string | null
}

interface AuthState {
  user: User | null
  token: string | null          // access_token (memory only, not localStorage)
  isAuthenticated: boolean
  isInitialized: boolean        // true after checkAuth() has completed (prevents flash of login page)
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
  setToken: (token: string | null) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,   // access_token is memory-only (not in localStorage for XSS safety)
  isAuthenticated: false,
  isInitialized: false,

  login: async (username: string, password: string) => {
    const resp = await apiClient.post('/api/v1/auth/login', { username, password })
    const data = resp.data
    // access_token stored in memory (Zustand state)
    // refresh_token is automatically stored in httpOnly cookie by the browser
    set({
      user: data.user,
      token: data.access_token,
      isAuthenticated: true,
    })
  },

  logout: async () => {
    try {
      await apiClient.post('/api/v1/auth/logout')
    } catch {
      // ignore errors on logout
    }
    set({
      user: null,
      token: null,
      isAuthenticated: false,
    })
  },

  checkAuth: async () => {
    try {
      const resp = await apiClient.get('/api/v1/auth/me')
      set({ user: resp.data, isAuthenticated: true, isInitialized: true })
    } catch {
      set({ user: null, token: null, isAuthenticated: false, isInitialized: true })
    }
  },

  setToken: (token: string | null) => {
    set({ token, isAuthenticated: !!token })
  },
}))
