import { useEffect } from 'react'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import { Server, ChevronDown, Loader } from 'lucide-react'

/**
 * Dropdown that lets the user pick which ProxySQL instance subsequent
 * pages operate on. Replaces the hardcoded "default" server_id that used
 * to be spread across every page.
 */
export default function ServerSelector() {
  const { servers, selectedId, loading, loaded, fetchServers, selectServer } = useServerStore()
  const { t } = useI18n()

  useEffect(() => {
    if (!loaded) {
      fetchServers()
    }
  }, [loaded, fetchServers])

  if (loading && servers.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-slate-400">
        <Loader size={14} className="animate-spin" />
        {t('layout.loadingServers')}
      </div>
    )
  }

  if (servers.length === 0) {
    return (
      <div className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 px-3 py-1.5 rounded-lg">
        {t('layout.noServers')}
      </div>
    )
  }

  const selected = servers.find((s) => s.id === selectedId) || servers[0]

  return (
    <div className="relative">
      <Server size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500 pointer-events-none" />
      <select
        value={selected?.id || ''}
        onChange={(e) => selectServer(e.target.value || null)}
        className="appearance-none pl-8 pr-8 py-1.5 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-700 dark:text-slate-300 outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer min-w-[200px]"
        title={t('layout.selectServer')}
      >
        {servers.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} ({s.host}:{s.port}){s.is_default ? ' \u2605' : ''}
          </option>
        ))}
      </select>
      <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500 pointer-events-none" />
    </div>
  )
}
