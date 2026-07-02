import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number
}

interface ToastContextValue {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, 'id'>) => string
  removeToast: (id: string) => void
  success: (title: string, message?: string) => string
  error: (title: string, message?: string) => string
  warning: (title: string, message?: string) => string
  info: (title: string, message?: string) => string
}

const ToastContext = createContext<ToastContextValue | null>(null)

const DEFAULT_DURATION = 5000

const iconMap: Record<ToastType, React.ElementType> = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
}

const colorMap: Record<ToastType, string> = {
  success: 'border-green-400 bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300',
  error: 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-300',
  warning: 'border-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-300',
  info: 'border-blue-400 bg-blue-50 dark:bg-blue-900/20 text-blue-800 dark:text-blue-300',
}

const iconColorMap: Record<ToastType, string> = {
  success: 'text-green-500 dark:text-green-400',
  error: 'text-red-500 dark:text-red-400',
  warning: 'text-yellow-500 dark:text-yellow-400',
  info: 'text-blue-500 dark:text-blue-400',
}

const ANIMATION_DURATION = 300

/**
 * Unified toast/notification system.
 *
 * Provides a lightweight toast context that can be used anywhere in the app
 * via the `useToast()` hook.  Toasts auto-dismiss after a configurable duration
 * and stack from the top-right corner.  Supports success, error, warning, and info types.
 */

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
  const exitingIdsRef = useRef<Set<string>>(new Set())

  const removeToast = useCallback((id: string) => {
    // Animate out first, then remove
    exitingIdsRef.current.add(id)
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
      exitingIdsRef.current.delete(id)
      const timer = timersRef.current.get(id)
      if (timer) {
        clearTimeout(timer)
        timersRef.current.delete(id)
      }
    }, ANIMATION_DURATION)
  }, [])

  const addToast = useCallback(
    (toast: Omit<Toast, 'id'>): string => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const duration = toast.duration ?? DEFAULT_DURATION
      setToasts((prev) => [...prev, { ...toast, id }])
      // Auto-dismiss
      const timer = setTimeout(() => removeToast(id), duration)
      timersRef.current.set(id, timer)
      return id
    },
    [removeToast]
  )

  const success = useCallback((title: string, message?: string) => addToast({ type: 'success', title, message }), [addToast])
  const error = useCallback((title: string, message?: string) => addToast({ type: 'error', title, message }), [addToast])
  const warning = useCallback((title: string, message?: string) => addToast({ type: 'warning', title, message }), [addToast])
  const info = useCallback((title: string, message?: string) => addToast({ type: 'info', title, message }), [addToast])

  // Clean up timers on unmount
  useEffect(() => {
    return () => {
      timersRef.current.forEach((timer) => clearTimeout(timer))
      timersRef.current.clear()
    }
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast, success, error, warning, info }}>
      {children}
      {/* Toast container: fixed in top-right, stacks vertically */}
      <div
        role="region"
        aria-label="Notifications"
        aria-live="polite"
        className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
      >
        {toasts.map((toast) => {
          const Icon = iconMap[toast.type]
          const isExiting = exitingIdsRef.current.has(toast.id)
          return (
            <div
              key={toast.id}
              role="alert"
              className={`pointer-events-auto flex items-start gap-3 p-4 border rounded-lg shadow-lg transition-all duration-${ANIMATION_DURATION} ${colorMap[toast.type]} ${isExiting ? 'opacity-0 translate-x-4 scale-95' : 'opacity-100 translate-x-0 scale-100'}`}
            >
              <Icon size={20} className={`flex-shrink-0 mt-0.5 ${iconColorMap[toast.type]}`} aria-hidden="true" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold">{toast.title}</p>
                {toast.message && <p className="text-xs mt-0.5 opacity-80">{toast.message}</p>}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="flex-shrink-0 p-1 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                aria-label="Close notification"
              >
                <X size={14} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within a <ToastProvider>')
  }
  return ctx
}
