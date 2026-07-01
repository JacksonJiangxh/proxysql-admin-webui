import { useState, useEffect, useCallback, createContext, useContext, type ReactNode } from 'react'
import { useI18n } from '../i18n'
import { X, ChevronRight, ChevronLeft, CheckCircle, Play } from 'lucide-react'

// ── Tour step definition ──

interface TourStep {
  /** CSS selector of the element to highlight */
  target: string
  /** Title shown in the tooltip */
  title: string
  /** Body text */
  content: string
  /** Tooltip placement relative to target */
  placement?: 'bottom' | 'top' | 'left' | 'right'
}

// ── Tour steps (static definition) ──

function buildTourSteps(t: (key: string) => string): TourStep[] {
  return [
    {
      target: '[data-tour="sidebar"]',
      title: t('tour.sidebar.title'),
      content: t('tour.sidebar.content'),
      placement: 'right',
    },
    {
      target: '[data-tour="server-selector"]',
      title: t('tour.serverSelector.title'),
      content: t('tour.serverSelector.content'),
      placement: 'bottom',
    },
    {
      target: '[data-tour="theme-language"]',
      title: t('tour.themeLanguage.title'),
      content: t('tour.themeLanguage.content'),
      placement: 'bottom',
    },
    {
      target: '[data-tour="dashboard-cards"]',
      title: t('tour.dashboard.title'),
      content: t('tour.dashboard.content'),
      placement: 'bottom',
    },
    {
      target: '[data-tour="nav-wizards"]',
      title: t('tour.wizards.title'),
      content: t('tour.wizards.content'),
      placement: 'right',
    },
    {
      target: '[data-tour="search-trigger"]',
      title: t('tour.search.title'),
      content: t('tour.search.content'),
      placement: 'bottom',
    },
  ]
}

// ── Context ──

interface TourContextValue {
  isActive: boolean
  currentStep: number
  startTour: () => void
  stopTour: () => void
  totalSteps: number
}

const TourContext = createContext<TourContextValue>({
  isActive: false,
  currentStep: 0,
  startTour: () => {},
  stopTour: () => {},
  totalSteps: 0,
})

export function useTour() {
  return useContext(TourContext)
}

// ── Provider ──

const TOUR_COMPLETED_KEY = 'proxysql_tour_completed'

export function TourProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const [isActive, setIsActive] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [hasCompleted, setHasCompleted] = useState(false)

  const steps = buildTourSteps(t)
  const totalSteps = steps.length

  // Check if user has completed the tour
  useEffect(() => {
    const done = localStorage.getItem(TOUR_COMPLETED_KEY)
    setHasCompleted(done === 'true')
  }, [])

  const startTour = useCallback(() => {
    setCurrentStep(0)
    setIsActive(true)
  }, [])

  const stopTour = useCallback(() => {
    setIsActive(false)
    localStorage.setItem(TOUR_COMPLETED_KEY, 'true')
    setHasCompleted(true)
  }, [])

  const goNext = useCallback(() => {
    if (currentStep < totalSteps - 1) {
      setCurrentStep((s) => s + 1)
    } else {
      stopTour()
    }
  }, [currentStep, totalSteps, stopTour])

  const goPrev = useCallback(() => {
    setCurrentStep((s) => Math.max(0, s - 1))
  }, [])

  const skip = useCallback(() => {
    stopTour()
  }, [stopTour])

  // Scroll target into view and calculate position
  const step = steps[currentStep]

  return (
    <TourContext.Provider value={{ isActive, currentStep, startTour, stopTour, totalSteps }}>
      {children}
      {/* Tour overlay + tooltip */}
      {isActive && step && (
        <TourOverlay
          step={step}
          currentStep={currentStep}
          totalSteps={totalSteps}
          onNext={goNext}
          onPrev={goPrev}
          onSkip={skip}
        />
      )}
      {/* "Start tour" floating button — only shown if tour not yet completed */}
      {!isActive && !hasCompleted && (
        <button
          data-tour="start-tour-btn"
          onClick={startTour}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg text-sm font-medium transition-all hover:scale-105"
          title={t('tour.start')}
        >
          <Play size={14} />
          <span>{t('tour.start')}</span>
        </button>
      )}
    </TourContext.Provider>
  )
}

// ── Overlay + Tooltip ──

function TourOverlay({
  step,
  currentStep,
  totalSteps,
  onNext,
  onPrev,
  onSkip,
}: {
  step: TourStep
  currentStep: number
  totalSteps: number
  onNext: () => void
  onPrev: () => void
  onSkip: () => void
}) {
  const { t } = useI18n()
  const [spotRect, setSpotRect] = useState<DOMRect | null>(null)
  const [tooltipStyle, setTooltipStyle] = useState<React.CSSProperties>({})

  useEffect(() => {
    const el = document.querySelector(step.target) as HTMLElement | null
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      const rect = el.getBoundingClientRect()
      setSpotRect(rect)

      // Position tooltip based on placement
      const gap = 12
      let left = 0
      let top = 0

      switch (step.placement) {
        case 'right':
          left = rect.right + gap
          top = rect.top + rect.height / 2 - 120
          break
        case 'left':
          left = rect.left - 340
          top = rect.top + rect.height / 2 - 120
          break
        case 'top':
          left = rect.left + rect.width / 2 - 160
          top = rect.top - 260
          break
        case 'bottom':
        default:
          left = rect.left + rect.width / 2 - 160
          top = rect.bottom + gap
          break
      }

      // Clamp to viewport
      if (left < 16) left = 16
      if (left + 320 > window.innerWidth - 16) left = window.innerWidth - 336
      if (top < 16) top = 16
      if (top + 260 > window.innerHeight - 16) top = window.innerHeight - 276

      setTooltipStyle({ left: `${left}px`, top: `${top}px` })
    }
  }, [step])

  return (
    <>
      {/* Spotlight border around the target */}
      {spotRect && (
        <div
          className="fixed z-50 pointer-events-none rounded-lg ring-2 ring-blue-500/60 ring-offset-2 ring-offset-transparent transition-all duration-300"
          style={{
            left: spotRect.left - 4,
            top: spotRect.top - 4,
            width: spotRect.width + 8,
            height: spotRect.height + 8,
          }}
        />
      )}
      {/* Semi-transparent backdrop (with cutout effect simulated via pointer-events) */}
      <div className="fixed inset-0 z-40 bg-black/30 transition-opacity duration-300" onClick={onSkip} />
      {/* Tooltip card */}
      <div
        className="fixed z-50 w-[320px] bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 shadow-2xl p-5 transition-all duration-300"
        style={tooltipStyle}
      >
        {/* Step counter */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
            {t('tour.stepCounter').replace('{current}', String(currentStep + 1)).replace('{total}', String(totalSteps))}
          </span>
          <button onClick={onSkip} className="text-gray-400 hover:text-gray-600 dark:hover:text-slate-300">
            <X size={14} />
          </button>
        </div>
        {/* Content */}
        <h4 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-1.5">{step.title}</h4>
        <p className="text-sm text-gray-500 dark:text-slate-400 leading-relaxed">{step.content}</p>
        {/* Navigation */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100 dark:border-slate-700">
          <button
            onClick={onSkip}
            className="text-xs text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300 px-2 py-1"
          >
            {t('tour.skip')}
          </button>
          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                onClick={onPrev}
                className="flex items-center gap-1 text-xs text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-200 px-2 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700"
              >
                <ChevronLeft size={14} />
                {t('tour.prev')}
              </button>
            )}
            <button
              onClick={onNext}
              className="flex items-center gap-1 text-xs text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg font-medium transition-colors"
            >
              {currentStep < totalSteps - 1 ? (
                <>
                  {t('tour.next')}
                  <ChevronRight size={14} />
                </>
              ) : (
                <>
                  <CheckCircle size={14} />
                  {t('tour.done')}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
