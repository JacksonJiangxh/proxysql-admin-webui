import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { tablesApi } from '../api/client'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import { Table, Database, HardDrive, Cpu, Zap, BarChart3, Monitor, History, ChevronDown, ChevronRight, Lightbulb, type LucideIcon } from 'lucide-react'

type GroupName = string

interface TableGroups {
  [key: string]: string[]
}

interface TableListResponse {
  groups: TableGroups
  table_db: Record<string, string>
}

interface LayerConfigItem {
  key: GroupName
  label: string
  icon: LucideIcon
  color: string
}

// Known layer configs — fallback for groups the backend may return.
const KNOWN_LAYERS_KEYS = ['disk', 'memory', 'runtime', 'stats', 'monitor', 'stats_history']

function buildLayerConfigs(groups: TableGroups, t: (key: string) => string): LayerConfigItem[] {
  const iconMap: Record<string, LucideIcon> = {
    disk: HardDrive,
    memory: Cpu,
    runtime: Zap,
    stats: BarChart3,
    monitor: Monitor,
    stats_history: History,
  }
  const colorMap: Record<string, string> = {
    disk: 'text-amber-600 dark:text-amber-400',
    memory: 'text-blue-600 dark:text-blue-400',
    runtime: 'text-green-600 dark:text-green-400',
    stats: 'text-purple-600 dark:text-purple-400',
    monitor: 'text-orange-600 dark:text-orange-400',
    stats_history: 'text-teal-600 dark:text-teal-400',
  }
  return Object.keys(groups).map(key => {
    if (KNOWN_LAYERS_KEYS.includes(key)) {
      return { key, label: t(`tables.layer.${key}`), icon: iconMap[key] || Database, color: colorMap[key] || 'text-gray-600 dark:text-gray-400' }
    }
    return { key, label: t('tables.layer.other'), icon: Database, color: 'text-gray-600 dark:text-gray-400' }
  })
}

function dbForTable(tableName: string, layer: string, tableDb: Record<string, string>): string {
  if (tableDb[tableName]) return tableDb[tableName]
  // fallback
  switch (layer) {
    case 'disk':       return 'disk'
    case 'monitor':    return 'monitor'
    case 'stats_history': return 'stats_history'
    case 'stats':      return 'main'
    case 'runtime':    return 'main'
    default:           return 'main'
  }
}

export default function TableBrowserPage() {
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [selectedLayer, setSelectedLayer] = useState<string>('memory')
  const [collapsedLayers, setCollapsedLayers] = useState<Set<string>>(new Set())
  const selectedId = useServerStore((s) => s.selectedId)
  const { t } = useI18n()

  const { data: tablesRes, isLoading: tablesLoading } = useQuery({
    queryKey: ['tables', selectedId],
    queryFn: () => tablesApi.list(selectedId!),
    enabled: !!selectedId,
  })

  const groups: TableGroups = tablesRes?.data?.groups || {}
  const tableDb: Record<string, string> = tablesRes?.data?.table_db || {}
  const layerConfigs = useMemo(() => buildLayerConfigs(groups, t), [groups, t])

  const selectedDatabase = useMemo(
    () => (selectedTable ? dbForTable(selectedTable, selectedLayer, tableDb) : 'main'),
    [selectedTable, selectedLayer, tableDb],
  )

  const { data: tableData, isLoading: dataLoading } = useQuery({
    queryKey: ['tables', selectedId, selectedTable, selectedLayer, selectedDatabase],
    queryFn: () => {
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      const params: Record<string, unknown> = { page_size: 100, layer: selectedLayer }
      if (selectedDatabase) params.database = selectedDatabase
      return tablesApi.getData(selectedId!, selectedTable!, params)
    },
    enabled: !!selectedId && !!selectedTable,
  })

  const toggleLayer = (key: string) => {
    setCollapsedLayers(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      return next
    })
  }

  // Guide text for the currently selected table.
  const guideKey = selectedTable ? `tables.guide.${selectedTable}` : ''
  const guideText = t(guideKey)
  const hasSpecificGuide = guideText !== '' && guideText !== guideKey
  const displayGuide = hasSpecificGuide ? guideText : t('tables.guide._default')

  if (!selectedId) {
    return (
      <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 text-amber-700 dark:text-amber-400">
        {t('tables.noServerSelected')}
      </div>
    )
  }

  if (tablesLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  const columns = tableData?.data?.column_names || []
  const rows = tableData?.data?.rows || []

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Table size={28} className="text-blue-600 dark:text-blue-400" />
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('tables.title')}</h2>
      </div>

      <div className="flex gap-4">
        {/* Table List – grouped by layer */}
        <div className="w-72 shrink-0">
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
            <h3 className="text-sm font-semibold text-gray-500 dark:text-slate-400 uppercase mb-3">{t('nav.tables')}</h3>
            <div className="space-y-2">
              {layerConfigs.map(({ key, label, icon: Icon, color }) => {
                const tableList = groups[key] || []
                if (tableList.length === 0) return null
                const isCollapsed = collapsedLayers.has(key)
                return (
                  <div key={key}>
                    <button
                      onClick={() => toggleLayer(key)}
                      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
                    >
                      {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                      <Icon size={14} className={color} />
                      <span className={color}>{label}</span>
                      <span className="ml-auto text-gray-400 dark:text-slate-500 font-normal">{tableList.length}</span>
                    </button>
                    {!isCollapsed && (
                      <div className="ml-2 space-y-0.5 mt-1">
                        {tableList.map((name: string) => (
                          <button
                            key={key + name}
                            onClick={() => { setSelectedTable(name); setSelectedLayer(key) }}
                            className={`w-full text-left pl-7 pr-3 py-1.5 rounded-md text-sm transition-colors ${
                              selectedTable === name && selectedLayer === key
                                ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                                : 'text-gray-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-700'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <Database size={12} className="shrink-0" />
                              <span className="truncate">{name}</span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Table Data */}
        <div className="flex-1">
          {selectedTable ? (
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700">
              <div className="px-4 py-3 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between">
                <h3 className="font-semibold text-gray-900 dark:text-slate-100">
                  {selectedTable}
                  <span className="ml-2 text-xs font-normal text-gray-400 dark:text-slate-500 uppercase">
                    ({selectedLayer}{selectedDatabase !== 'main' ? ` · ${selectedDatabase}` : ''})
                  </span>
                </h3>
                <span className="text-sm text-gray-500 dark:text-slate-400">{rows.length} {t('tables.rows')}</span>
              </div>

              {/* ── Beginner's Guide Panel ── */}
              <div className="mx-4 mt-3 mb-1 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg px-4 py-3">
                <div className="flex items-start gap-2">
                  <Lightbulb size={18} className="text-blue-500 dark:text-blue-400 mt-0.5 shrink-0" />
                  <div>
                    <h4 className="text-sm font-semibold text-blue-700 dark:text-blue-300 mb-1">
                      {t('tables.guideTitle')}
                    </h4>
                    <p className="text-sm text-blue-700 dark:text-blue-300 leading-relaxed whitespace-pre-line">
                      {displayGuide}
                    </p>
                  </div>
                </div>
              </div>

              <div className="overflow-x-auto">
                {dataLoading ? (
                  <div className="p-8 text-center text-gray-500 dark:text-slate-400">{t('common.loading')}</div>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700">
                        {columns.map((col: string) => (
                          <th key={col} className="text-left py-2 px-3 font-medium text-gray-600 dark:text-slate-400">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row: any, i: number) => (
                        <tr key={i} className="border-b border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                          {columns.map((col: string, j: number) => (
                            <td key={j} className="py-2 px-3 text-gray-700 dark:text-slate-300 max-w-xs truncate">
                              {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="text-gray-400 dark:text-slate-500 italic">{t('tables.null')}</span>}
                            </td>
                          ))}
                        </tr>
                      ))}
                      {rows.length === 0 && (
                        <tr>
                          <td colSpan={columns.length} className="py-8 text-center text-gray-400 dark:text-slate-500">
                            {t('tables.empty')}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-12 text-center">
              <Lightbulb size={48} className="mx-auto text-gray-300 dark:text-slate-600 mb-4" />
              <p className="text-gray-500 dark:text-slate-400">{t('tables.selectTable')}</p>
              <p className="text-gray-400 dark:text-slate-500 text-sm mt-2 max-w-md mx-auto">{t('tables.guideHint')}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
