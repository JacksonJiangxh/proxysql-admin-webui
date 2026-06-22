import { useState, useCallback } from 'react'
import { queryApi } from '../api/client'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import { Terminal, Play, Loader } from 'lucide-react'

export default function QueryConsolePage() {
  const selectedId = useServerStore((s) => s.selectedId)
  const { t } = useI18n()
  const [sql, setSql] = useState('SELECT * FROM main.mysql_servers')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // useCallback: stable handler for execute button and keyboard shortcut,
  // prevents re-creating the function on every keystroke.
  const handleExecute = useCallback(async () => {
    if (!selectedId) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const resp = await queryApi.execute(selectedId, sql)
      setResult(resp.data)
    } catch (err: any) {
      console.error('[Query]', err.response?.data?.detail || err.message)
      setError(t('query.failed'))
    } finally {
      setLoading(false)
    }
  }, [selectedId, sql, t])

  // useCallback: stable onChange handler for textarea
  const handleSqlChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setSql(e.target.value)
  }, [])

  // useCallback: keyboard shortcut handler (Ctrl+Enter to execute)
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleExecute()
    }
  }, [handleExecute])

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Terminal size={28} className="text-blue-600 dark:text-blue-400" />
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('query.title')}</h2>
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
          <button
            onClick={handleExecute}
            disabled={loading || !sql.trim() || !selectedId}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader size={14} className="animate-spin" /> : <Play size={14} />}
            {t('query.execute')}
          </button>
        </div>
        <textarea
          value={sql}
          onChange={handleSqlChange}
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
    </div>
  )
}
