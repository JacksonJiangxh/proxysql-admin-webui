import { describe, it, expect, vi, beforeEach } from 'vitest'

// Hoisted mocks must be declared before any imports that use them
const mockPost = vi.hoisted(() => vi.fn())
const mockGet = vi.hoisted(() => vi.fn())

vi.mock('../../api/client', () => ({
  apiClient: {
    post: mockPost,
    get: mockGet,
  },
}))

import { useAuthStore } from '../authStore'

describe('authStore', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    })
    vi.clearAllMocks()
  })

  describe('login', () => {
    it('should set user and token on successful login', async () => {
      const mockUser = { id: 1, username: 'admin', role: 'admin', email: null }
      mockPost.mockResolvedValueOnce({
        data: {
          user: mockUser,
          access_token: 'test-access-token',
        },
      })

      await useAuthStore.getState().login('admin', 'password123')

      const state = useAuthStore.getState()
      expect(state.user).toEqual(mockUser)
      expect(state.token).toBe('test-access-token')
      expect(state.isAuthenticated).toBe(true)
    })

    it('should throw error on failed login', async () => {
      mockPost.mockRejectedValueOnce(new Error('Invalid credentials'))

      await expect(
        useAuthStore.getState().login('admin', 'wrong')
      ).rejects.toThrow('Invalid credentials')

      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(false)
    })
  })

  describe('logout', () => {
    it('should clear auth state on logout', async () => {
      mockPost.mockResolvedValueOnce({ data: { message: 'ok' } })

      useAuthStore.setState({
        user: { id: 1, username: 'admin', role: 'admin', email: null },
        token: 'some-token',
        isAuthenticated: true,
      })

      await useAuthStore.getState().logout()

      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
      expect(state.token).toBeNull()
      expect(state.isAuthenticated).toBe(false)
    })

    it('should clear state even if logout API call fails', async () => {
      mockPost.mockRejectedValueOnce(new Error('Network error'))

      useAuthStore.setState({
        user: { id: 1, username: 'admin', role: 'admin', email: null },
        token: 'some-token',
        isAuthenticated: true,
      })

      await useAuthStore.getState().logout()

      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
      expect(state.isAuthenticated).toBe(false)
    })
  })

  describe('checkAuth', () => {
    it('should set user on successful auth check', async () => {
      const mockUser = { id: 1, username: 'admin', role: 'admin', email: null }
      mockGet.mockResolvedValueOnce({ data: mockUser })

      await useAuthStore.getState().checkAuth()

      const state = useAuthStore.getState()
      expect(state.user).toEqual(mockUser)
      expect(state.isAuthenticated).toBe(true)
    })

    it('should clear auth state on failed check', async () => {
      mockGet.mockRejectedValueOnce(new Error('Unauthorized'))

      useAuthStore.setState({
        user: { id: 1, username: 'admin', role: 'admin', email: null },
        token: 'expired-token',
        isAuthenticated: true,
      })

      await useAuthStore.getState().checkAuth()

      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
      expect(state.token).toBeNull()
      expect(state.isAuthenticated).toBe(false)
    })
  })

  describe('setToken', () => {
    it('should update token and authentication state', () => {
      useAuthStore.getState().setToken('new-token')
      expect(useAuthStore.getState().token).toBe('new-token')
      expect(useAuthStore.getState().isAuthenticated).toBe(true)

      useAuthStore.getState().setToken(null)
      expect(useAuthStore.getState().token).toBeNull()
      expect(useAuthStore.getState().isAuthenticated).toBe(false)
    })
  })
})
