import { Globe, ChevronDown } from 'lucide-react'
import { useI18n, localeNames, Locale } from '../i18n'

/**
 * Compact language switcher dropdown. Persists the choice to localStorage
 * via the i18n provider.
 */
export default function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n()

  return (
    <div className="relative inline-flex items-center">
      <Globe size={16} className="absolute left-2.5 text-gray-400 dark:text-slate-500 pointer-events-none" />
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        className="appearance-none pl-8 pr-7 py-1.5 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-700 dark:text-slate-300 outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
        title={t('language.title')}
      >
        {(Object.keys(localeNames) as Locale[]).map((code) => (
          <option key={code} value={code}>
            {localeNames[code]}
          </option>
        ))}
      </select>
      <ChevronDown size={14} className="absolute right-2 text-gray-400 dark:text-slate-500 pointer-events-none" />
    </div>
  )
}
