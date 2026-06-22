import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clustersApi, serversApi } from '../api/client'
import { useI18n } from '../i18n'
import {
  Network, ArrowLeft, Plus, Trash2, RefreshCw, Activity,
  CheckCircle, XCircle, AlertTriangle, Zap, Clock, Server,
  Settings, History, Search, Loader,
} from 'lucide-react'

const SYNC_MODULE_KEYS = [
  'proxysql_servers',
  'mysql_servers',
  'mysql_users',
  'mysql_query_rules',
  'mysql_variables',
  'admin_variables',
  'scheduler',
]

const inputCls = 'px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-purple-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100'

export default function ClusterDetailPage() {
  const { clusterId } = useParams<{ clusterId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { t } = useI18n()

  // Tab state
  const [activeTab, setActiveTab] = useState<'nodes' | 'sync' | 'logs' | 'variables'>('nodes')

  // Add member state
  const [showAddMember, setShowAddMember] = useState(false)
  const [newMember, setNewMember] = useState({ server_id: '', role: 'slave' })

  // Sync state
  const [selectedModules, setSelectedModules] = useState<string[]>([])
  const [autoApply, setAutoApply] = useState(true)
  const [autoSave, setAutoSave] = useState(false)
  const [selectedTargets, setSelectedTargets] = useState<string[]>([])

  // Variables state
  const [varEntries, setVarEntries] = useState<Array<{ name: string; value: string }>>([
    { name: 'admin-cluster_username', value: '' },
    { name: 'admin-cluster_password', value: '' },
    { name: 'admin-cluster_check_interval_ms', value: '1000' },
  ])

  // Queries
  const { data: clusterData, isLoading: clusterLoading } = useQuery({
    queryKey: ['cluster', clusterId],
    queryFn: () => clustersApi.get(clusterId!),
    enabled: !!clusterId,
  })

  const { data: membersData, isLoading: membersLoading } = useQuery({
    queryKey: ['cluster-members', clusterId],
    queryFn: () => clustersApi.listMembers(clusterId!),
    enabled: !!clusterId,
  })

  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ['cluster-status', clusterId],
    queryFn: () => clustersApi.getStatus(clusterId!),
    enabled: !!clusterId,
    refetchInterval: 15000,
  })

  const { data: serversData } = useQuery({
    queryKey: ['servers'],
    queryFn: () => serversApi.list(),
  })

  const { data: syncLogsData } = useQuery({
    queryKey: ['cluster-sync-logs', clusterId],
    queryFn: () => clustersApi.getSyncLogs(clusterId!),
    enabled: !!clusterId && activeTab === 'logs',
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['cluster-members', clusterId] })
    queryClient.invalidateQueries({ queryKey: ['cluster-status', clusterId] })
    queryClient.invalidateQueries({ queryKey: ['cluster', clusterId] })
  }

  // Mutations
  const addMemberMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => clustersApi.addMember(clusterId!, data),
    onSuccess: () => {
      refresh()
      setShowAddMember(false)
      setNewMember({ server_id: '', role: 'slave' })
    },
  })

  const removeMemberMutation = useMutation({
    mutationFn: (serverId: string) => clustersApi.removeMember(clusterId!, serverId),
    onSuccess: () => refresh(),
  })

  const syncMutation = useMutation({
    mutationFn: () => clustersApi.sync(clusterId!, {
      modules: selectedModules.length > 0 ? selectedModules : undefined,
      auto_apply: autoApply,
      auto_save: autoSave,
      target_servers: selectedTargets.length > 0 ? selectedTargets : undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cluster-sync-logs', clusterId] })
      refresh()
    },
  })

  const configVarsMutation = useMutation({
    mutationFn: () => {
      const vars: Record<string, string> = {}
      varEntries.forEach((e) => {
        if (e.name && e.value) vars[e.name] = e.value
      })
      return clustersApi.configureVariables(clusterId!, vars)
    },
    onSuccess: () => refresh(),
  })

  const discoverMutation = useMutation({
    mutationFn: () => clustersApi.discover(clusterId!),
  })

  const cluster = clusterData?.data
  const members = membersData?.data || []
  const status = statusData?.data
  const servers = serversData?.data || []
  const syncLogs = syncLogsData?.data || []

  // Get available servers (not already in cluster)
  const memberIds = new Set(members.map((m: any) => m.server_id))
  const availableServers = servers.filter((s: any) => !memberIds.has(s.id))

  const toggleModule = (key: string) => {
    setSelectedModules((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    )
  }

  const toggleTarget = (serverId: string) => {
    setSelectedTargets((prev) =>
      prev.includes(serverId) ? prev.filter((s) => s !== serverId) : [...prev, serverId]
    )
  }

  if (clusterLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
      </div>
    )
  }

  if (!cluster) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400 dark:text-slate-500">{t('cluster.notFound')}</p>
      </div>
    )
  }

  const nodes = status?.nodes || []
  const consistency = status?.config_consistency

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate('/clusters')}
            className="flex items-center gap-1 text-sm text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-300 mb-2"
          >
            <ArrowLeft size={14} />
            {t('cluster.backToList')}
          </button>
          <div className="flex items-center gap-3">
            <Network size={28} className="text-purple-600 dark:text-purple-400" />
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{cluster.name}</h2>
            <span className="text-xs bg-purple-100 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 px-2 py-0.5 rounded-full">
              {t('cluster.totalNodes', { count: members.length })}
            </span>
          </div>
          {cluster.description && (
            <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">{cluster.description}</p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              setActiveTab('sync')
              syncMutation.mutate()
            }}
            disabled={syncMutation.isPending || members.length < 2}
            className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 text-sm font-medium disabled:opacity-50"
          >
            {syncMutation.isPending ? <Loader size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            {t('cluster.syncAll')}
          </button>
        </div>
      </div>

      {/* Config Consistency Summary */}
      {consistency && (
        <div className={`rounded-xl border p-4 mb-6 ${consistency.status === 'consistent' ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700' : 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-700'}`}>
          <div className="flex items-center gap-2">
            {consistency.status === 'consistent' ? (
              <CheckCircle size={20} className="text-green-600 dark:text-green-400" />
            ) : (
              <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400" />
            )}
            <span className={`font-semibold ${consistency.status === 'consistent' ? 'text-green-700 dark:text-green-400' : 'text-yellow-700 dark:text-yellow-400'}`}>
              {consistency.status === 'consistent' ? t('cluster.consistent') : t('cluster.inconsistent')}
            </span>
            {consistency.status !== 'single_node' && (
              <span className="text-sm text-gray-500 dark:text-slate-400 ml-2">
                {t('cluster.consistentTables', {
                  consistent: consistency.consistent_tables || 0,
                  total: consistency.total_tables || 0,
                })}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 dark:bg-slate-700 rounded-lg p-1 mb-6 w-fit">
        {([
          ['nodes', Activity],
          ['sync', RefreshCw],
          ['variables', Settings],
          ['logs', History],
        ] as const).map(([tab, Icon]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'bg-white dark:bg-slate-600 text-gray-900 dark:text-slate-100 shadow-sm'
                : 'text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-300'
            }`}
          >
            <Icon size={15} />
            {t(`cluster.${tab}`)}
          </button>
        ))}
      </div>

      {/* Tab: Nodes */}
      {activeTab === 'nodes' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-slate-100">{t('cluster.nodes')}</h3>
            <div className="flex gap-2">
              <button
                onClick={() => discoverMutation.mutate()}
                disabled={discoverMutation.isPending}
                className="flex items-center gap-1.5 text-sm text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 px-3 py-1.5 rounded-lg border border-purple-200 dark:border-purple-700 hover:bg-purple-50 dark:hover:bg-purple-900/20"
              >
                {discoverMutation.isPending ? <Loader size={14} className="animate-spin" /> : <Search size={14} />}
                {t('cluster.discover')}
              </button>
              <button
                onClick={() => setShowAddMember(!showAddMember)}
                className="flex items-center gap-1.5 text-sm bg-purple-600 text-white px-3 py-1.5 rounded-lg hover:bg-purple-700"
              >
                <Plus size={14} />
                {t('cluster.addNode')}
              </button>
            </div>
          </div>

          {/* Add Member Form */}
          {showAddMember && (
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4 mb-4">
              <div className="flex items-center gap-3">
                <select
                  value={newMember.server_id}
                  onChange={(e) => setNewMember({ ...newMember, server_id: e.target.value })}
                  className={`flex-1 ${inputCls}`}
                >
                  <option value="">{t('cluster.selectServer')}</option>
                  {availableServers.map((s: any) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.host}:{s.port})</option>
                  ))}
                </select>
                <select
                  value={newMember.role}
                  onChange={(e) => setNewMember({ ...newMember, role: e.target.value })}
                  className={inputCls}
                >
                  <option value="slave">{t('cluster.role.slave')}</option>
                  <option value="master">{t('cluster.role.master')}</option>
                </select>
                <button
                  onClick={() => addMemberMutation.mutate(newMember)}
                  disabled={!newMember.server_id || addMemberMutation.isPending}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
                >
                  {t('common.add')}
                </button>
                <button onClick={() => setShowAddMember(false)} className="text-gray-600 dark:text-slate-400 px-4 py-2 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-slate-700">
                  {t('common.cancel')}
                </button>
              </div>
            </div>
          )}

          {/* Discover Results */}
          {discoverMutation.data?.data?.peers && discoverMutation.data.data.peers.length > 0 && (
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-xl p-4 mb-4">
              <h4 className="font-medium text-blue-800 dark:text-blue-300 mb-2">{t('cluster.discoveredPeers')}</h4>
              <div className="space-y-1">
                {discoverMutation.data.data.peers.map((p: any, i: number) => (
                  <div key={i} className="text-sm text-blue-700 dark:text-blue-400">
                    {p.hostname}:{p.port} ({t('cluster.weight')}: {p.weight}) {p.comment ? `- ${p.comment}` : ''}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Members List */}
          {membersLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
            </div>
          ) : members.length === 0 ? (
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-12 text-center">
              <Server size={48} className="mx-auto text-gray-300 dark:text-slate-600 mb-4" />
              <p className="text-gray-400 dark:text-slate-500">{t('cluster.noMembers')}</p>
            </div>
          ) : (
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700">
                    <th className="text-left py-2.5 px-4 text-gray-600 dark:text-slate-400">{t('cluster.nodeName')}</th>
                    <th className="text-left py-2.5 px-4 text-gray-600 dark:text-slate-400">{t('cluster.nodeAddress')}</th>
                    <th className="text-left py-2.5 px-4 text-gray-600 dark:text-slate-400">{t('cluster.nodeRole')}</th>
                    <th className="text-left py-2.5 px-4 text-gray-600 dark:text-slate-400">{t('cluster.nodeStatus')}</th>
                    <th className="text-left py-2.5 px-4 text-gray-600 dark:text-slate-400">{t('cluster.version')}</th>
                    <th className="text-right py-2.5 px-4 text-gray-600 dark:text-slate-400">{t('common.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((member: any) => {
                    const nodeStatus = nodes.find((n: any) => n.server_id === member.server_id)
                    return (
                      <tr key={member.server_id} className="border-b border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                        <td className="py-2.5 px-4 font-medium text-gray-900 dark:text-slate-100">{member.server_name}</td>
                        <td className="py-2.5 px-4 text-gray-500 dark:text-slate-400">{member.server_host}:{member.server_port}</td>
                        <td className="py-2.5 px-4">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                            member.role === 'master'
                              ? 'bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400'
                              : 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400'
                          }`}>
                            {member.role === 'master' ? t('cluster.role.master') : t('cluster.role.slave')}
                          </span>
                        </td>
                        <td className="py-2.5 px-4">
                          {statusLoading ? (
                            <Loader size={14} className="animate-spin text-gray-400" />
                          ) : nodeStatus ? (
                            nodeStatus.online ? (
                              <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
                                <CheckCircle size={14} />
                                <span className="text-xs">{t('cluster.status.online')}</span>
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-red-500 dark:text-red-400" title={t('cluster.status.offlineDetail')}>
                                <XCircle size={14} />
                                <span className="text-xs">{t('cluster.status.offline')}</span>
                              </span>
                            )
                          ) : (
                            <span className="text-xs text-gray-400 dark:text-slate-500">{t('cluster.status.unknown')}</span>
                          )}
                        </td>
                        <td className="py-2.5 px-4 text-gray-500 dark:text-slate-400 text-xs">
                          {nodeStatus?.version || '-'}
                        </td>
                        <td className="py-2.5 px-4 text-right">
                          <button
                            onClick={() => {
                              if (confirm(t('common.confirm') + '?')) {
                                removeMemberMutation.mutate(member.server_id)
                              }
                            }}
                            className="p-1.5 text-gray-400 dark:text-slate-500 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg"
                            title={t('common.delete')}
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Consistency Detail */}
          {consistency && consistency.tables && Object.keys(consistency.tables).length > 0 && (
            <div className="mt-6">
              <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-3">{t('cluster.configConsistency')}</h3>
              <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700">
                      <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('cluster.table')}</th>
                      <th className="text-center py-2 px-4 text-gray-600 dark:text-slate-400">{t('common.status')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(consistency.tables).map(([table, info]: [string, any]) => (
                      <tr key={table} className="border-b border-gray-100 dark:border-slate-700">
                        <td className="py-2 px-4 font-mono text-xs">{table}</td>
                        <td className="py-2 px-4 text-center">
                          {info.consistent ? (
                            <CheckCircle size={16} className="inline text-green-500" />
                          ) : (
                            <AlertTriangle size={16} className="inline text-yellow-500" />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Sync */}
      {activeTab === 'sync' && (
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-4">{t('cluster.sync')}</h3>

          <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4 mb-4 space-y-4">
            {/* Modules */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">{t('cluster.selectModules')}</label>
              <div className="flex flex-wrap gap-2">
                {SYNC_MODULE_KEYS.map((key) => (
                  <button
                    key={key}
                    onClick={() => toggleModule(key)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      selectedModules.includes(key)
                        ? 'bg-purple-100 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 border border-purple-300 dark:border-purple-600'
                        : 'bg-gray-100 dark:bg-slate-600 text-gray-600 dark:text-slate-300 border border-gray-200 dark:border-slate-500 hover:bg-gray-200 dark:hover:bg-slate-500'
                    }`}
                  >
                    {t(`cluster.syncModule.${key}`)}
                  </button>
                ))}
              </div>
            </div>

            {/* Target Servers */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">{t('cluster.selectTargets')}</label>
              <div className="flex flex-wrap gap-2">
                {members
                  .filter((m: any) => m.role === 'slave')
                  .map((m: any) => (
                    <button
                      key={m.server_id}
                      onClick={() => toggleTarget(m.server_id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        selectedTargets.includes(m.server_id)
                          ? 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 border border-blue-300 dark:border-blue-600'
                          : 'bg-gray-100 dark:bg-slate-600 text-gray-600 dark:text-slate-300 border border-gray-200 dark:border-slate-500 hover:bg-gray-200 dark:hover:bg-slate-500'
                      }`}
                    >
                      {m.server_name}
                    </button>
                  ))}
                {members.filter((m: any) => m.role === 'slave').length === 0 && (
                  <span className="text-xs text-gray-400 dark:text-slate-500">{t('cluster.noSlaveNodes')}</span>
                )}
              </div>
            </div>

            {/* Options */}
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoApply}
                  onChange={(e) => setAutoApply(e.target.checked)}
                  className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                />
                {t('cluster.autoApply')}
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoSave}
                  onChange={(e) => setAutoSave(e.target.checked)}
                  className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                />
                {t('cluster.autoSave')}
              </label>
            </div>

            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="flex items-center gap-2 bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700 text-sm font-medium disabled:opacity-50"
            >
              {syncMutation.isPending ? <Loader size={16} className="animate-spin" /> : <Zap size={16} />}
              {syncMutation.isPending ? t('cluster.syncing') : t('cluster.sync')}
            </button>
          </div>

          {/* Sync Result */}
          {syncMutation.data?.data && (
            <div className={`rounded-xl border p-4 ${syncMutation.data.data.failed_count > 0 ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-700' : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700'}`}>
              <div className="flex items-center gap-2 mb-3">
                {syncMutation.data.data.failed_count > 0 ? (
                  <AlertTriangle size={20} className="text-yellow-600 dark:text-yellow-400" />
                ) : (
                  <CheckCircle size={20} className="text-green-600 dark:text-green-400" />
                )}
                <span className="font-semibold">
                  {t('cluster.syncSuccess', {
                    success: syncMutation.data.data.success_count,
                    total: syncMutation.data.data.success_count + syncMutation.data.data.failed_count,
                  })}
                </span>
              </div>
              {syncMutation.data.data.results?.map((r: any, i: number) => (
                <div key={i} className="text-sm mb-2 last:mb-0">
                  <span className="font-medium">{r.server_id}:</span>
                  {r.modules?.map((m: any, j: number) => (
                    <span key={j} className={`ml-2 text-xs ${m.success ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400'}`}>
                      {m.module} {m.success ? t('cluster.rowsCount', { count: m.rows }) : `✗ ${t('common.failed')}`}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: Variables */}
      {activeTab === 'variables' && (
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-4">{t('cluster.variables')}</h3>

          <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4 mb-4">
            <div className="space-y-3">
              {varEntries.map((entry, idx) => (
                <div key={idx} className="flex gap-3">
                  <input
                    type="text"
                    placeholder={t('cluster.variableName')}
                    value={entry.name}
                    onChange={(e) => {
                      const updated = [...varEntries]
                      updated[idx] = { ...updated[idx], name: e.target.value }
                      setVarEntries(updated)
                    }}
                    className={`flex-1 ${inputCls} font-mono`}
                  />
                  <input
                    type="text"
                    placeholder={t('cluster.variableValue')}
                    value={entry.value}
                    onChange={(e) => {
                      const updated = [...varEntries]
                      updated[idx] = { ...updated[idx], value: e.target.value }
                      setVarEntries(updated)
                    }}
                    className={`flex-1 ${inputCls}`}
                  />
                  <button
                    onClick={() => setVarEntries(varEntries.filter((_, i) => i !== idx))}
                    className="p-2 text-gray-400 dark:text-slate-500 hover:text-red-500 dark:hover:text-red-400"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={() => setVarEntries([...varEntries, { name: '', value: '' }])}
              className="flex items-center gap-1 text-sm text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 mt-3"
            >
              <Plus size={14} />
              {t('cluster.addVariable')}
            </button>
          </div>

          <button
            onClick={() => configVarsMutation.mutate()}
            disabled={configVarsMutation.isPending || varEntries.every((e) => !e.name || !e.value)}
            className="flex items-center gap-2 bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700 text-sm font-medium disabled:opacity-50"
          >
            {configVarsMutation.isPending ? <Loader size={16} className="animate-spin" /> : <Settings size={16} />}
            {t('cluster.configureVariables')}
          </button>

          {configVarsMutation.data?.data && (
            <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-xl text-sm text-green-700 dark:text-green-400">
              {t('cluster.varsConfigured', { count: configVarsMutation.data.data.results?.length || 0 })}
            </div>
          )}
        </div>
      )}

      {/* Tab: Logs */}
      {activeTab === 'logs' && (
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-4">{t('cluster.syncLogs')}</h3>
          {syncLogs.length === 0 ? (
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-12 text-center">
              <History size={48} className="mx-auto text-gray-300 dark:text-slate-600 mb-4" />
              <p className="text-gray-400 dark:text-slate-500">{t('cluster.noSyncLogs')}</p>
            </div>
          ) : (
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700">
                    <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('settings.time')}</th>
                    <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('settings.user')}</th>
                    <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('settings.action')}</th>
                    <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('cluster.source')}</th>
                    <th className="text-center py-2 px-4 text-gray-600 dark:text-slate-400">{t('cluster.successFailed')}</th>
                    <th className="text-left py-2 px-4 text-gray-600 dark:text-slate-400">{t('settings.details')}</th>
                  </tr>
                </thead>
                <tbody>
                  {syncLogs.map((log: any) => (
                    <tr key={log.id} className="border-b border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                      <td className="py-2 px-4 text-xs text-gray-500 dark:text-slate-400">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="py-2 px-4 text-gray-900 dark:text-slate-100">{log.username}</td>
                      <td className="py-2 px-4">
                        <span className="text-xs bg-purple-100 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 px-2 py-0.5 rounded-full">
                          {log.action}
                        </span>
                      </td>
                      <td className="py-2 px-4 text-xs text-gray-500 dark:text-slate-400">{log.source_server_id}</td>
                      <td className="py-2 px-4 text-center">
                        <span className="text-green-600 dark:text-green-400">{log.success_count}</span>
                        {' / '}
                        <span className="text-red-500 dark:text-red-400">{log.failed_count}</span>
                      </td>
                      <td className="py-2 px-4 text-xs text-gray-400 dark:text-slate-500 max-w-xs truncate">
                        {log.details}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
