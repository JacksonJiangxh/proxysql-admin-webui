import React, { ErrorInfo, ReactNode } from 'react'
import { useI18n } from '../i18n'

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: string | null
}

/**
 * Global error boundary component.
 *
 * Catches rendering errors in child components and displays a friendly fallback UI
 * instead of crashing the entire application. In development mode, the error
 * stack is shown to aid debugging.
 *
 * Usage: wrap the top-level router or layout with <ErrorBoundary>.
 */
export class ErrorBoundary extends React.Component<
  { children: ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo: errorInfo.componentStack || null })
    // Log to console in all environments; in production you may also send
    // this to an error tracking service (eentry, LogRocket, etc.).
    console.error('[ErrorBoundary]', error, errorInfo)
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    window.location.reload()
  }

  handleGoHome = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    window.location.href = '/'
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallbackView error={this.state.error} onReload={this.handleReload} onGoHome={this.handleGoHome} />
    }
    return this.props.children
  }
}

/** Friendly error page shown when a rendering error is caught. */
function ErrorFallbackView({
  error,
  onReload,
  onGoHome,
}: {
  error: Error | null
  onReload: () => void
  onGoHome: () => void
}) {
  const { t } = useI18n()
  const isDev = import.meta.env.DEV

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-slate-900 px-4">
      <div className="max-w-lg w-full bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-8 text-center">
        {/* Error icon */}
        <div className="mb-6">
          <span className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-3xl">
            !
          </span>
        </div>

        <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100 mb-2">
          {t('error.title') || 'Something went wrong'}
        </h2>
        <p className="text-gray-500 dark:text-slate-400 mb-6">
          {t('error.description') || 'An unexpected error occurred. Please try again.'}
        </p>

        {/* Error details (dev mode only) */}
        {isDev && error && (
          <pre className="mb-6 p-4 bg-gray-100 dark:bg-slate-700 rounded-lg text-left text-xs text-red-600 dark:text-red-400 overflow-auto max-h-48">
            {error.stack}
          </pre>
        )}

        {/* Action buttons */}
        <div className="flex gap-3 justify-center">
          <button
            onClick={onReload}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {t('error.reload') || 'Reload Page'}
          </button>
          <button
            onClick={onGoHome}
            className="px-4 py-2 bg-gray-200 dark:bg-slate-700 hover:bg-gray-300 dark:hover:bg-slate-600 text-gray-700 dark:text-slate-300 rounded-lg text-sm font-medium transition-colors"
          >
            {t('error.goHome') || 'Go to Home'}
          </button>
        </div>
      </div>
    </div>
  )
}
