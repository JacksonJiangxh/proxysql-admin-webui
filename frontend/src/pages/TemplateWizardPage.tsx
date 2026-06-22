import { useState, useMemo, useCallback, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { templateApi } from '../api/client'
import { useServerStore } from '../stores/serverStore'
import { useI18n } from '../i18n'
import {
  Rocket, ChevronRight, ChevronLeft, Play, Eye, AlertCircle,
  Loader2, Plus, Trash2, SkipForward, CheckCircle2, XCircle,
  Server, Shield, Shuffle, Link, LayoutGrid, Zap,
} from 'lucide-react'

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

const ARCH_ICONS: Record<string, any> = {
  single_primary_replica: Server,
  multi_primary_replica: LayoutGrid,
  group_replication_single_primary: Shield,
  group_replication_multi_primary: Shuffle,
  galera_cluster: Link,
}

export default function TemplateWizardPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const selectedId = useServerStore((s) => s.selectedId)
  const { t } = useI18n()

  // ── State ──────────────────────────────
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [selectedMode, setSelectedMode] = useState<string | null>(null)
  const [currentStepIdx, setCurrentStepIdx] = useState(0)
  const [sharedValues, setSharedValues] = useState<Record<string, any>>({})
  const [stepValues, setStepValues] = useState<Record<string, Record<string, any>>>({})
  const [skippedSteps, setSkippedSteps] = useState<string[]>([])
  const [autoApply, setAutoApply] = useState(true)
  const [autoSave, setAutoSave] = useState(false)
  const [previewResult, setPreviewResult] = useState<any>(null)
  const [executeResult, setExecuteResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  // ── Data ───────────────────────────────
  const { data: templatesData } = useQuery({
    queryKey: ['templates'],
    queryFn: () => templateApi.getTemplates(),
  })
  const templates = useMemo(() => templatesData?.data?.templates || [], [templatesData])

  const { data: templateDetail } = useQuery({
    queryKey: ['template', selectedTemplate],
    queryFn: () => templateApi.getTemplate(selectedTemplate!),
    enabled: !!selectedTemplate,
  })

  const { data: stepsData } = useQuery({
    queryKey: ['template-steps', selectedTemplate, selectedMode],
    queryFn: () => templateApi.getSteps(selectedTemplate!, selectedMode!),
    enabled: !!selectedTemplate && !!selectedMode,
  })
  const steps = useMemo(() => stepsData?.data?.steps || [], [stepsData])
  const sharedFields = useMemo(() => templateDetail?.data?.shared_fields || [], [templateDetail])

  // ── Handlers ────────────────────────────
  const handleSharedChange = useCallback((name: string, value: any) => {
    setSharedValues((prev) => ({ ...prev, [name]: value }))
  }, [])

  const handleStepChange = useCallback((stepKey: string, name: string, value: any) => {
    setStepValues((prev) => ({
      ...prev,
      [stepKey]: { ...(prev[stepKey] || {}), [name]: value },
    }))
  }, [])

  const handleArrayAdd = useCallback((stepKey: string, fieldNames: string[], defaults: Record<string, any>) => {
    setStepValues((prev) => {
      const sv = prev[stepKey] || {}
      const updated = { ...sv }
      for (const fn of fieldNames) {
        const arrKey = `_array_${fn}`
        const arr = updated[arrKey] || []
        const defaultVal = defaults[fn] ?? ''
        updated[arrKey] = [...arr, defaultVal]
      }
      return { ...prev, [stepKey]: updated }
    })
  }, [])

  const handleArrayRemove = useCallback((stepKey: string, fieldNames: string[], index: number) => {
    setStepValues((prev) => {
      const sv = prev[stepKey] || {}
      const updated = { ...sv }
      for (const fn of fieldNames) {
        const arrKey = `_array_${fn}`
        const arr = updated[arrKey] || []
        updated[arrKey] = arr.filter((_: any, i: number) => i !== index)
      }
      return { ...prev, [stepKey]: updated }
    })
  }, [])

  const handleArrayItemChange = useCallback((stepKey: string, fieldName: string, index: number, value: any) => {
    setStepValues((prev) => {
      const sv = prev[stepKey] || {}
      const arrKey = `_array_${fieldName}`
      const arr = sv[arrKey] || []
      const updated = { ...sv, [arrKey]: arr.map((v: any, i: number) => i === index ? value : v) }
      return { ...prev, [stepKey]: updated }
    })
  }, [])

  const handleSkipStep = useCallback((stepKey: string) => {
    setSkippedSteps((prev) => [...prev, stepKey])
    // Move to next step
    const nextIdx = currentStepIdx + 1
    if (nextIdx < steps.length) {
      setCurrentStepIdx(nextIdx)
    }
  }, [currentStepIdx, steps.length])

  const handleBackStep = useCallback(() => {
    // If going back from a skipped step, un-skip it
    const currentStep = steps[currentStepIdx]
    if (currentStep && skippedSteps.includes(currentStep.step_key)) {
      setSkippedSteps((prev) => prev.filter(k => k !== currentStep.step_key))
    }
    if (currentStepIdx > 0) {
      setCurrentStepIdx(currentStepIdx - 1)
    }
  }, [currentStepIdx, steps, skippedSteps])

  const handleNextStep = useCallback(() => {
    const nextIdx = currentStepIdx + 1
    if (nextIdx < steps.length) {
      setCurrentStepIdx(nextIdx)
    }
  }, [currentStepIdx, steps.length])

  const handleBackToWizards = useCallback(() => {
    navigate('/wizards')
  }, [navigate])

  // Auto-populate shared defaults
  useEffect(() => {
    if (sharedFields.length > 0 && Object.keys(sharedValues).length === 0) {
      const defaults: Record<string, any> = {}
      sharedFields.forEach((f: any) => {
        if (f.default !== undefined && f.default !== null) {
          defaults[f.name] = f.default
        }
      })
      setSharedValues(defaults)
    }
  }, [sharedFields])

  // Auto-populate step defaults
  useEffect(() => {
    if (steps.length > 0) {
      const defaults: Record<string, Record<string, any>> = {}
      steps.forEach((step: any) => {
        const sv: Record<string, any> = {}
        step.fields?.forEach((f: any) => {
          if (f.default !== undefined && f.default !== null && !f.is_array) {
            if (!stepValues[step.step_key]?.[f.name]) {
              sv[f.name] = f.default
            }
          }
          // Initialize array fields with one row
          if (f.is_array) {
            const arrKey = `_array_${f.name}`
            if (!stepValues[step.step_key]?.[arrKey]) {
              sv[arrKey] = [f.default ?? '']
            }
          }
        })
        if (Object.keys(sv).length > 0) {
          defaults[step.step_key] = sv
        }
      })
      if (Object.keys(defaults).length > 0) {
        setStepValues((prev) => {
          const merged = { ...prev }
          for (const [sk, vals] of Object.entries(defaults)) {
            merged[sk] = { ...(prev[sk] || {}), ...vals }
          }
          return merged
        })
      }
    }
  }, [steps])

  // ── Preview mutation ────────────────────
  const previewMutation = useMutation({
    mutationFn: () =>
      templateApi.preview({
        template_id: selectedTemplate!,
        server_id: selectedId || 'preview',
        architecture_mode: selectedMode!,
        shared_values: sharedValues,
        step_values: stepValues,
        skipped_steps: skippedSteps,
      }),
    onSuccess: (resp) => {
      setPreviewResult(resp.data)
      setError(null)
    },
    onError: (err: any) => {
      console.error('[Template preview]', err.response?.data?.detail || err.message)
      setError(t('wizard.previewFailed'))
      setPreviewResult(null)
    },
  })

  // ── Execute mutation ────────────────────
  const executeMutation = useMutation({
    mutationFn: () =>
      templateApi.execute({
        template_id: selectedTemplate!,
        server_id: selectedId!,
        architecture_mode: selectedMode!,
        shared_values: sharedValues,
        step_values: stepValues,
        skipped_steps: skippedSteps,
        options: { auto_apply: autoApply, auto_save: autoSave },
      }),
    onSuccess: (resp) => {
      setExecuteResult(resp.data)
      queryClient.invalidateQueries({ queryKey: ['sync'] })
      setError(null)
    },
    onError: (err: any) => {
      console.error('[Template execute]', err.response?.data?.detail || err.message)
      setError(t('wizard.executeFailed'))
      setExecuteResult(null)
    },
  })

  // ── Render helper: field input ──────────
  const renderFieldInput = (f: any, value: any, onChange: (v: any) => void) => {
    if (f.type === 'textarea') {
      return (
        <textarea
          value={value ?? f.default ?? ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={f.placeholder}
          className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm font-mono outline-none focus:ring-2 focus:ring-blue-500 min-h-[80px] bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
        />
      )
    }
    if (f.type === 'select') {
      return (
        <select
          value={value ?? f.default ?? ''}
          onChange={(e) => onChange(f.type === 'number' ? Number(e.target.value) : e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
        >
          {f.options?.map((opt: any) => {
            const v = typeof opt === 'string' ? opt : opt.value
            const l = typeof opt === 'string' ? opt : opt.label
            return <option key={v} value={v}>{translateOptionLabel(t, l)}</option>
          })}
        </select>
      )
    }
    if (f.type === 'radio') {
      return (
        <div className="flex gap-3">
          {(f.options || []).map((opt: string) => (
            <label key={opt} className="flex items-center gap-1 text-sm">
              <input type="radio" name={f.name} checked={(value ?? f.default) === opt} onChange={() => onChange(opt)} />
              {translateOptionLabel(t, opt)}
            </label>
          ))}
        </div>
      )
    }
    if (f.type === 'toggle' || f.type === 'checkbox') {
      return (
        <input
          type="checkbox"
          checked={Boolean(value ?? f.default ?? 0)}
          onChange={(e) => onChange(e.target.checked ? 1 : 0)}
          className="h-4 w-4"
        />
      )
    }
    if (f.type === 'password') {
      return (
        <input
          type="password"
          value={value ?? f.default ?? ''}
          placeholder={f.placeholder}
          onChange={(e) => onChange(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
        />
      )
    }
    return (
      <input
        type={f.type === 'number' ? 'number' : 'text'}
        value={value ?? f.default ?? ''}
        placeholder={f.placeholder}
        min={f.min}
        max={f.max}
        onChange={(e) => onChange(f.type === 'number' ? Number(e.target.value) : e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
      />
    )
  }

  // ── Phase 0: Template selection ──────────
  if (!selectedTemplate) {
    return (
      <div>
        <div className="flex items-center gap-3 mb-6">
          <Rocket size={28} className="text-purple-600 dark:text-purple-400" />
          <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('template.title')}</h2>
        </div>
        <p className="text-gray-500 dark:text-slate-400 mb-6">{t('template.subtitle')}</p>

        <button onClick={handleBackToWizards} className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 mb-4">
          {t('wizard.back')}
        </button>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((tpl: any) => (
            <button
              key={tpl.id}
              onClick={() => setSelectedTemplate(tpl.id)}
              className="text-left p-5 rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-purple-400 dark:hover:border-purple-500 hover:shadow-md transition-all"
            >
              <div className="flex items-center gap-3 mb-2">
                <Rocket size={20} className="text-purple-600 dark:text-purple-400" />
                <span className="font-bold text-gray-900 dark:text-slate-100">{t(`template.${tpl.id}.name`, tpl.name)}</span>
                <span className="text-sm text-gray-400">{tpl.id}</span>
              </div>
              <p className="text-sm text-gray-500 dark:text-slate-400">{t(`template.${tpl.id}.description`, tpl.description)}</p>
            </button>
          ))}
        </div>
      </div>
    )
  }

  // ── Phase 1: Architecture selection ──────
  if (!selectedMode) {
    const archOptions = templateDetail?.data?.architecture_options || []
    return (
      <div>
        <button onClick={() => setSelectedTemplate(null)} className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 mb-4">
          {t('wizard.back')}
        </button>

        <div className="flex items-center gap-3 mb-2">
          <Rocket size={28} className="text-purple-600 dark:text-purple-400" />
          <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{t('template.selectArch')}</h2>
        </div>
        <p className="text-gray-500 dark:text-slate-400 mb-6">{t('template.selectArchDesc')}</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {archOptions.map((opt: any) => {
            const IconComp = ARCH_ICONS[opt.value] || Server
            return (
              <button
                key={opt.value}
                onClick={() => setSelectedMode(opt.value)}
                className="text-left p-5 rounded-xl border-2 border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-purple-400 dark:hover:border-purple-500 hover:shadow-lg transition-all"
              >
                <div className="flex items-center gap-3 mb-2">
                  <IconComp size={24} className="text-purple-600 dark:text-purple-400" />
                  <span className="font-bold text-gray-900 dark:text-slate-100 text-lg">{t(`template.arch.${opt.value}.label`, opt.label)}</span>
                </div>
                <p className="text-sm text-gray-500 dark:text-slate-400">{t(`template.arch.${opt.value}.description`, opt.description)}</p>
              </button>
            )
          })}
        </div>

        {/* Shared fields — entered once before steps */}
        {sharedFields.length > 0 && (
          <div className="mt-8 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 rounded-xl p-5">
            <h3 className="text-lg font-semibold text-purple-800 dark:text-purple-300 mb-4">
              {t('template.sharedFieldsTitle')}
            </h3>
            <p className="text-sm text-purple-600 dark:text-purple-400 mb-4">
              {t('template.sharedFieldsDesc')}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {sharedFields.map((f: any) => (
                <div key={f.name}>
                  <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                    {translateFieldLabel(t, f.name, f.label)}
                    {f.required && <span className="text-red-500"> *</span>}
                  </label>
                  {renderFieldInput(f, sharedValues[f.name], (v) => handleSharedChange(f.name, v))}
                  {f.help && <p className="text-xs text-purple-500 dark:text-purple-400 mt-1">{translateFieldHelp(t, f.name, f.help)}</p>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── Phase 2: Multi-step wizard ──────────
  if (steps.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={24} className="animate-spin text-purple-500" />
      </div>
    )
  }

  const currentStep = steps[currentStepIdx]
  const isSkipped = skippedSteps.includes(currentStep?.step_key)
  const isLastStep = currentStepIdx === steps.length - 1
  const hasResult = !!executeResult

  const currentStepFields = currentStep?.fields || []
  const arrayFieldNames = currentStep?.array_fields || []
  const arrayFields = currentStepFields.filter((f: any) => f.is_array)
  const singleFields = currentStepFields.filter((f: any) => !f.is_array)
  const arrayRowCount = arrayFields.length > 0
    ? (stepValues[currentStep?.step_key]?.[`_array_${arrayFields[0]?.name}`] || []).length
    : 0

  // ── Phase 2a: Show execution result ────
  if (hasResult) {
    return (
      <div>
        <div className="flex items-center gap-3 mb-4">
          {executeResult.ok ? (
            <CheckCircle2 size={28} className="text-green-600" />
          ) : (
            <XCircle size={28} className="text-red-600" />
          )}
          <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">
            {executeResult.ok ? t('template.successTitle') : t('template.failedTitle')}
          </h2>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5 mb-4">
          <p className="text-sm text-gray-500 dark:text-slate-400 mb-2">
            {t('template.totalSql', { count: executeResult.total_sql_count || 0 })}
          </p>
          {executeResult.step_results?.map((sr: any, i: number) => (
            <div key={i} className={`p-3 rounded-lg mb-2 ${
              sr.skipped ? 'bg-gray-100 dark:bg-slate-700' :
              sr.ok ? 'bg-green-50 dark:bg-green-900/20' :
              'bg-red-50 dark:bg-red-900/20'
            }`}>
              <div className="flex items-center gap-2 text-sm">
                {sr.skipped ? <SkipForward size={14} className="text-gray-400" /> :
                 sr.ok ? <CheckCircle2 size={14} className="text-green-600" /> :
                 <XCircle size={14} className="text-red-600" />}
                <span className="font-medium">{sr.title}</span>
                {sr.skipped && <span className="text-gray-400">({t('template.skipped')})</span>}
              </div>
              {sr.errors && sr.errors.length > 0 && (
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">{t('common.failed')} ({sr.errors.length})</p>
              )}
              {sr.executed_sql && sr.executed_sql.length > 0 && (
                <div className="mt-1">
                  <pre className="text-xs text-gray-600 dark:text-slate-400 font-mono">
                    {sr.executed_sql.join(';\n')}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>

        <button onClick={handleBackToWizards}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">
          {t('wizard.back')}
        </button>
      </div>
    )
  }

  // ── Phase 2b: Multi-step wizard form ────

  return (
    <div>
      {/* Back to arch selection */}
      <button onClick={() => { setSelectedMode(null); setCurrentStepIdx(0); setSkippedSteps([]) }}
        className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 mb-4">
        {t('wizard.back')}
      </button>

      {/* Stepper indicator */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto">
        {/* Step 0: Architecture */}
        <div className="flex items-center gap-1 text-sm">
          <CheckCircle2 size={16} className="text-purple-600" />
          <span className="font-medium text-purple-600 dark:text-purple-400">{t('template.stepArch')}</span>
        </div>
        <ChevronRight size={14} className="text-gray-400" />
        {steps.map((step: any, idx: number) => {
          const isCurrent = idx === currentStepIdx
          const isDone = idx < currentStepIdx
          const isSkippedStep = skippedSteps.includes(step.step_key)
          return (
            <div key={step.step_key} className="flex items-center gap-1">
              <div className={`flex items-center gap-1 text-sm ${
                isCurrent ? 'font-semibold text-purple-600 dark:text-purple-400' :
                isSkippedStep ? 'text-gray-400 dark:text-slate-500' :
                isDone ? 'text-green-600 dark:text-green-400' :
                'text-gray-500 dark:text-slate-400'
              }`}>
                {isDone && !isSkippedStep ? <CheckCircle2 size={16} /> :
                 isSkippedStep ? <SkipForward size={16} /> :
                 isCurrent ? <div className="w-4 h-4 rounded-full bg-purple-600 flex items-center justify-center text-white text-xs">{idx + 1}</div> :
                 <div className="w-4 h-4 rounded-full border border-gray-400 flex items-center justify-center text-gray-500 text-xs">{idx + 1}</div>}
                <span className="hidden md:inline">{t(`template.step.${step.i18n_key || step.wizard_id}.title`, step.title)}</span>
              </div>
              {idx < steps.length - 1 && <ChevronRight size={14} className="text-gray-400" />}
            </div>
          )
        })}
      </div>

      {/* Current step form */}
      <div>
          {/* Step title */}
          <div className="mb-4">
            <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100">
              {t(`template.step.${currentStep?.i18n_key || currentStep?.wizard_id}.title`, currentStep?.title)}
            </h2>
            <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
              {t(`template.step.${currentStep?.i18n_key || currentStep?.wizard_id}.description`, currentStep?.description)}
            </p>
            <span className="text-xs text-gray-400 dark:text-slate-500">
              {t('template.stepOf', { current: currentStepIdx + 1, total: steps.length })}
              {currentStep?.wizard_id && ` — ${currentStep.wizard_id}`}
            </span>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-3 text-red-700 dark:text-red-400 text-sm mb-4">
              {error}
            </div>
          )}

          {/* Guide */}
          {currentStep?.guide && (
            <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 rounded-lg p-4 mb-4">
              <div className="flex items-start gap-2">
                <span className="text-purple-500 text-lg">💡</span>
                <div className="text-sm text-purple-700 dark:text-purple-400 whitespace-pre-line leading-relaxed">
                  {t(`template.step.${currentStep?.i18n_key || currentStep?.wizard_id}.guide`, currentStep.guide)}
                </div>
              </div>
            </div>
          )}

          {/* Shared fields reference */}
          {Object.keys(currentStep?.shared_refs || {}).length > 0 && (
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg p-3 mb-4">
              <p className="text-sm text-blue-700 dark:text-blue-400">
                {t('template.sharedInherited')}
                {Object.entries(currentStep.shared_refs).map(([wfName, sharedName]) => (
                  <span key={wfName} className="ml-1 font-medium">
                    {translateFieldLabel(t, wfName, wfName)} ← {translateFieldLabel(t, String(sharedName), String(sharedName))}={sharedValues[String(sharedName)] ?? '?'}
                  </span>
                ))}
              </p>
            </div>
          )}

          {/* Form */}
          <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5 mb-4">
            {/* Array fields section */}
            {arrayFields.length > 0 && (
              <div className="mb-6">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300">
                    {t('template.multiEntry')}
                  </h3>
                  <button
                    onClick={() => {
                      const defaults: Record<string, any> = {}
                      arrayFields.forEach((f: any) => { defaults[f.name] = f.default ?? '' })
                      handleArrayAdd(currentStep.step_key, arrayFields.map((f: any) => f.name), defaults)
                    }}
                    className="flex items-center gap-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 px-3 py-1.5 rounded-lg text-sm hover:bg-purple-200 dark:hover:bg-purple-900/50"
                  >
                    <Plus size={14} />
                    {t('template.addRow')}
                  </button>
                </div>
                {Array.from({ length: arrayRowCount }, (_, rowIdx) => (
                  <div key={rowIdx} className="border border-gray-200 dark:border-slate-600 rounded-lg p-3 mb-2">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-600 dark:text-slate-400">
                        #{rowIdx + 1}
                      </span>
                      {rowIdx > 0 && (
                        <button
                          onClick={() => handleArrayRemove(
                            currentStep.step_key,
                            arrayFields.map((f: any) => f.name),
                            rowIdx,
                          )}
                          className="flex items-center gap-1 text-red-600 dark:text-red-400 text-xs hover:text-red-800"
                        >
                          <Trash2 size={12} />
                          {t('template.removeRow')}
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {arrayFields.map((f: any) => (
                        <div key={`${f.name}_${rowIdx}`}>
                          <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                            {translateFieldLabel(t, f.name, f.label)}
                            {f.required && <span className="text-red-500"> *</span>}
                          </label>
                          <input
                            type={f.type === 'number' ? 'number' : 'text'}
                            value={stepValues[currentStep.step_key]?.[`_array_${f.name}`]?.[rowIdx] ?? f.default ?? ''}
                            min={f.min}
                            max={f.max}
                            placeholder={f.placeholder}
                            onChange={(e) => handleArrayItemChange(
                              currentStep.step_key, f.name, rowIdx,
                              f.type === 'number' ? Number(e.target.value) : e.target.value,
                            )}
                            className="w-full px-3 py-2 border border-gray-300 dark:border-slate-600 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-slate-700 text-gray-900 dark:text-slate-100"
                          />
                          {f.help && <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">{translateFieldHelp(t, f.name, f.help)}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Single fields section */}
            {singleFields.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {singleFields.map((f: any) => (
                  <div key={f.name}>
                    <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">
                      {translateFieldLabel(t, f.name, f.label)}
                      {f.required && <span className="text-red-500"> *</span>}
                      {f.shared_from && <span className="text-xs text-blue-500 ml-1">{t('template.sharedMark')}</span>}
                    </label>
                    {renderFieldInput(
                      f,
                      f.shared_from && sharedValues[f.shared_from] !== undefined
                        ? sharedValues[f.shared_from]
                        : stepValues[currentStep.step_key]?.[f.name],
                      (v) => handleStepChange(currentStep.step_key, f.name, v),
                    )}
                    {f.help && <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">{translateFieldHelp(t, f.name, f.help)}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Navigation buttons */}
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              {currentStepIdx > 0 && (
                <button onClick={handleBackStep}
                  className="flex items-center gap-2 bg-gray-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-700">
                  <ChevronLeft size={16} />
                  {t('template.prevStep')}
                </button>
              )}
              {currentStep?.skip_allowed && !isSkipped && (
                <button onClick={() => handleSkipStep(currentStep.step_key)}
                  className="flex items-center gap-2 bg-gray-200 dark:bg-slate-600 text-gray-700 dark:text-slate-300 px-4 py-2 rounded-lg text-sm hover:bg-gray-300 dark:hover:bg-slate-500">
                  <SkipForward size={16} />
                  {t('template.skipStep')}
                </button>
              )}
            </div>
            <div className="flex gap-2">
              {!isLastStep ? (
                <button onClick={handleNextStep}
                  className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-purple-700">
                  {t('template.nextStep')}
                  <ChevronRight size={16} />
                </button>
              ) : (
                <>
                  <button onClick={() => previewMutation.mutate()}
                    disabled={previewMutation.isPending || !selectedId}
                    className="flex items-center gap-2 bg-gray-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-700 disabled:opacity-50">
                    <Eye size={16} />
                    {previewMutation.isPending ? t('wizard.previewing') : t('wizard.previewSql')}
                  </button>
                  <button onClick={() => executeMutation.mutate()}
                    disabled={executeMutation.isPending || !selectedId}
                    className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-purple-700 disabled:opacity-50">
                    <Play size={16} />
                    {executeMutation.isPending ? t('wizard.executing') : t('template.submitAll')}
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Auto Apply / Auto Save */}
          {isLastStep && (
            <div className="flex gap-4 mt-4">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-300">
                <input type="checkbox" checked={autoApply} onChange={(e) => setAutoApply(e.target.checked)} className="h-4 w-4" />
                {t('wizard.autoApply')}
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-300">
                <input type="checkbox" checked={autoSave} onChange={(e) => setAutoSave(e.target.checked)} className="h-4 w-4" />
                {t('wizard.autoSave')}
              </label>
            </div>
          )}

          {/* No server selected warning */}
          {isLastStep && !selectedId && (
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 text-amber-700 dark:text-amber-400 mt-4">
              {t('wizard.noServerSelected')}
            </div>
          )}

          {/* Preview result */}
          {previewResult && (
            <div className="mt-4 bg-gray-900 rounded-xl border border-gray-700 p-4">
              <h3 className="text-sm font-semibold text-gray-200 mb-2">{t('wizard.sqlPreview')}</h3>
              <p className="text-xs text-gray-400 mb-2">
                {t('template.totalSql', { count: previewResult.total_sql_count || 0 })}
              </p>
              <pre className="text-xs text-green-300 whitespace-pre-wrap font-mono">
                {(previewResult.sql_preview || []).join(';\n')}{previewResult.sql_preview?.length > 0 ? ';' : ''}
              </pre>
              {previewResult.step_results?.map((sr: any, i: number) => (
                <div key={i} className="mt-2 border-t border-gray-700 pt-2">
                  <p className="text-xs text-gray-300 font-medium">{sr.title} {sr.skipped ? `(${t('template.skipped')})` : ''}</p>
                  {sr.errors?.length > 0 && (
                    <p className="text-xs text-red-400">{t('common.failed')} ({sr.errors.length})</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
  )
}
