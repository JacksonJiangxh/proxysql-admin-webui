import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  toggleTheme: () => void
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  if (theme === 'dark') {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: 'light',
      toggleTheme: () => {
        set((state) => {
          const next = state.theme === 'light' ? 'dark' : 'light'
          applyTheme(next)
          return { theme: next }
        })
      },
    }),
    {
      name: 'theme-storage',
      onRehydrateStorage: () => {
        return (state) => {
          if (state) {
            applyTheme(state.theme)
          } else {
            // No saved preference: check system preference
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
            applyTheme(prefersDark ? 'dark' : 'light')
          }
        }
      },
    }
  )
)
