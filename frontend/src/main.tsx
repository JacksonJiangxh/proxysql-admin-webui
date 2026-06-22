import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { I18nProvider } from './i18n'
import { useThemeStore } from './stores/themeStore'
import App from './App'
import './index.css'

// Initialize theme store to trigger persistence hydration
useThemeStore.getState()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30000,
      // gcTime: keep unused data in cache for 5 minutes before garbage collection.
      // This prevents re-fetching when users navigate back to a previously visited page.
      gcTime: 5 * 60 * 1000,
      // refetchOnWindowFocus: false - avoids unnecessary refetches when users switch
      // browser tabs/windows and return. ProxySQL admin data doesn't change frequently
      // enough to warrant refetching on every focus event. Pages that need live data
      // (Dashboard, ConfigDiff) already have refetchInterval set.
      refetchOnWindowFocus: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </I18nProvider>
  </React.StrictMode>,
)
