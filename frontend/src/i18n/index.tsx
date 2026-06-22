import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { zhCN } from './locales/zh-CN'
import { enUS } from './locales/en-US'
import { tableGuidesZhCN } from './tableGuides_zh'
import { tableGuidesEnUS } from './tableGuides_en'

export type Locale = 'zh-CN' | 'en-US'

const STORAGE_KEY = 'proxysql-admin-locale'

/**
 * Translation dictionaries keyed by locale code.
 *
 * To add a new language:
 *   1. Create `frontend/src/i18n/locales/<code>.ts` exporting a dictionary
 *      with the same shape as `zh-CN.ts`.
 *   2. Import it here and add an entry to `locales` below.
 *   3. Add a human-readable label to `localeNames`.
 */
const locales: Record<Locale, Record<string, string>> = {
  'zh-CN': { ...zhCN, ...tableGuidesZhCN },
  'en-US': { ...enUS, ...tableGuidesEnUS },
}

/** Human-readable names shown in the language switcher. */
export const localeNames: Record<Locale, string> = {
  'zh-CN': '简体中文',
  'en-US': 'English',
}

/** Default locale — Chinese, per project requirement. */
const DEFAULT_LOCALE: Locale = 'zh-CN'

function detectInitialLocale(): Locale {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored && stored in locales) {
    return stored as Locale
  }
  return DEFAULT_LOCALE
}

interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  /** Translate a key. Falls back to the key itself when missing. */
  t: (key: string, params?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(detectInitialLocale)

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
    localStorage.setItem(STORAGE_KEY, next)
    document.documentElement.lang = next
  }, [])

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => {
      const dict = locales[locale] || locales[DEFAULT_LOCALE]
      let text = dict[key] ?? locales[DEFAULT_LOCALE][key] ?? key
      if (params) {
        for (const [name, value] of Object.entries(params)) {
          text = text.replace(new RegExp(`\\{${name}\\}`, 'g'), String(value))
        }
      }
      return text
    },
    [locale],
  )

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  )
}

/** Hook to access the i18n context. Must be used inside <I18nProvider>. */
export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    throw new Error('useI18n must be used within an I18nProvider')
  }
  return ctx
}
