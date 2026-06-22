import { useState, useMemo, useCallback, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useNavigate } from 'react-router-dom'
import { wizardApi } from '../api/client'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import { Wand2, ChevronRight, Play, Eye, AlertCircle, Loader2 } from 'lucide-react'

const CATEGORY_LABELS: Record<string, string> = {
  backend_servers: 'wizard.category.backend_servers',
  backend_users: 'wizard.category.backend_users',
  query_routing: 'wizard.category.query_routing',
  replication_topology: 'wizard.category.replication_topology',
  system_config: 'wizard.category.system_config',
  firewall_security: 'wizard.category.firewall_security',
  operations: 'wizard.category.operations',
  monitoring: 'wizard.category.monitoring',
}

/** Translate wizard name/description/guide using i18n, falling back to the backend value. */
function translateWizardText(t: (key: string, params?: Record<string, string | number>) => string, wizardId: string, field: 'name' | 'desc' | 'guide', fallback: string): string {
  const key = `wizard.${wizardId}.${field}`
  const translated = t(key)
  // If the translation returns the key itself, it's missing — use fallback
  return translated === key ? fallback : translated
}

/** Translate a field label using i18n key wizard.field.<name>, falling back to the backend label. */
function translateFieldLabel(t: (key: string, params?: Record<string, string | number>) => string, fieldName: string, fallback: string): string {
  const key = `wizard.field.${fieldName}`
  const translated = t(key)
  return translated === key ? fallback : translated
}

/** Translate a select/radio option label using i18n key wizard.option.<label>, falling back to the original label. */
function translateOptionLabel(t: (key: string, params?: Record<string, string | number>) => string, label: string): string {
  const key = `wizard.option.${label}`
  const translated = t(key)
  return translated === key ? label : translated
}

/** Translate a field help text using i18n key wizard.help.<name>, falling back to the backend help text. */
function translateFieldHelp(t: (key: string, params?: Record<string, string | number>) => string, fieldName: string, fallback: string): string {
  const key = `wizard.help.${fieldName}`
  const translated = t(key)
  return translated === key ? fallback : translated
}

export default function WizardsPage() {
  const { wizardId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const selectedId = useServerStore((s) => s.selectedId)
  const { t } = useI18n()
  const [formValues, setFormValues] = useState<Record<string, any>>({})
  const [previewSql, setPreviewSql] = useState<string[] | null>(null)
  const [executeResult, setExecuteResult] = useState<any>(null)
  const [autoApply, setAutoApply] = useState(true)
  const [autoSave, setAutoSave] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ── Wizard definitions (must be declared BEFORE the lookup useEffect) ──
  const { data, isLoading } = useQuery({
    queryKey: ['wizards', 'definitions'],
    queryFn: () => wizardApi.getDefinitions(),
  })

  const wizards = useMemo(() => data?.data?.wizards || [], [data])

  // ── Dynamic lookup state ────────────────────────────────────
  const [lookupOptions, setLookupOptions] = useState<Record<string, any[]>>({})
  const [lookupLoading, setLookupLoading] = useState<Record<string, boolean>>({})

  // Fetch lookup options when wizard definitions load, wizardId or selectedId changes
  useEffect(() => {
    if (!wizardId || !selectedId || wizards.length === 0) return
    const wizard = wizards.find((w: any) => w.id === wizardId)
    if (!wizard) return

    const lookupFields = (wizard.fields || []).filter((f: any) => f.type === 'lookup')
    if (lookupFields.length === 0) return

    const fetchOptions = async () => {
      const newLoading: Record<string, boolean> = {}
      lookupFields.forEach((f: any) => { newLoading[f.name] = true })
      setLookupLoading(newLoading)

      const newOptions: Record<string, any[]> = {}
      await Promise.all(
        lookupFields.map(async (f: any) => {
          try {
            const resp = await wizardApi.lookupOptions(selectedId!, wizardId, f.name)
            newOptions[f.name] = resp.data?.options || []
          } catch {
            newOptions[f.name] = []
          } finally {
            setLookupLoading(prev => ({ ...prev, [f.name]: false }))
          }
        })
      )
      setLookupOptions(prev => ({ ...prev, ...newOptions }))
    }
    fetchOptions()
  }, [wizardId, selectedId, wizards])
  const activeWizard = useMemo(
    () => wizardId ? wizards.find((w: any) => w.id === wizardId) : null,
    [wizardId, wizards]
  )

  const previewMutation = useMutation({
    mutationFn: (fields: Record<string, unknown>) =>
      wizardApi.preview(wizardId!, selectedId || 'preview', fields),
    onSuccess: (resp) => {
      setPreviewSql(resp.data?.sql_preview || [])
      setError(null)
    },
    onError: (err: any) => {
      console.error('[Wizard preview]', err.response?.data?.detail || err.message)
      setError(t('wizard.previewFailed'))
      setPreviewSql(null)
    },
  })

  const executeMutation = useMutation({
    mutationFn: (fields: Record<string, unknown>) =>
      wizardApi.execute(wizardId!, selectedId!, fields, { auto_apply: autoApply, auto_save: autoSave }),
    onSuccess: (resp) => {
      setExecuteResult(resp.data)
      queryClient.invalidateQueries({ queryKey: ['sync'] })
      setError(null)
    },
    onError: (err: any) => {
      console.error('[Wizard execute]', err.response?.data?.detail || err.message)
      setError(t('wizard.executeFailed'))
      setExecuteResult(null)
    },
  })

  // useMemo: group wizards by category only when wizards data changes
  const categories = useMemo(() => {
    const cats: Record<string, any[]> = {}
    wizards.forEach((w: any) => {
      if (!cats[w.category]) cats[w.category] = []
      cats[w.category].push(w)
    })
    return cats
  }, [wizards])

  // useCallback: handler for form field changes - stable reference across renders
  const handleFieldChange = useCallback((name: string, value: any) => {
    setFormValues((prev) => ({ ...prev, [name]: value }))
  }, [])

  // useCallback: build payload from form values and field definitions
  const buildFieldsPayload = useCallback(() => {
    const fieldList: any[] = activeWizard?.fields || []
    const payload: Record<string, any> = {}
    fieldList.forEach((f) => {
      // Skip lookup-type fields — they are UI helpers only, not part of the actual payload
      if (f.type === 'lookup') return
      payload[f.name] = formValues[f.name] !== undefined ? formValues[f.name] : f.default
    })
    // Special-case the JSON textarea wizards (variables field)
    if (payload.variables && typeof payload.variables === 'string') {
      try {
        payload.variables = JSON.parse(payload.variables)
      } catch {
        // leave as string; validation will surface the error downstream
      }
    }
    return payload
  }, [activeWizard, formValues])

  // useCallback: navigate back to wizard list, resetting all state
  const handleBack = useCallback(() => {
    setFormValues({})
    setPreviewSql(null)
    setExecuteResult(null)
    setError(null)
    setLookupOptions({})
    setLookupLoading({})
    navigate('/wizards')
  }, [navigate])

  // useCallback: select a wizard card
  const handleSelectWizard = useCallback((id: string) => {
    setFormValues({})
    setPreviewSql(null)
    setExecuteResult(null)
    setError(null)
    setLookupOptions({})
    setLookupLoading({})
    navigate(`/wizards/${id}`)
  }, [navigate])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  // ── Detail view: render the form for the selected wizard ──
  if (activeWizard) {
    const isPlanned = activeWizard.status !== 'implemented'
    const fieldList: any[] = activeWizard.fields || []

    return (
      <div>
        <button
          onClick={handleBack}
          className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 mb-4"
        >
          {t('wizard.back')}
        </button>

        <div className="flex items-center gap-3 mb-2">
          <Wand2 size={28} className="text-blue-600 dark:text-blue-400" />
          <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">
            {translateWizardText(t, activeWizard.id, 'name', activeWizard.name)}
          </h2>
          <span className="text-sm text-gray-400 dark:text-slate-500">{activeWizard.id}</span>
        </div>
        <p className="text-gray-500 dark:text-slate-400 mb-6">
          {translateWizardText(t, activeWizard.id, 'desc', activeWizard.description)}
        </p>

        {isPlanned && (
          <div className="flex items-center gap-2 bg-gray-100 dark:bg-slate-700 border border-gray-300 dark:border-slate-600 rounded-lg p-4 text-gray-700 dark:text-slate-300 mb-6">
            <AlertCircle size={18} />
            <span>{t('wizard.plannedNotice')}</span>
          </div>
        )}

        {!selectedId && !isPlanned && (
          <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 text-amber-700 dark:text-amber-400 mb-6">
            {t('wizard.noServerSelected')}
          </div>
        )}

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-3 text-red-700 dark:text-red-400 text-sm mb-4">
            {error}
          </div>
        )}

        {/* Beginner-friendly guide */}
        {(() => {
          const guideText = translateWizardText(t, activeWizard.id, 'guide', activeWizard.guide || '')
          if (guideText) {
            return (
              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-4 mb-4">
                <div className="flex items-start gap-2">
                  <span className="text-blue-500 dark:text-blue-400 text-lg mt-0.5">💡</span>
                  <div>
                    <p className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-1">{t('wizard.guideTitle')}</p>
                    <div className="text-sm text-blue-700 dark:text-blue-400 whitespace-pre-line leading-relaxed">
                      {guideText}
                    </div>
                  </div>
                </div>
              </div>
            )
          }
          return null
        })()}

        {/* Form */}
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5 mb-4">
          {fieldList.length === 0 ? (
            <p className="text-sm text-gray-400 dark:text-slate-500">{t('wizard.noFields')}</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {fieldList.map((f) => (
                <div key={f.name}>
                  <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                    {translateFieldLabel(t, f.name, f.label)}
                    {f.required && <span className="text-red-500"> *</span>}
                  </label>
                  {f.type === 'textarea' ? (
                    <textarea
                      value={formValues[f.name] !== undefined ? formValues[f.name] : f.default ?? ''}
                      onChange={(e) => handleFieldChange(f.name, e.target.value)}
                      placeholder={f.placeholder}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm font-mono outline-none focus:ring-2 focus:ring-blue-500 min-h-[80px] bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
                    />
                  ) : f.type === 'lookup' ? (
                    <div className="flex items-center gap-2">
                      {lookupLoading[f.name] && (
                        <Loader2 size={16} className="animate-spin text-blue-500 flex-shrink-0" />
                      )}
                      <select
                        value={formValues[f.name] || ''}
                        onChange={(e) => {
                          const val = e.target.value
                          handleFieldChange(f.name, val)
                          // Auto-fill linked fields when an option is selected
                          if (val && f.lookup?.linked_fields) {
                            const selectedOption = (lookupOptions[f.name] || []).find(
                              (opt: any) => opt.value === val
                            )
                            if (selectedOption?.fields) {
                              Object.entries(selectedOption.fields).forEach(([fieldName, fieldValue]) => {
                                handleFieldChange(fieldName, fieldValue)
                              })
                            }
                          }
                        }}
                        className="flex-1 px-3 py-2 border border-blue-300 dark:border-blue-600 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-slate-100"
                      >
                        <option value="">{t('wizard.selectPlaceholder') || '-- Select to auto-fill --'}</option>
                        {(lookupOptions[f.name] || []).map((opt: any) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    </div>
                  ) : f.type === 'select' ? (
                    <select
                      value={formValues[f.name] !== undefined ? formValues[f.name] : f.default ?? ''}
                      onChange={(e) => handleFieldChange(f.name, e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
                    >
                      {f.options?.map((opt: any) => {
                        const value = typeof opt === 'string' ? opt : opt.value
                        const rawLabel = typeof opt === 'string' ? opt : opt.label
                        const label = translateOptionLabel(t, rawLabel)
                        return <option key={value} value={value}>{label}</option>
                      })}
                    </select>
                  ) : f.type === 'radio' ? (
                    <div className="flex gap-3">
                      {(f.options || []).map((opt: string) => (
                        <label key={opt} className="flex items-center gap-1 text-sm">
                          <input
                            type="radio"
                            name={f.name}
                            checked={(formValues[f.name] !== undefined ? formValues[f.name] : f.default) === opt}
                            onChange={() => handleFieldChange(f.name, opt)}
                          />
                          {translateOptionLabel(t, opt)}
                        </label>
                      ))}
                    </div>
                  ) : f.type === 'toggle' || f.type === 'checkbox' ? (
                    <input
                      type="checkbox"
                      checked={Boolean(formValues[f.name] !== undefined ? formValues[f.name] : f.default)}
                      onChange={(e) => handleFieldChange(f.name, e.target.checked ? 1 : 0)}
                      className="h-4 w-4"
                    />
                  ) : (
                    <input
                      type={f.type === 'password' ? 'password' : f.type === 'number' ? 'number' : 'text'}
                      value={formValues[f.name] !== undefined ? formValues[f.name] : f.default ?? ''}
                      placeholder={f.placeholder}
                      min={f.min}
                      max={f.max}
                      onChange={(e) => handleFieldChange(f.name, f.type === 'number' ? Number(e.target.value) : e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
                    />
                  )}
                  {f.help && <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">{translateFieldHelp(t, f.name, f.help)}</p>}
                </div>
              ))}
            </div>
          )}

          {activeWizard.auto_apply_module && (
            <div className="flex gap-4 mt-4 mb-2">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={autoApply}
                  onChange={(e) => setAutoApply(e.target.checked)}
                  className="h-4 w-4"
                />
                {t('wizard.autoApply')}
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={autoSave}
                  onChange={(e) => setAutoSave(e.target.checked)}
                  className="h-4 w-4"
                />
                {t('wizard.autoSave')}
              </label>
            </div>
          )}

          <div className="flex gap-2 mt-5">
            <button
              onClick={() => previewMutation.mutate(buildFieldsPayload())}
              disabled={isPlanned || previewMutation.isPending}
              className="flex items-center gap-2 bg-gray-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-700 disabled:opacity-50"
            >
              <Eye size={16} />
              {previewMutation.isPending ? t('wizard.previewing') : t('wizard.previewSql')}
            </button>
            <button
              onClick={() => executeMutation.mutate(buildFieldsPayload())}
              disabled={isPlanned || executeMutation.isPending || !selectedId}
              className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              <Play size={16} />
              {executeMutation.isPending ? t('wizard.executing') : t('wizard.execute')}
            </button>
          </div>
        </div>

        {/* SQL Preview */}
        {previewSql && (
          <div className="bg-gray-900 rounded-xl border border-gray-700 p-4 mb-4">
            <h3 className="text-sm font-semibold text-gray-200 mb-2">{t('wizard.sqlPreview')}</h3>
            <pre className="text-xs text-green-300 whitespace-pre-wrap font-mono">
              {previewSql.join(';\n')}{previewSql.length > 0 ? ';' : ''}
            </pre>
          </div>
        )}

        {/* Execute result */}
        {executeResult && (
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-2">{t('wizard.result')}</h3>
            <p className={`text-sm mb-2 ${executeResult.ok ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
              {executeResult.ok
                ? t('wizard.resultSuccess', { count: executeResult.executed_sql?.length || 0 })
                : t('common.failed')}
            </p>
            {executeResult.errors && executeResult.errors.length > 0 && (
              <p className="text-xs text-red-600 dark:text-red-400">{t('wizard.executeFailed')} ({executeResult.errors.length})</p>
            )}
            {executeResult.results && (
              <ul className="text-xs text-gray-600 dark:text-slate-400 mt-2 space-y-1">
                {executeResult.results.map((r: any, i: number) => (
                  <li key={i} className={r.ok ? '' : 'text-red-600'}>
                    {r.ok ? '\u2713' : '\u2717'} <code className="font-mono">{r.sql}</code>
                    {!r.ok && r.error ? ` — ${t('common.failed')}` : ''}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    )
  }

  // ── List view ──
  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Wand2 size={28} className="text-blue-600 dark:text-blue-400" />
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('wizard.title')}</h2>
      </div>

      <p className="text-gray-500 dark:text-slate-400 mb-6">{t('wizard.subtitle')}</p>

      <div className="space-y-6">
        {Object.entries(categories).map(([category, items]) => (
          <div key={category}>
            <h3 className="text-lg font-semibold text-gray-700 dark:text-slate-300 mb-3">
              {t(CATEGORY_LABELS[category] || category)}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((wizard: any) => {
                const isPlanned = wizard.status !== 'implemented'
                return (
                  <button
                    key={wizard.id}
                    onClick={() => handleSelectWizard(wizard.id)}
                    className={`text-left p-4 rounded-xl border transition-all hover:shadow-md ${
                      wizardId === wizard.id
                        ? 'border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/30 shadow-md'
                        : 'border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-blue-300 dark:hover:border-blue-600'
                    } ${isPlanned ? 'opacity-70' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-gray-900 dark:text-slate-100 text-sm">{wizard.id}</span>
                      <ChevronRight size={16} className="text-gray-400 dark:text-slate-500" />
                    </div>
                    <p className="font-semibold text-gray-800 dark:text-slate-200">
                      {translateWizardText(t, wizard.id, 'name', wizard.name)}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
                      {translateWizardText(t, wizard.id, 'desc', wizard.description)}
                    </p>
                    <div className="flex items-center gap-2 mt-3 flex-wrap">
                      {wizard.fields?.length > 0 && (
                        <span className="text-xs bg-gray-100 dark:bg-slate-600 text-gray-600 dark:text-slate-300 px-2 py-0.5 rounded">
                          {t('wizard.fields', { count: wizard.fields.length })}
                        </span>
                      )}
                      {wizard.auto_apply_module && (
                        <span className="text-xs bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-400 px-2 py-0.5 rounded">
                          {t('wizard.autoApply')}
                        </span>
                      )}
                      {isPlanned ? (
                        <span className="text-xs bg-gray-200 dark:bg-slate-600 text-gray-500 dark:text-slate-400 px-2 py-0.5 rounded">
                          {t('wizard.planned')}
                        </span>
                      ) : (
                        <span className="text-xs bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 px-2 py-0.5 rounded">
                          {t('wizard.implemented')}
                        </span>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
