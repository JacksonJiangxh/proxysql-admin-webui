/**
 * Database Manager Page — direct backend MySQL database management.
 *
 * Allows users to browse and query backend MySQL databases that are
 * registered in ProxySQL's mysql_servers table. All connection info
 * (host, port, credentials) comes from ProxySQL configuration.
 *
 * Features:
 * - Backend server list (from ProxySQL mysql_servers)
 * - Connection test
 * - Database/table browser
 * - Table data viewer with pagination
 * - SQL query console with result display
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import { dbManagerApi } from '../api/client'
import {
  Database, Table, Play, Loader2, AlertTriangle, Server,
  ChevronRight, ChevronDown, RefreshCw, Zap, Terminal,
  HardDrive, Info, X, CheckCircle, XCircle, ArrowLeft,
  Clock, Hash, FileText, Columns,
} from 'lucide-react'

// ── Types ──

interface BackendUser {
  username: string
  default_hostgroup: number
  default_schema: string
  active: number
  max_connections: number
  comment: string
}

interface BackendServer {
  id: string
  hostgroup_id: number
  hostname: string
  port: number
  status: string
  comment: string
  available_users: BackendUser[]
}

interface ConnectionTestResult {
  success: boolean
  version?: string
  server_time?: string
  error?: string
  elapsed_ms: number
}

interface TableInfo {
  name: string
  rows_estimate?: number
}

interface ColumnSchema {
  field: string
  type: string
  null: string
  key: string
  default: string | null
  extra: string
}

interface QueryResult {
  type: 'select' | 'modify' | 'error'
  rows?: Record<string, unknown>[]
  columns?: string[]
  row_count: number
  affected_rows?: number
  elapsed_ms: number
  error?: string
}

// ── Sub-components ──

/** Backend server list panel */
function BackendList({
  backends, selectedId, selectedUsername, onSelect, onTest, testing, testResult, onRefresh, loading,
}: {
  backends: BackendServer[]
  selectedId: string | null
  selectedUsername: string
  onSelect: (s: BackendServer) => void
  onTest: (s: BackendServer) => void
  testing: string | null
  testResult: { id: string; result: ConnectionTestResult } | null
  onRefresh: () => void
  loading: boolean
}) {
  const { t } = useI18n()
  const statusColor = (status: string) => {
    const s = status.toUpperCase()
    if (s === 'ONLINE') return 'text-green-500'
    if (s === 'OFFLINE_SOFT' || s === 'OFFLINE_HARD') return 'text-red-500'
    if (s === 'SHUNNED') return 'text-orange-500'
    return 'text-gray-400'
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-slate-700">
        <h3 className="font-medium text-gray-900 dark:text-slate-100 flex items-center gap-2">
          <Server size={16} className="text-blue-500" />
          {t('dbm.backends')}
          {backends.length > 0 && (
            <span className="text-xs text-gray-400 font-normal">({backends.length})</span>
          )}
        </h3>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-1.5 hover:bg-gray-100 dark:hover:bg-slate-700 rounded text-gray-400 hover:text-gray-600"
          title={t('common.refresh')}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {loading && backends.length === 0 ? (
        <div className="flex items-center justify-center py-12 text-gray-400">
          <Loader2 size={20} className="animate-spin mr-2" />
          <span className="text-sm">{t('common.loading')}</span>
        </div>
      ) : backends.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-gray-400 px-4">
          <Database size={32} className="mb-2 opacity-50" />
          <p className="text-sm text-center">{t('dbm.noBackends')}</p>
          <p className="text-xs text-center mt-1 text-gray-400 dark:text-slate-500">
            {t('dbm.noBackendsHint')}
          </p>
        </div>
      ) : (
        <div className="divide-y divide-gray-100 dark:divide-slate-700/50 max-h-[400px] overflow-y-auto">
          {backends.map((be) => (
            <div key={be.id}>
              <button
                onClick={() => onSelect(be)}
                className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-slate-700/50 transition-colors ${
                  selectedId === be.id
                    ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-blue-500'
                    : 'border-l-2 border-transparent'
                }`}
              >
                <div className={`w-2 h-2 rounded-full shrink-0 ${statusColor(be.status)}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 dark:text-slate-100 truncate">
                    {be.hostname}:{be.port}
                  </div>
                  <div className="text-xs text-gray-400 dark:text-slate-500 truncate">
                    HG: {be.hostgroup_id} · {be.status}
                    {be.comment ? ` · ${be.comment}` : ''}
                  </div>
                  {be.available_users.length > 0 && selectedId === be.id && (
                    <div className="text-[10px] text-blue-500 dark:text-blue-400 mt-0.5 font-medium">
                      {selectedUsername || t('dbm.noUserSelected')}
                    </div>
                  )}
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onTest(be)
                  }}
                  disabled={testing === be.id}
                  className="p-1.5 hover:bg-gray-200 dark:hover:bg-slate-600 rounded shrink-0"
                  title={t('dbm.testConnection')}
                >
                  {testing === be.id ? (
                    <Loader2 size={14} className="animate-spin text-blue-500" />
                  ) : (
                    <Zap size={14} className="text-gray-400" />
                  )}
                </button>
              </button>
              {/* Test result inline */}
              {testResult?.id === be.id && (
                <div className={`mx-4 mb-2 px-3 py-2 rounded text-xs flex items-start gap-2 ${
                  testResult.result.success
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300'
                    : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
                }`}>
                  {testResult.result.success
                    ? <CheckCircle size={14} className="shrink-0 mt-0.5" />
                    : <XCircle size={14} className="shrink-0 mt-0.5" />
                  }
                  <div>
                    {testResult.result.success
                      ? <>{testResult.result.version} · {testResult.result.server_time} · {testResult.result.elapsed_ms}ms</>
                      : testResult.result.error
                    }
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

/** Database list panel */
function DatabaseList({
  databases, selectedDb, onSelect, loading,
}: {
  databases: string[]
  selectedDb: string | null
  onSelect: (db: string) => void
  loading: boolean
}) {
  const { t } = useI18n()
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-400">
        <Loader2 size={16} className="animate-spin mr-2" />
        <span className="text-sm">{t('common.loading')}</span>
      </div>
    )
  }
  if (databases.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">{t('dbm.noDatabases')}</div>
    )
  }
  return (
    <div className="space-y-0.5">
      {databases.map((db) => (
        <button
          key={db}
          onClick={() => onSelect(db)}
          className={`w-full flex items-center gap-2 px-3 py-1.5 rounded text-sm text-left transition-colors ${
            selectedDb === db
              ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
              : 'text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700/50'
          }`}
        >
          <Database size={14} className="shrink-0" />
          <span className="truncate">{db}</span>
        </button>
      ))}
    </div>
  )
}

/** Table list panel */
function TableList({
  tables, selectedTable, onSelect, loading,
}: {
  tables: string[]
  selectedTable: string | null
  onSelect: (table: string) => void
  loading: boolean
}) {
  const { t } = useI18n()
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-400">
        <Loader2 size={16} className="animate-spin mr-2" />
        <span className="text-sm">{t('common.loading')}</span>
      </div>
    )
  }
  if (tables.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">{t('dbm.noTables')}</div>
    )
  }
  return (
    <div className="space-y-0.5">
      {tables.map((tbl) => (
        <button
          key={tbl}
          onClick={() => onSelect(tbl)}
          className={`w-full flex items-center gap-2 px-3 py-1.5 rounded text-sm text-left transition-colors ${
            selectedTable === tbl
              ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
              : 'text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700/50'
          }`}
        >
          <Table size={14} className="shrink-0" />
          <span className="truncate">{tbl}</span>
        </button>
      ))}
    </div>
  )
}

/** Schema panel */
function SchemaPanel({ columns, loading }: { columns: ColumnSchema[]; loading: boolean }) {
  const { t } = useI18n()
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-400">
        <Loader2 size={16} className="animate-spin mr-2" />
        <span className="text-sm">{t('common.loading')}</span>
      </div>
    )
  }
  if (columns.length === 0) return null
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 dark:border-slate-700">
            <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 uppercase">{t('dbm.column')}</th>
            <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 uppercase">{t('dbm.type')}</th>
            <th className="text-center py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 uppercase">{t('dbm.nullable')}</th>
            <th className="text-center py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 uppercase">{t('dbm.key')}</th>
            <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 uppercase">{t('dbm.default')}</th>
            <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 uppercase">{t('dbm.extra')}</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => (
            <tr key={col.field} className="border-b border-gray-50 dark:border-slate-800 hover:bg-gray-50 dark:hover:bg-slate-700/30">
              <td className="py-1.5 px-3 font-mono text-gray-900 dark:text-slate-100">{col.field}</td>
              <td className="py-1.5 px-3 text-gray-500 dark:text-slate-400 font-mono text-xs">{col.type}</td>
              <td className="py-1.5 px-3 text-center">
                {col.null === 'YES' ? (
                  <span className="text-green-500 text-xs">YES</span>
                ) : (
                  <span className="text-red-400 text-xs">NO</span>
                )}
              </td>
              <td className="py-1.5 px-3 text-center">
                {col.key && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    col.key === 'PRI'
                      ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                      : 'bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400'
                  }`}>
                    {col.key}
                  </span>
                )}
              </td>
              <td className="py-1.5 px-3 text-gray-400 dark:text-slate-500 text-xs font-mono">
                {col.default ?? <span className="italic">NULL</span>}
              </td>
              <td className="py-1.5 px-3 text-gray-400 dark:text-slate-500 text-xs">{col.extra}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Data table viewer */
function DataViewer({
  rows, columns, total, page, pageSize, onPageChange, loading, elapsedMs,
}: {
  rows: Record<string, unknown>[]
  columns: string[]
  total: number
  page: number
  pageSize: number
  onPageChange: (p: number) => void
  loading: boolean
  elapsedMs: number
}) {
  const { t } = useI18n()
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-400">
        <Loader2 size={20} className="animate-spin mr-2" />
        <span className="text-sm">{t('common.loading')}</span>
      </div>
    )
  }

  return (
    <div>
      {/* Stats bar */}
      <div className="flex items-center justify-between mb-3 text-xs text-gray-400 dark:text-slate-500">
        <span>{t('dbm.totalRows', { count: total })} · {elapsedMs}ms</span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            ←
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            className="px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            →
          </button>
        </div>
      </div>

      {/* Data table */}
      {columns.length === 0 ? (
        <div className="text-center py-8 text-gray-400 text-sm">{t('dbm.noData')}</div>
      ) : (
        <div className="overflow-x-auto border border-gray-200 dark:border-slate-700 rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 dark:bg-slate-800/50">
                <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 w-8">#</th>
                {columns.map((col) => (
                  <th key={col} className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 font-mono whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-slate-800">
              {rows.map((row, idx) => (
                <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-slate-700/30">
                  <td className="py-1.5 px-3 text-gray-400 text-xs">{(page - 1) * pageSize + idx + 1}</td>
                  {columns.map((col) => {
                    const val = row[col]
                    return (
                      <td key={col} className="py-1.5 px-3 text-gray-700 dark:text-slate-300 font-mono text-xs max-w-xs truncate whitespace-nowrap">
                        {val === null
                          ? <span className="text-gray-300 dark:text-slate-600 italic">NULL</span>
                          : val === undefined
                          ? ''
                          : String(val)
                        }
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/** SQL Console panel */
function SQLConsole({
  hostname, port, database, username, onExecute, result, loading,
}: {
  hostname: string
  port: number
  database: string
  username: string
  onExecute: (sql: string) => void
  result: QueryResult | null
  loading: boolean
}) {
  const { t } = useI18n()
  const [sql, setSql] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleExecute = useCallback(() => {
    if (sql.trim()) {
      onExecute(sql.trim())
    }
  }, [sql, onExecute])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        handleExecute()
      }
    },
    [handleExecute]
  )

  return (
    <div className="space-y-3">
      {/* SQL Editor */}
      <div className="border border-gray-200 dark:border-slate-700 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-slate-400">
            <Terminal size={14} />
            <span className="font-mono">{hostname}:{port}</span>
            <span className="text-gray-300 dark:text-slate-600">/</span>
            <span className="font-mono">{database}</span>
            <span className="text-gray-300 dark:text-slate-600">|</span>
            <span className="font-mono text-blue-500">{username}</span>
          </div>
          <button
            onClick={handleExecute}
            disabled={loading || !sql.trim()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 dark:disabled:bg-blue-800 text-white text-xs rounded font-medium transition-colors"
          >
            {loading ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Play size={12} />
            )}
            {t('dbm.run')}
          </button>
        </div>
        <textarea
          ref={textareaRef}
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('dbm.sqlPlaceholder')}
          className="w-full bg-transparent px-4 py-3 text-sm font-mono text-gray-900 dark:text-slate-100 placeholder-gray-400 dark:placeholder-slate-500 outline-none resize-none"
          rows={6}
          style={{ minHeight: '120px' }}
        />
        <div className="px-3 py-1.5 bg-gray-50 dark:bg-slate-800/50 border-t border-gray-200 dark:border-slate-700 text-[10px] text-gray-400">
          Ctrl+Enter {t('dbm.toExecute')}
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="border border-gray-200 dark:border-slate-700 rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
            <div className="flex items-center gap-2 text-xs">
              {result.type === 'error' ? (
                <XCircle size={14} className="text-red-500" />
              ) : (
                <CheckCircle size={14} className="text-green-500" />
              )}
              <span className={`font-medium ${
                result.type === 'error' ? 'text-red-600 dark:text-red-400' : 'text-gray-600 dark:text-slate-400'
              }`}>
                {result.type === 'select'
                  ? t('dbm.resultSelect', { rows: result.row_count, ms: result.elapsed_ms })
                  : result.type === 'modify'
                  ? t('dbm.resultModify', { rows: result.affected_rows ?? 0, ms: result.elapsed_ms })
                  : t('dbm.resultError')
                }
              </span>
            </div>
            <span className="text-xs text-gray-400">{result.elapsed_ms}ms</span>
          </div>

          {result.type === 'error' && result.error && (
            <div className="px-4 py-3 text-sm text-red-600 dark:text-red-400 font-mono whitespace-pre-wrap">
              {result.error}
            </div>
          )}

          {result.type === 'select' && result.columns && result.rows && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
                    {result.columns.map((col) => (
                      <th key={col} className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-slate-400 font-mono whitespace-nowrap">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-slate-800">
                  {result.rows.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50 dark:hover:bg-slate-700/30">
                      {result.columns!.map((col) => {
                        const val = row[col]
                        return (
                          <td key={col} className="py-1.5 px-3 text-gray-700 dark:text-slate-300 font-mono text-xs max-w-sm truncate whitespace-nowrap">
                            {val === null
                              ? <span className="text-gray-300 dark:text-slate-600 italic">NULL</span>
                              : val === undefined ? '' : String(val)
                            }
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.type === 'modify' && (
            <div className="px-4 py-3 text-sm text-green-600 dark:text-green-400">
              {t('dbm.affectedRows', { count: result.affected_rows ?? 0 })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Page Component ──

export default function DatabaseManagerPage() {
  const { t } = useI18n()
  const selectedId = useServerStore((s) => s.selectedId)

  // Backend servers
  const [backends, setBackends] = useState<BackendServer[]>([])
  const [backendsLoading, setBackendsLoading] = useState(false)
  const [selectedBackend, setSelectedBackend] = useState<BackendServer | null>(null)
  const [selectedUsername, setSelectedUsername] = useState('')

  // Connection test
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ id: string; result: ConnectionTestResult } | null>(null)

  // Database browsing
  const [databases, setDatabases] = useState<string[]>([])
  const [databasesLoading, setDatabasesLoading] = useState(false)
  const [selectedDb, setSelectedDb] = useState<string | null>(null)

  // Table browsing
  const [tables, setTables] = useState<string[]>([])
  const [tablesLoading, setTablesLoading] = useState(false)
  const [selectedTable, setSelectedTable] = useState<string | null>(null)

  // Schema
  const [schema, setSchema] = useState<ColumnSchema[]>([])
  const [schemaLoading, setSchemaLoading] = useState(false)

  // Data viewing
  const [tableRows, setTableRows] = useState<Record<string, unknown>[]>([])
  const [tableColumns, setTableColumns] = useState<string[]>([])
  const [tableTotal, setTableTotal] = useState(0)
  const [tablePage, setTablePage] = useState(1)
  const [tableLoading, setTableLoading] = useState(false)
  const [tableElapsed, setTableElapsed] = useState(0)

  // SQL console
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null)
  const [queryLoading, setQueryLoading] = useState(false)

  // Active tab in content area
  const [activeTab, setActiveTab] = useState<'browse' | 'sql'>('browse')

  // Load backends
  const loadBackends = useCallback(async () => {
    if (!selectedId) return
    setBackendsLoading(true)
    try {
      const resp = await dbManagerApi.listBackends(selectedId)
      setBackends(resp.data || [])
    } catch (err) {
      console.error('Failed to load backends:', err)
      setBackends([])
    } finally {
      setBackendsLoading(false)
    }
  }, [selectedId])

  useEffect(() => {
    loadBackends()
  }, [loadBackends])

  // Auto-select first available user when backend changes
  useEffect(() => {
    if (selectedBackend?.available_users?.length) {
      const firstUser = selectedBackend.available_users[0].username
      if (firstUser && firstUser !== selectedUsername) {
        setSelectedUsername(firstUser)
      }
    } else if (selectedBackend) {
      setSelectedUsername('')
    }
  }, [selectedBackend])

  // Select a backend
  const handleSelectBackend = useCallback(async (be: BackendServer) => {
    setSelectedBackend(be)
    setSelectedDb(null)
    setSelectedTable(null)
    setSchema([])
    setTableRows([])
    setQueryResult(null)

    // Auto-select first user
    if (be.available_users?.length) {
      setSelectedUsername(be.available_users[0].username)
    }

    // Load databases
    if (be.available_users?.length) {
      const username = be.available_users[0].username
      setDatabasesLoading(true)
      try {
        const resp = await dbManagerApi.listDatabases(selectedId!, be.hostname, be.port, username)
        setDatabases(resp.data.databases || [])
      } catch (err) {
        console.error('Failed to load databases:', err)
        setDatabases([])
      } finally {
        setDatabasesLoading(false)
      }
    }
  }, [selectedId])

  // Test connection
  const handleTestConnection = useCallback(async (be: BackendServer) => {
    if (!be.available_users?.length) return
    const username = selectedBackend?.id === be.id ? selectedUsername : be.available_users[0].username
    setTesting(be.id)
    setTestResult(null)
    try {
      const resp = await dbManagerApi.testConnection(selectedId!, be.hostname, be.port, username)
      setTestResult({ id: be.id, result: resp.data })
    } catch (err) {
      setTestResult({
        id: be.id,
        result: { success: false, error: 'Request failed', elapsed_ms: 0 },
      })
    } finally {
      setTesting(null)
    }
  }, [selectedId, selectedBackend, selectedUsername])

  // Select database
  const handleSelectDb = useCallback(async (db: string) => {
    if (!selectedBackend || !selectedUsername) return
    setSelectedDb(db)
    setSelectedTable(null)
    setSchema([])
    setTableRows([])

    setTablesLoading(true)
    try {
      const resp = await dbManagerApi.listTables(selectedId!, selectedBackend.hostname, selectedBackend.port, db, selectedUsername)
      setTables(resp.data.tables || [])
    } catch (err) {
      console.error('Failed to load tables:', err)
      setTables([])
    } finally {
      setTablesLoading(false)
    }
  }, [selectedId, selectedBackend, selectedUsername])

  // Select table
  const handleSelectTable = useCallback(async (table: string) => {
    if (!selectedBackend || !selectedDb || !selectedUsername) return
    setSelectedTable(table)

    // Load schema
    setSchemaLoading(true)
    try {
      const schemaResp = await dbManagerApi.getTableSchema(
        selectedId!, selectedBackend.hostname, selectedBackend.port, selectedDb, table, selectedUsername
      )
      setSchema(schemaResp.data.columns || [])
    } catch (err) {
      console.error('Failed to load schema:', err)
      setSchema([])
    } finally {
      setSchemaLoading(false)
    }

    // Load data
    await loadTableData(table, 1)
  }, [selectedId, selectedBackend, selectedDb, selectedUsername])

  // Load table data
  const loadTableData = useCallback(async (table: string, page: number) => {
    if (!selectedBackend || !selectedDb || !selectedUsername) return
    setTableLoading(true)
    setTablePage(page)
    try {
      const resp = await dbManagerApi.getTableData(
        selectedId!, selectedBackend.hostname, selectedBackend.port,
        selectedDb, table, selectedUsername, page,
      )
      setTableRows(resp.data.rows || [])
      setTableColumns(resp.data.columns || [])
      setTableTotal(resp.data.total)
      setTableElapsed(resp.data.elapsed_ms)
    } catch (err) {
      console.error('Failed to load table data:', err)
      setTableRows([])
      setTableColumns([])
    } finally {
      setTableLoading(false)
    }
  }, [selectedId, selectedBackend, selectedDb, selectedUsername])

  // Execute SQL
  const handleExecuteSQL = useCallback(async (sql: string) => {
    if (!selectedBackend || !selectedUsername) return
    setQueryLoading(true)
    setQueryResult(null)
    try {
      const resp = await dbManagerApi.executeSQL(selectedId!, {
        sql,
        database: selectedDb || undefined,
        hostname: selectedBackend.hostname,
        port: selectedBackend.port,
        username: selectedUsername,
        limit: 500,
      })
      setQueryResult(resp.data)
    } catch (err: any) {
      setQueryResult({
        type: 'error',
        row_count: 0,
        elapsed_ms: 0,
        error: err?.response?.data?.detail || err?.message || 'Unknown error',
      })
    } finally {
      setQueryLoading(false)
    }
  }, [selectedId, selectedBackend, selectedDb, selectedUsername])

  // Refresh all after data modification
  const handleAfterModify = useCallback(() => {
    if (selectedTable && selectedBackend && selectedDb) {
      loadTableData(selectedTable, tablePage)
    } else if (selectedBackend && selectedDb) {
      handleSelectDb(selectedDb)
    }
  }, [selectedTable, selectedBackend, selectedDb, tablePage, loadTableData, handleSelectDb])

  // ── Render ──

  if (!selectedId) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <AlertTriangle size={48} className="mx-auto mb-4 text-amber-500" />
          <p className="text-gray-500 dark:text-slate-400">{t('wizard.noServerSelected')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100 flex items-center gap-2">
            <Database size={24} className="text-blue-500" />
            {t('dbm.title')}
          </h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">{t('dbm.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadBackends}
            disabled={backendsLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
          >
            <RefreshCw size={14} className={backendsLoading ? 'animate-spin' : ''} />
            {t('common.refresh')}
          </button>
        </div>
      </div>

      {/* Main layout: sidebar + content */}
      <div className="flex gap-4 min-h-[600px]">
        {/* Left sidebar */}
        <div className="w-72 shrink-0 space-y-3">
          {/* Backend server list */}
          <BackendList
            backends={backends}
            selectedId={selectedBackend?.id ?? null}
            selectedUsername={selectedUsername}
            onSelect={handleSelectBackend}
            onTest={handleTestConnection}
            testing={testing}
            testResult={testResult}
            onRefresh={loadBackends}
            loading={backendsLoading}
          />

          {/* Database list (shown after backend selected) */}
          {selectedBackend && (
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700">
              <div className="px-4 py-3 border-b border-gray-200 dark:border-slate-700">
                <h3 className="font-medium text-gray-900 dark:text-slate-100 text-sm flex items-center gap-2">
                  <HardDrive size={14} className="text-purple-500" />
                  {t('dbm.databases')}
                </h3>
              </div>
              <div className="p-2">
                <DatabaseList
                  databases={databases}
                  selectedDb={selectedDb}
                  onSelect={handleSelectDb}
                  loading={databasesLoading}
                />
              </div>
            </div>
          )}

          {/* Table list (shown after database selected) */}
          {selectedDb && (
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700">
              <div className="px-4 py-3 border-b border-gray-200 dark:border-slate-700">
                <h3 className="font-medium text-gray-900 dark:text-slate-100 text-sm flex items-center gap-2">
                  <Table size={14} className="text-green-500" />
                  {t('dbm.tables')}
                </h3>
              </div>
              <div className="p-2">
                <TableList
                  tables={tables}
                  selectedTable={selectedTable}
                  onSelect={handleSelectTable}
                  loading={tablesLoading}
                />
              </div>
            </div>
          )}
        </div>

        {/* Main content area */}
        <div className="flex-1 min-w-0">
          {!selectedBackend ? (
            <div className="flex flex-col items-center justify-center h-full py-20 bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700">
              <Database size={48} className="mb-4 text-gray-300 dark:text-slate-600" />
              <p className="text-gray-500 dark:text-slate-400 text-sm">{t('dbm.selectBackend')}</p>
              <p className="text-gray-400 dark:text-slate-500 text-xs mt-1">{t('dbm.selectBackendHint')}</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Breadcrumb */}
              <div className="flex items-center gap-2 text-sm bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 px-4 py-2.5">
                <Server size={14} className="text-blue-500" />
                <span className="font-medium text-gray-700 dark:text-slate-300">
                  {selectedBackend.hostname}:{selectedBackend.port}
                </span>
                <span className="text-gray-300 dark:text-slate-600">·</span>
                <span className="text-xs text-gray-400">
                  HG: {selectedBackend.hostgroup_id} · {selectedBackend.status}
                </span>

                {/* User selector */}
                {selectedBackend.available_users.length > 0 && (
                  <>
                    <span className="text-gray-300 dark:text-slate-600">·</span>
                    <select
                      value={selectedUsername}
                      onChange={(e) => {
                        const newUser = e.target.value
                        setSelectedUsername(newUser)
                        // Reload databases with new user
                        if (selectedBackend && newUser) {
                          setSelectedDb(null)
                          setSelectedTable(null)
                          setSchema([])
                          setTableRows([])
                          setDatabasesLoading(true)
                          dbManagerApi.listDatabases(selectedId!, selectedBackend.hostname, selectedBackend.port, newUser)
                            .then(resp => setDatabases(resp.data.databases || []))
                            .catch(() => setDatabases([]))
                            .finally(() => setDatabasesLoading(false))
                        }
                      }}
                      className="text-xs bg-gray-50 dark:bg-slate-700 border border-gray-200 dark:border-slate-600 rounded px-2 py-0.5 text-gray-700 dark:text-slate-300 outline-none focus:border-blue-400"
                    >
                      {selectedBackend.available_users.map((u) => (
                        <option key={u.username} value={u.username}>
                          {u.username}
                        </option>
                      ))}
                    </select>
                  </>
                )}
                {selectedBackend.available_users.length === 0 && (
                  <>
                    <span className="text-gray-300 dark:text-slate-600">·</span>
                    <span className="text-xs text-red-400">{t('dbm.noBackendUser')}</span>
                  </>
                )}
                {selectedDb && (
                  <>
                    <ChevronRight size={14} className="text-gray-300 dark:text-slate-600" />
                    <Database size={14} className="text-purple-500" />
                    <span className="text-gray-700 dark:text-slate-300">{selectedDb}</span>
                  </>
                )}
                {selectedTable && (
                  <>
                    <ChevronRight size={14} className="text-gray-300 dark:text-slate-600" />
                    <Table size={14} className="text-green-500" />
                    <span className="text-gray-700 dark:text-slate-300">{selectedTable}</span>
                  </>
                )}
              </div>

              {/* Tabs */}
              <div className="flex gap-1 bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 p-1">
                <button
                  onClick={() => setActiveTab('browse')}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded text-sm font-medium transition-colors ${
                    activeTab === 'browse'
                      ? 'bg-blue-500 text-white shadow-sm'
                      : 'text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                  }`}
                >
                  <Table size={14} />
                  {t('dbm.browse')}
                </button>
                <button
                  onClick={() => setActiveTab('sql')}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded text-sm font-medium transition-colors ${
                    activeTab === 'sql'
                      ? 'bg-blue-500 text-white shadow-sm'
                      : 'text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700'
                  }`}
                >
                  <Terminal size={14} />
                  {t('dbm.sqlConsole')}
                </button>
              </div>

              {/* Browse tab content */}
              {activeTab === 'browse' && (
                <div className="space-y-4">
                  {/* Schema panel */}
                  {selectedTable && (
                    <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700">
                      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-slate-700">
                        <Columns size={14} className="text-blue-500" />
                        <h3 className="font-medium text-sm text-gray-900 dark:text-slate-100">
                          {t('dbm.schema')} — {selectedTable}
                        </h3>
                        {schemaLoading && <Loader2 size={14} className="animate-spin text-gray-400 ml-auto" />}
                      </div>
                      <div className="p-2">
                        <SchemaPanel columns={schema} loading={schemaLoading} />
                      </div>
                    </div>
                  )}

                  {/* Data viewer */}
                  {selectedTable && (
                    <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700">
                      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-slate-700">
                        <FileText size={14} className="text-green-500" />
                        <h3 className="font-medium text-sm text-gray-900 dark:text-slate-100">
                          {t('dbm.data')} — {selectedTable}
                        </h3>
                        {tableLoading && <Loader2 size={14} className="animate-spin text-gray-400 ml-auto" />}
                      </div>
                      <div className="p-3">
                        <DataViewer
                          rows={tableRows}
                          columns={tableColumns}
                          total={tableTotal}
                          page={tablePage}
                          pageSize={50}
                          onPageChange={(p) => loadTableData(selectedTable, p)}
                          loading={tableLoading}
                          elapsedMs={tableElapsed}
                        />
                      </div>
                    </div>
                  )}

                  {!selectedTable && selectedDb && (
                    <div className="flex flex-col items-center justify-center py-16 bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700">
                      <Table size={40} className="mb-3 text-gray-300 dark:text-slate-600" />
                      <p className="text-gray-500 dark:text-slate-400 text-sm">{t('dbm.selectTable')}</p>
                    </div>
                  )}

                  {!selectedDb && (
                    <div className="flex flex-col items-center justify-center py-16 bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700">
                      <HardDrive size={40} className="mb-3 text-gray-300 dark:text-slate-600" />
                      <p className="text-gray-500 dark:text-slate-400 text-sm">{t('dbm.selectDatabase')}</p>
                    </div>
                  )}
                </div>
              )}

              {/* SQL Console tab */}
              {activeTab === 'sql' && (
                <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-slate-700 p-4">
                  <SQLConsole
                    hostname={selectedBackend.hostname}
                    port={selectedBackend.port}
                    database={selectedDb || 'mysql'}
                    username={selectedUsername}
                    onExecute={(sql) => {
                      handleExecuteSQL(sql).then(() => {
                        // If the SQL was a modify, refresh browse data
                        const sqlUpper = sql.trim().toUpperCase()
                        if (
                          sqlUpper.startsWith('INSERT') ||
                          sqlUpper.startsWith('UPDATE') ||
                          sqlUpper.startsWith('DELETE') ||
                          sqlUpper.startsWith('ALTER') ||
                          sqlUpper.startsWith('CREATE') ||
                          sqlUpper.startsWith('DROP') ||
                          sqlUpper.startsWith('TRUNCATE')
                        ) {
                          handleAfterModify()
                        }
                      })
                    }}
                    result={queryResult}
                    loading={queryLoading}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
