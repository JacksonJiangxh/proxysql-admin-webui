import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../api/client'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import { Activity, Database, Zap, Server } from 'lucide-react'

export default function DashboardPage() {
  const selectedId = useServerStore((s) => s.selectedId)
  const { t } = useI18n()

  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', selectedId],
    queryFn: () => dashboardApi.getSnapshot(selectedId!),
    enabled: !!selectedId,
    refetchInterval: 10000,
  })

  // useMemo: compute snapshot-derived values only when data changes,
  // not on every render (e.g. sidebar toggle).
  const snapshot = useMemo(() => data?.data || {}, [data])
  const connections = useMemo(() => snapshot.connections?.[0] || {}, [snapshot])
  const qps = useMemo(() => snapshot.qps?.[0]?.questions || 0, [snapshot])
  const traffic = useMemo(() => snapshot.traffic?.[0]?.queries || 0, [snapshot])

  // useMemo: cards array is a derived data structure that triggers
  // re-mapping on every render without memoization.
  const cards = useMemo(() => [
    { label: t('dashboard.activeConnections'), value: connections.used || 0, icon: Activity, color: 'blue' },
    { label: t('dashboard.freeConnections'), value: connections.free || 0, icon: Zap, color: 'green' },
    { label: t('dashboard.totalQueries'), value: Number(traffic).toLocaleString(), icon: Database, color: 'purple' },
    { label: t('dashboard.qps'), value: Number(qps).toLocaleString(), icon: Server, color: 'orange' },
  ], [connections.used, connections.free, traffic, qps, t])

  // useMemo: hostgroups list to avoid re-filtering on every render
  const hostgroups = useMemo(() => snapshot.hostgroups || [], [snapshot])

  if (!selectedId) {
    return (
      <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 text-amber-700 dark:text-amber-400">
        {t('dashboard.noServerSelected')}
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-4 text-red-700 dark:text-red-400">
        {t('dashboard.loadFailed')}
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100 mb-6">{t('dashboard.title')}</h2>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map((card) => (
          <div key={card.label} className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-500 dark:text-slate-400">{card.label}</span>
              <card.icon size={20} className={`text-${card.color}-500`} />
            </div>
            <p className="text-2xl font-bold text-gray-900 dark:text-slate-100">{card.value}</p>
          </div>
        ))}
      </div>

      {/* Connection Pool */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-4">{t('dashboard.connectionPool')}</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-slate-700">
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('dashboard.hostgroup')}</th>
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('dashboard.host')}</th>
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('dashboard.port')}</th>
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('common.status')}</th>
                <th className="text-right py-2 px-3 text-gray-600 dark:text-slate-400">{t('dashboard.used')}</th>
                <th className="text-right py-2 px-3 text-gray-600 dark:text-slate-400">{t('dashboard.free')}</th>
              </tr>
            </thead>
            <tbody>
              {hostgroups.map((hg: any, i: number) => (
                <tr key={i} className="border-b border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                  <td className="py-2 px-3">{hg.hostgroup}</td>
                  <td className="py-2 px-3">{hg.srv_host}</td>
                  <td className="py-2 px-3">{hg.srv_port}</td>
                  <td className="py-2 px-3">
                    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                      hg.status === 'ONLINE' ? 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400' :
                      hg.status === 'SHUNNED' ? 'bg-yellow-100 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400' :
                      'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                    }`}>
                      {hg.status}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right">{hg.ConnUsed}</td>
                  <td className="py-2 px-3 text-right">{hg.ConnFree}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
