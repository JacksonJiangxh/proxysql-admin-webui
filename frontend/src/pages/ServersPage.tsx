import { useState, Fragment } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { serversApi } from '../api/client'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import { Server, Plus, Trash2, CheckCircle, Loader, Pencil } from 'lucide-react'

export default function ServersPage() {
  const queryClient = useQueryClient()
  const { fetchServers, selectServer } = useServerStore()
  const { t } = useI18n()
  const [showCreate, setShowCreate] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [newServer, setNewServer] = useState({
    name: '', host: '127.0.0.1', port: 6032, admin_user: '', admin_password: '',
  })
  const [editServer, setEditServer] = useState({
    name: '', host: '', port: 6032, admin_user: '', admin_password: '',
  })
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['servers'],
    queryFn: () => serversApi.list(),
  })

  const refreshServers = () => {
    queryClient.invalidateQueries({ queryKey: ['servers'] })
    fetchServers()
  }

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => serversApi.create(data),
    onSuccess: () => {
      refreshServers()
      setShowCreate(false)
      setNewServer({ name: '', host: '127.0.0.1', port: 6032, admin_user: '', admin_password: '' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: { id: string; payload: Record<string, unknown> }) =>
      serversApi.update(data.id, data.payload),
    onSuccess: () => {
      refreshServers()
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => serversApi.delete(id),
    onSuccess: () => refreshServers(),
  })

  const startEdit = (server: any) => {
    setEditingId(server.id)
    setEditServer({
      name: server.name,
      host: server.host,
      port: server.port,
      admin_user: server.admin_user,
      admin_password: '',
    })
  }

  const testConnection = async (id: string) => {
    setTestingId(id)
    setTestResult(null)
    try {
      const resp = await serversApi.test(id)
      // 后端 detail 仅供开发者参考，用户看到翻译后的消息
      console.info('[Test]', resp.data.message)
      setTestResult({ success: true, message: t('servers.testSuccess') })
    } catch (err: any) {
      console.error('[Test]', err.response?.data?.detail || err.response?.data?.message || err.message)
      setTestResult({ success: false, message: t('servers.testFailed') })
    } finally {
      setTestingId(null)
    }
  }

  const servers = data?.data || []

  const inputCls = 'px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Server size={28} className="text-blue-600 dark:text-blue-400" />
          <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('servers.title')}</h2>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          <Plus size={16} />
          {t('servers.add')}
        </button>
      </div>

      {/* Test Connection Result */}
      {testResult && (
        <div className={`mb-6 p-3 rounded-lg text-sm ${
          testResult.success
            ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 text-green-700 dark:text-green-400'
            : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 text-red-700 dark:text-red-400'
        }`}>
          {testResult.message}
        </div>
      )}

      {/* Create Server Form */}
      {showCreate && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4 mb-6">
          <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-3">{t('servers.add')}</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <input
              type="text" placeholder={t('servers.serverName')} value={newServer.name}
              onChange={(e) => setNewServer({ ...newServer, name: e.target.value })}
              className={inputCls}
            />
            <input
              type="text" placeholder={t('servers.host')} value={newServer.host}
              onChange={(e) => setNewServer({ ...newServer, host: e.target.value })}
              className={inputCls}
            />
            <input
              type="number" placeholder={t('servers.port')} value={newServer.port}
              onChange={(e) => setNewServer({ ...newServer, port: parseInt(e.target.value) })}
              className={inputCls}
            />
            <input
              type="text" placeholder={t('servers.adminUser')} value={newServer.admin_user}
              onChange={(e) => setNewServer({ ...newServer, admin_user: e.target.value })}
              className={inputCls}
            />
            <input
              type="password" placeholder={t('servers.adminPassword')} value={newServer.admin_password}
              onChange={(e) => setNewServer({ ...newServer, admin_password: e.target.value })}
              className={inputCls}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => createMutation.mutate(newServer)}
              disabled={!newServer.name || !newServer.admin_user || !newServer.admin_password}
              className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            >
              {t('common.add')}
            </button>
            <button onClick={() => setShowCreate(false)} className="text-gray-600 dark:text-slate-400 px-4 py-1.5 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-slate-700">{t('common.cancel')}</button>
          </div>
        </div>
      )}

      {/* Servers Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700">
                <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('servers.name')}</th>
                <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('servers.address')}</th>
                <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('servers.user')}</th>
                <th className="text-center py-2 px-4 text-gray-600 dark:text-slate-400">{t('servers.default')}</th>
                <th className="text-right py-2 px-4 text-gray-600 dark:text-slate-400">{t('servers.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {servers.map((server: any) => (
                <Fragment key={server.id}>
                  <tr className="border-b border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                    <td className="py-2 px-4 font-medium text-gray-900 dark:text-slate-100">{server.name}</td>
                    <td className="py-2 px-4 text-gray-500 dark:text-slate-400">{server.host}:{server.port}</td>
                    <td className="py-2 px-4 text-gray-500 dark:text-slate-400">{server.admin_user}</td>
                    <td className="py-2 px-4 text-center">
                      {server.is_default && <CheckCircle size={16} className="inline text-green-500" />}
                    </td>
                    <td className="py-2 px-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => selectServer(server.id)}
                          className="text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-300 text-xs px-2 py-1"
                          title={t('servers.selectHint')}
                        >
                          {t('common.use')}
                        </button>
                        <button
                          onClick={() => testConnection(server.id)}
                          disabled={testingId === server.id}
                          className="text-blue-500 hover:text-blue-700 text-xs px-2 py-1"
                        >
                          {testingId === server.id ? <Loader size={14} className="animate-spin" /> : t('common.test')}
                        </button>
                        <button
                          onClick={() => startEdit(server)}
                          className="text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-300 p-1"
                          title={t('servers.editHint')}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => deleteMutation.mutate(server.id)}
                          className="text-red-500 hover:text-red-700 p-1"
                          title={t('servers.deleteHint')}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                  {editingId === server.id && (
                    <tr className="bg-gray-50 dark:bg-slate-700">
                      <td colSpan={5} className="p-4">
                        <h4 className="font-semibold text-gray-900 dark:text-slate-100 mb-3">{t('servers.edit', { name: server.name })}</h4>
                        <div className="grid grid-cols-2 gap-3 mb-3">
                          <input
                            type="text" placeholder={t('servers.serverName')} value={editServer.name}
                            onChange={(e) => setEditServer({ ...editServer, name: e.target.value })}
                            className={inputCls}
                          />
                          <input
                            type="text" placeholder={t('servers.host')} value={editServer.host}
                            onChange={(e) => setEditServer({ ...editServer, host: e.target.value })}
                            className={inputCls}
                          />
                          <input
                            type="number" placeholder={t('servers.port')} value={editServer.port}
                            onChange={(e) => setEditServer({ ...editServer, port: parseInt(e.target.value) || 0 })}
                            className={inputCls}
                          />
                          <input
                            type="text" placeholder={t('servers.adminUser')} value={editServer.admin_user}
                            onChange={(e) => setEditServer({ ...editServer, admin_user: e.target.value })}
                            className={inputCls}
                          />
                          <input
                            type="password" placeholder={t('servers.newPassword')} value={editServer.admin_password}
                            onChange={(e) => setEditServer({ ...editServer, admin_password: e.target.value })}
                            className={`${inputCls} col-span-2`}
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              const payload: Record<string, unknown> = {
                                name: editServer.name,
                                host: editServer.host,
                                port: editServer.port,
                                admin_user: editServer.admin_user,
                              }
                              if (editServer.admin_password) {
                                payload.admin_password = editServer.admin_password
                              }
                              updateMutation.mutate({ id: server.id, payload })
                            }}
                            disabled={!editServer.name || !editServer.host || !editServer.admin_user || updateMutation.isPending}
                            className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
                          >
                            {t('common.save')}
                          </button>
                          <button onClick={() => setEditingId(null)} className="text-gray-600 dark:text-slate-400 px-4 py-1.5 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-slate-700">
                            {t('common.cancel')}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {servers.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-gray-400 dark:text-slate-500">
                    {t('servers.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
