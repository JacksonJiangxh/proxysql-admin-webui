import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi } from '../api/client'
import { useI18n } from '../i18n'
import { Settings, Trash2, Info } from 'lucide-react'

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const { t } = useI18n()
  const [actionFilter, setActionFilter] = useState('')

  const { data: infoData } = useQuery({
    queryKey: ['settings', 'info'],
    queryFn: () => settingsApi.getSystemInfo(),
  })

  const { data: logsData, isLoading } = useQuery({
    queryKey: ['settings', 'audit-logs', actionFilter],
    queryFn: () => settingsApi.getAuditLogs(actionFilter ? { action: actionFilter } : {}),
  })

  const clearLogsMutation = useMutation({
    mutationFn: () => settingsApi.clearAuditLogs(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'audit-logs'] })
      queryClient.invalidateQueries({ queryKey: ['settings', 'info'] })
    },
  })

  const info = infoData?.data || {}
  const logs = logsData?.data?.logs || []

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Settings size={28} className="text-blue-600 dark:text-blue-400" />
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('settings.title')}</h2>
      </div>

      <p className="text-gray-500 dark:text-slate-400 mb-6">{t('settings.subtitle')}</p>

      {/* System Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
          <div className="flex items-center gap-2 text-gray-500 dark:text-slate-400 text-sm mb-1">
            <Info size={14} />
            {t('settings.version')}
          </div>
          <p className="text-2xl font-bold text-gray-900 dark:text-slate-100">{info.version || '—'}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
          <div className="text-gray-500 dark:text-slate-400 text-sm mb-1">{t('settings.userCount')}</div>
          <p className="text-2xl font-bold text-gray-900 dark:text-slate-100">{info.user_count ?? '—'}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
          <div className="text-gray-500 dark:text-slate-400 text-sm mb-1">{t('settings.serverCount')}</div>
          <p className="text-2xl font-bold text-gray-900 dark:text-slate-100">{info.server_count ?? '—'}</p>
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
          <div className="text-gray-500 dark:text-slate-400 text-sm mb-1">{t('settings.auditLogCount')}</div>
          <p className="text-2xl font-bold text-gray-900 dark:text-slate-100">{info.audit_log_count ?? '—'}</p>
        </div>
      </div>

      {/* Audit Logs */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between">
          <span className="font-semibold text-gray-900 dark:text-slate-100">{t('settings.auditLogs')}</span>
          <div className="flex items-center gap-2">
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="text-sm border border-gray-300 dark:border-slate-600 rounded-lg px-2 py-1 outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
            >
              <option value="">{t('common.all')}</option>
              <option value="login">login</option>
              <option value="logout">logout</option>
              <option value="query">query</option>
              <option value="insert">insert</option>
              <option value="update">update</option>
              <option value="delete">delete</option>
              <option value="sync_apply">sync_apply</option>
              <option value="sync_save">sync_save</option>
              <option value="wizard_execute">wizard_execute</option>
            </select>
            <button
              onClick={() => clearLogsMutation.mutate()}
              disabled={clearLogsMutation.isPending}
              className="flex items-center gap-1 text-sm text-red-600 dark:text-red-400 hover:text-red-700 px-2 py-1 border border-red-200 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
            >
              <Trash2 size={14} />
              {t('settings.clearLogs')}
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700">
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('settings.time')}</th>
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('settings.user')}</th>
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('settings.action')}</th>
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('settings.resource')}</th>
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('settings.ipAddress')}</th>
                <th className="text-left py-2 px-3 text-gray-600 dark:text-slate-400">{t('settings.details')}</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log: any, i: number) => (
                <tr key={i} className="border-b border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                  <td className="py-2 px-3 text-gray-600 dark:text-slate-400 whitespace-nowrap">{log.created_at}</td>
                  <td className="py-2 px-3 font-medium text-gray-800 dark:text-slate-300">{log.username || '—'}</td>
                  <td className="py-2 px-3">
                    <span className="inline-block bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 text-xs px-2 py-0.5 rounded">
                      {log.action}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-gray-600 dark:text-slate-400">{log.resource || '—'}</td>
                  <td className="py-2 px-3 text-gray-600 dark:text-slate-400">{log.ip_address || '—'}</td>
                  <td className="py-2 px-3 text-gray-400 dark:text-slate-500 text-xs max-w-xs truncate">{log.details || '—'}</td>
                </tr>
              ))}
              {logs.length === 0 && !isLoading && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-gray-400 dark:text-slate-500">
                    {t('settings.noLogs')}
                  </td>
                </tr>
              )}
              {isLoading && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-gray-400 dark:text-slate-500">
                    {t('common.loading')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
