import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { I18nProvider } from './i18n'
import { TourProvider } from './components/TourGuide'
import { ToastProvider } from './components/ToastProvider'
import { useThemeStore } from './stores/themeStore'
import { useAuthStore } from './stores/authStore'
import App from './App'
import './index.css'

// Initialize theme store to trigger persistence hydration
useThemeStore.getState()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    },
  },
})

// Expose auth store to window for the axios interceptor (client.ts).
// This avoids a circular import between authStore.ts and client.ts.
// Must be set BEFORE rendering so the interceptor can read token during
// the initial checkAuth() call below.
window.__AUTH_STORE__ = {
  get token() { return useAuthStore.getState().token },
  setToken(token: string | null) { useAuthStore.getState().setToken(token) },
}

// On app startup, try to restore the user session via the httpOnly
// refresh_token cookie. If the cookie is still valid the backend will
// issue a new access_token and return the user profile, so the user
// does NOT have to re-login after every page refresh.
useAuthStore.getState().checkAuth()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ToastProvider>
            <TourProvider>
              <App />
            </TourProvider>
          </ToastProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </I18nProvider>
  </React.StrictMode>,
)
