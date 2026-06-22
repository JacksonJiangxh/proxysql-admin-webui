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
  token: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),

  login: async (username: string, password: string) => {
    const resp = await apiClient.post('/api/v1/auth/login', { username, password })
    const data = resp.data
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    set({
      user: data.user,
      token: data.access_token,
      refreshToken: data.refresh_token,
      isAuthenticated: true,
    })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
    })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) return
    try {
      const resp = await apiClient.get('/api/v1/auth/me')
      set({ user: resp.data, isAuthenticated: true })
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      set({ user: null, token: null, refreshToken: null, isAuthenticated: false })
    }
  },
}))
