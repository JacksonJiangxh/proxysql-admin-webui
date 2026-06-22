import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clustersApi, serversApi } from '../api/client'
import { useI18n } from '../i18n'
import { Network, Plus, Trash2, Pencil, ChevronRight, Loader } from 'lucide-react'

export default function ClustersPage() {
  const queryClient = useQueryClient()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [showCreate, setShowCreate] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [newCluster, setNewCluster] = useState({
    name: '', description: '', master_server_id: '',
  })
  const [editCluster, setEditCluster] = useState({
    name: '', description: '', master_server_id: '',
  })

  const { data: clustersData, isLoading } = useQuery({
    queryKey: ['clusters'],
    queryFn: () => clustersApi.list(),
  })

  const { data: serversData } = useQuery({
    queryKey: ['servers'],
    queryFn: () => serversApi.list(),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['clusters'] })
  }

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => clustersApi.create(data),
    onSuccess: () => {
      refresh()
      setShowCreate(false)
      setNewCluster({ name: '', description: '', master_server_id: '' })
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: { id: string; payload: Record<string, unknown> }) =>
      clustersApi.update(data.id, data.payload),
    onSuccess: () => {
      refresh()
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => clustersApi.delete(id),
    onSuccess: () => refresh(),
  })

  const startEdit = (cluster: any) => {
    setEditingId(cluster.id)
    setEditCluster({
      name: cluster.name,
      description: cluster.description || '',
      master_server_id: cluster.master_server_id || '',
    })
  }

  const clusters = clustersData?.data || []
  const servers = serversData?.data || []

  const inputCls = 'px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-purple-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100'

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <Network size={28} className="text-purple-600 dark:text-purple-400" />
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('cluster.title')}</h2>
          </div>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">{t('cluster.subtitle')}</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 text-sm font-medium"
        >
          <Plus size={16} />
          {t('cluster.add')}
        </button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4 mb-6">
          <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-3">{t('cluster.add')}</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <input
              type="text" placeholder={t('cluster.name')} value={newCluster.name}
              onChange={(e) => setNewCluster({ ...newCluster, name: e.target.value })}
              className={inputCls}
            />
            <select
              value={newCluster.master_server_id}
              onChange={(e) => setNewCluster({ ...newCluster, master_server_id: e.target.value })}
              className={inputCls}
            >
              <option value="">{t('cluster.selectMaster')}</option>
              {servers.map((s: any) => (
                <option key={s.id} value={s.id}>{s.name} ({s.host}:{s.port})</option>
              ))}
            </select>
            <input
              type="text" placeholder={t('cluster.description')} value={newCluster.description}
              onChange={(e) => setNewCluster({ ...newCluster, description: e.target.value })}
              className={`${inputCls} col-span-2`}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => createMutation.mutate(newCluster)}
              disabled={!newCluster.name || createMutation.isPending}
              className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            >
              {t('common.add')}
            </button>
            <button onClick={() => setShowCreate(false)} className="text-gray-600 dark:text-slate-400 px-4 py-1.5 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-slate-700">
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}

      {/* Cluster List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
        </div>
      ) : clusters.length === 0 ? (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-12 text-center">
          <Network size={48} className="mx-auto text-gray-300 dark:text-slate-600 mb-4" />
          <p className="text-gray-400 dark:text-slate-500">{t('cluster.empty')}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {clusters.map((cluster: any) => (
            <div key={cluster.id}>
              <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 hover:border-purple-300 dark:hover:border-purple-600 transition-colors">
                <div className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1 cursor-pointer" onClick={() => navigate(`/clusters/${cluster.id}`)}>
                      <div className="flex items-center gap-2">
                        <Network size={20} className="text-purple-500" />
                        <h3 className="font-semibold text-gray-900 dark:text-slate-100">{cluster.name}</h3>
                        <span className="text-xs bg-purple-100 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 px-2 py-0.5 rounded-full">
                          {t('cluster.memberCount', { count: cluster.member_count })}
                        </span>
                      </div>
                      {cluster.description && (
                        <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">{cluster.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => startEdit(cluster)}
                        className="p-2 text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg"
                        title={t('common.edit')}
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(t('common.confirm') + '?')) deleteMutation.mutate(cluster.id)
                        }}
                        className="p-2 text-gray-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg"
                        title={t('common.delete')}
                      >
                        <Trash2 size={16} />
                      </button>
                      <ChevronRight
                        size={20}
                        className="text-gray-300 dark:text-slate-600 cursor-pointer"
                        onClick={() => navigate(`/clusters/${cluster.id}`)}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Edit Form */}
              {editingId === cluster.id && (
                <div className="bg-gray-50 dark:bg-slate-700 rounded-b-xl border border-t-0 border-gray-200 dark:border-slate-600 p-4 ml-4">
                  <h4 className="font-semibold text-gray-900 dark:text-slate-100 mb-3">{t('cluster.edit')}</h4>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <input
                      type="text" placeholder={t('cluster.name')} value={editCluster.name}
                      onChange={(e) => setEditCluster({ ...editCluster, name: e.target.value })}
                      className={inputCls}
                    />
                    <select
                      value={editCluster.master_server_id}
                      onChange={(e) => setEditCluster({ ...editCluster, master_server_id: e.target.value })}
                      className={inputCls}
                    >
                      <option value="">{t('cluster.selectMaster')}</option>
                      {servers.map((s: any) => (
                        <option key={s.id} value={s.id}>{s.name} ({s.host}:{s.port})</option>
                      ))}
                    </select>
                    <input
                      type="text" placeholder={t('cluster.description')} value={editCluster.description}
                      onChange={(e) => setEditCluster({ ...editCluster, description: e.target.value })}
                      className={`${inputCls} col-span-2`}
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        updateMutation.mutate({
                          id: cluster.id,
                          payload: {
                            name: editCluster.name,
                            description: editCluster.description,
                            master_server_id: editCluster.master_server_id || null,
                          },
                        })
                      }}
                      disabled={!editCluster.name || updateMutation.isPending}
                      className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
                    >
                      {t('common.save')}
                    </button>
                    <button onClick={() => setEditingId(null)} className="text-gray-600 dark:text-slate-400 px-4 py-1.5 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-slate-700">
                      {t('common.cancel')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
