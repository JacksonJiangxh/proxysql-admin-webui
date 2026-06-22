import { Sun, Moon } from 'lucide-react'
import { useThemeStore } from '../stores/themeStore'
import { useI18n } from '../i18n'

export default function ThemeToggle() {
  const { theme, toggleTheme } = useThemeStore()
  const { t } = useI18n()

  return (
    <button
      onClick={toggleTheme}
      className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
      title={theme === 'light' ? t('theme.dark') : t('theme.light')}
    >
      {theme === 'light' ? (
        <Moon size={18} className="text-gray-600 dark:text-slate-400" />
      ) : (
        <Sun size={18} className="text-yellow-500" />
      )}
    </button>
  )
}
