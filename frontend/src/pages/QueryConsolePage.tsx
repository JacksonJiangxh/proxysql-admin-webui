import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryApi, exportApi } from '../api/client'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import {
  Terminal, Play, Loader, History, Search, Trash2, X,
  ChevronLeft, ChevronRight, Download, Clock, AlertCircle,
} from 'lucide-react'

interface HistoryItem {
  id: number
  sql_text: string
  target: string
  database_name: string
  execution_time_ms: number | null
  row_count: number
  error: string | null
  created_at: string
}

const HISTORY_PAGE_SIZE = 20

export default function QueryConsolePage() {
  const selectedId = useServerStore((s) => s.selectedId)
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const [sql, setSql] = useState('SELECT * FROM main.mysql_servers')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const [historySearch, setHistorySearch] = useState('')
  const [historyPage, setHistoryPage] = useState(0)
  const [showExportMenu, setShowExportMenu] = useState(false)

  // Fetch query history
  const historyParams: Record<string, unknown> = {
    limit: HISTORY_PAGE_SIZE,
    offset: historyPage * HISTORY_PAGE_SIZE,
  }
  if (historySearch.trim()) {
    historyParams.search = historySearch.trim()
  }
  const { data: historyRes } = useQuery({
    queryKey: ['queryHistory', selectedId, historyParams],
    queryFn: () => queryApi.getHistory(selectedId!, historyParams),
    enabled: !!selectedId && showHistory,
  })

  const history: HistoryItem[] = historyRes?.data?.history || []
  const historyTotal: number = historyRes?.data?.total || 0
  const historyHasMore = (historyPage + 1) * HISTORY_PAGE_SIZE < historyTotal

  // Clear history mutation
  const clearMutation = useMutation({
    mutationFn: () => queryApi.clearHistory(selectedId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queryHistory', selectedId] })
      setHistoryPage(0)
    },
  })

  // Delete single history item
  const deleteItemMutation = useMutation({
    mutationFn: (id: number) => queryApi.deleteHistoryItem(selectedId!, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queryHistory', selectedId] })
    },
  })

  // Execute query
  const handleExecute = useCallback(async () => {
    if (!selectedId) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const resp = await queryApi.execute(selectedId, sql)
      setResult(resp.data)
      // Invalidate history after executing
      queryClient.invalidateQueries({ queryKey: ['queryHistory', selectedId] })
    } catch (err: any) {
      console.error('[Query]', err.response?.data?.detail || err.message)
      setError(t('query.failed'))
    } finally {
      setLoading(false)
    }
  }, [selectedId, sql, t, queryClient])

  // Load history item into editor
  const handleLoadHistory = useCallback((historySql: string) => {
    setSql(historySql)
    setShowHistory(false)
  }, [])

  // Export current results
  const handleExport = useCallback(async (format: 'csv' | 'json') => {
    if (!selectedId || !sql.trim()) return
    try {
      const resp = await exportApi.queryResult(selectedId, sql, format)
      const ext = format === 'csv' ? 'csv' : 'json'
      const mime = format === 'csv' ? 'text/csv' : 'application/json'
      const url = window.URL.createObjectURL(new Blob([resp.data], { type: mime }))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `query_export.${ext}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      // silently fail
    } finally {
      setShowExportMenu(false)
    }
  }, [selectedId, sql])

  const handleSearchKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      setHistoryPage(0)
      queryClient.invalidateQueries({ queryKey: ['queryHistory', selectedId] })
    }
  }, [queryClient, selectedId])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleExecute()
    }
  }, [handleExecute])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Terminal size={28} className="text-blue-600 dark:text-blue-400" />
          <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('query.title')}</h2>
        </div>
        <button
          onClick={() => setShowHistory((v) => !v)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
            showHistory
              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
              : 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-400 hover:bg-gray-200 dark:hover:bg-slate-600'
          }`}
        >
          <History size={16} />
          {t('query.historyTitle')}
        </button>
      </div>

      <p className="text-gray-500 dark:text-slate-400 mb-4">{t('query.subtitle')}</p>

      {!selectedId && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 text-amber-700 dark:text-amber-400 mb-4">
          {t('query.noServerSelected')}
        </div>
      )}

      {/* SQL Editor */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-600 dark:text-slate-400">{t('query.sqlLabel')}</span>
          <div className="flex items-center gap-2">
            {/* Export button */}
            {result && result.type === 'select' && result.rows?.length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setShowExportMenu((v) => !v)}
                  className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 border border-gray-300 dark:border-slate-600 px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Download size={14} />
                  {t('query.exportBtn')}
                </button>
                {showExportMenu && (
                  <div className="absolute right-0 top-full mt-1 bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-lg shadow-lg z-10 py-1 min-w-[140px]">
                    <button
                      onClick={() => handleExport('csv')}
                      className="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-700"
                    >
                      {t('query.exportCsv')}
                    </button>
                    <button
                      onClick={() => handleExport('json')}
                      className="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-700"
                    >
                      {t('query.exportJson')}
                    </button>
                  </div>
                )}
              </div>
            )}
            <button
              onClick={handleExecute}
              disabled={loading || !sql.trim() || !selectedId}
              className="flex items-center gap-2 bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? <Loader size={14} className="animate-spin" /> : <Play size={14} />}
              {t('query.execute')}
            </button>
          </div>
        </div>
        <textarea
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          className="w-full h-32 p-3 font-mono text-sm bg-gray-50 dark:bg-slate-700 border border-gray-200 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y text-gray-900 dark:text-slate-100"
          placeholder={t('query.placeholder')}
          onKeyDown={handleKeyDown}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-4 text-red-700 dark:text-red-400 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between">
            <span className="font-semibold text-gray-900 dark:text-slate-100">{t('query.results')}</span>
            <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-slate-400">
              {result.type === 'select' && <span>{result.row_count} {t('query.rows')}</span>}
              {result.elapsed_ms !== undefined && <span>{result.elapsed_ms}{t('query.ms')}</span>}
            </div>
          </div>

          {result.type === 'select' && result.rows?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-700">
                    {Object.keys(result.rows[0]).map((key) => (
                      <th key={key} className="text-left py-2 px-3 font-medium text-gray-600 dark:text-slate-400">{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row: any, i: number) => (
                    <tr key={i} className="border-b border-gray-100 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-700">
                      {Object.values(row).map((val: any, j: number) => (
                        <td key={j} className="py-2 px-3 text-gray-700 dark:text-slate-300 max-w-xs truncate">
                          {val !== null ? String(val) : <span className="text-gray-400 dark:text-slate-500 italic">{t('tables.null')}</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.type === 'modify' && (
            <div className="p-4 text-green-700 dark:text-green-400">
              {t('query.affected', { count: result.affected_rows })}
            </div>
          )}

          {result.type === 'admin_command' && (
            <div className="p-4">
              <pre className="text-sm text-gray-700 dark:text-slate-300 whitespace-pre-wrap">{result.output}</pre>
            </div>
          )}
        </div>
      )}

      {/* History Panel */}
      {showHistory && (
        <div className="fixed inset-y-0 right-0 w-96 bg-white dark:bg-slate-800 border-l border-gray-200 dark:border-slate-700 shadow-xl z-40 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-slate-700">
            <h3 className="font-semibold text-gray-900 dark:text-slate-100">{t('query.historyTitle')}</h3>
            <div className="flex items-center gap-2">
              {history.length > 0 && (
                <button
                  onClick={() => { if (confirm(t('query.historyClearConfirm'))) clearMutation.mutate() }}
                  className="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400"
                >
                  {t('query.historyClearAll')}
                </button>
              )}
              <button
                onClick={() => setShowHistory(false)}
                className="p-1 hover:bg-gray-100 dark:hover:bg-slate-700 rounded"
              >
                <X size={18} className="text-gray-500 dark:text-slate-400" />
              </button>
            </div>
          </div>

          {/* Search */}
          <div className="px-4 py-2">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder={t('query.historySearchPlaceholder')}
                className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-gray-50 dark:bg-slate-700 text-gray-900 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>

          {/* History List */}
          <div className="flex-1 overflow-y-auto px-2">
            {history.length === 0 ? (
              <div className="text-center text-gray-400 dark:text-slate-500 py-8">
                <History size={32} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">{t('query.historyEmpty')}</p>
              </div>
            ) : (
              <div className="space-y-1 py-1">
                {history.map((item) => (
                  <div
                    key={item.id}
                    className="group px-2 py-2 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700 cursor-pointer border border-transparent hover:border-gray-200 dark:hover:border-slate-600"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0" onClick={() => handleLoadHistory(item.sql_text)}>
                        <code className="text-xs text-gray-800 dark:text-slate-200 block truncate font-mono">
                          {item.sql_text}
                        </code>
                        <div className="flex items-center gap-3 mt-1 text-xs text-gray-400 dark:text-slate-500">
                          <span className="inline-flex items-center gap-1">
                            <Clock size={10} />
                            {item.execution_time_ms !== null ? `${item.execution_time_ms}ms` : '—'}
                          </span>
                          <span>{item.row_count} rows</span>
                          {item.error && (
                            <span className="inline-flex items-center gap-0.5 text-red-400">
                              <AlertCircle size={10} />{t('query.historyError')}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteItemMutation.mutate(item.id)
                        }}
                        className="p-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 rounded transition-all"
                        title={t('query.historyDeleteItem')}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Pagination */}
          {historyTotal > 0 && (
            <div className="px-4 py-2 border-t border-gray-200 dark:border-slate-700 flex items-center justify-between text-xs text-gray-500 dark:text-slate-400">
              <span>{t('query.historyTotal', { total: historyTotal })}</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setHistoryPage((p) => Math.max(0, p - 1))}
                  disabled={historyPage === 0}
                  className="p-1 hover:bg-gray-100 dark:hover:bg-slate-700 rounded disabled:opacity-30"
                >
                  <ChevronLeft size={14} />
                </button>
                <span className="px-2">{historyPage + 1}</span>
                <button
                  onClick={() => setHistoryPage((p) => p + 1)}
                  disabled={!historyHasMore}
                  className="p-1 hover:bg-gray-100 dark:hover:bg-slate-700 rounded disabled:opacity-30"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
