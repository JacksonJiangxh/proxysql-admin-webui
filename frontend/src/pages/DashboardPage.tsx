import { useMemo, useCallback } from 'react'
import { useServerStore } from '../stores/serverStore'
import { useAuthStore } from '../stores/authStore'
import { useI18n } from '../i18n'
import { useWebSocket } from '../hooks/useWebSocket'
import { Activity, Database, Zap, Server, Wifi, WifiOff } from 'lucide-react'

/** Dashboard snapshot data shape (matches backend dashboard_service response). */
interface ConnectionInfo {
  used: number
  free: number
  [key: string]: unknown
}

interface HostgroupRow {
  hostgroup: string
  srv_host: string
  srv_port: number
  status: string
  ConnUsed: number
  ConnFree: number
  [key: string]: unknown
}

interface DashboardSnapshot {
  connections: ConnectionInfo[]
  qps: { questions: number }[]
  traffic: { queries: number }[]
  hostgroups: HostgroupRow[]
  [key: string]: unknown
}

/** WebSocket message shape for dashboard feed. */
interface DashboardWsMessage {
  type: string
  server_id: string
  data: DashboardSnapshot
}

/** Build the WebSocket URL for the dashboard feed. */
function buildWsUrl(serverId: string, token: string | null): string | null {
  if (!serverId || !token) return null
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const params = new URLSearchParams({
    token,
    interval: '5',
  })
  return `${protocol}//${host}/ws/dashboard/${serverId}?${params.toString()}`
}

export default function DashboardPage() {
  const selectedId = useServerStore((s) => s.selectedId)
  const token = useAuthStore((s) => s.token)
  const { t } = useI18n()

  const wsUrl = useMemo(() => buildWsUrl(selectedId!, token), [selectedId, token])

  const { data, isConnected, error, reconnect } = useWebSocket<DashboardWsMessage>(
    wsUrl,
    !!selectedId,
  )

  // Extract snapshot from the latest WebSocket message
  const snapshot: DashboardSnapshot = data?.data || {
    connections: [],
    qps: [],
    traffic: [],
    hostgroups: [],
  }
  const connections = snapshot.connections?.[0] || {}
  const qps = snapshot.qps?.[0]?.questions || 0
  const traffic = snapshot.traffic?.[0]?.queries || 0

  const cards = useMemo(() => [
    { label: t('dashboard.activeConnections'), value: connections.used || 0, icon: Activity, color: 'blue' },
    { label: t('dashboard.freeConnections'), value: connections.free || 0, icon: Zap, color: 'green' },
    { label: t('dashboard.totalQueries'), value: Number(traffic).toLocaleString(), icon: Database, color: 'purple' },
    { label: t('dashboard.qps'), value: Number(qps).toLocaleString(), icon: Server, color: 'orange' },
  ], [connections.used, connections.free, traffic, qps, t])

  const hostgroups: HostgroupRow[] = snapshot.hostgroups || []

  if (!selectedId) {
    return (
      <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 text-amber-700 dark:text-amber-400">
        {t('dashboard.noServerSelected')}
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('dashboard.title')}</h2>
        {/* Connection status indicator */}
        <div className="flex items-center gap-2">
          {isConnected ? (
            <span className="inline-flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
              <Wifi size={16} /> {t('dashboard.connected') || 'Connected'}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-slate-400">
              <WifiOff size={16} /> {t('dashboard.reconnecting') || 'Reconnecting...'}
            </span>
          )}
          {error && (
            <button
              onClick={reconnect}
              className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              {t('common.retry') || 'Retry'}
            </button>
          )}
        </div>
      </div>

      {/* Metric Cards */}
      <div data-tour="dashboard-cards" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
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
              {hostgroups.map((hg: HostgroupRow, i: number) => (
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
