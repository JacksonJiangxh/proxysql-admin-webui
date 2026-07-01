/**
 * PageSkeleton - Content-placeholder loading skeleton for Suspense fallback.
 *
 * Unlike a plain spinner, this provides a skeleton that mimics the page
 * structure, reducing perceived loading time and layout shift.
 */
export default function PageSkeleton({ type = 'default' }: { type?: 'default' | 'dashboard' | 'table' }) {
  if (type === 'dashboard') {
    return (
      <div className="animate-pulse space-y-6 p-2">
        {/* Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5">
              <div className="h-3 bg-gray-200 dark:bg-slate-700 rounded w-1/3 mb-3" />
              <div className="h-7 bg-gray-200 dark:bg-slate-700 rounded w-1/2 mb-2" />
              <div className="h-3 bg-gray-200 dark:bg-slate-700 rounded w-2/3" />
            </div>
          ))}
        </div>
        {/* Connection Pool Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5">
          <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-1/4 mb-4" />
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-200 dark:bg-slate-700 rounded" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (type === 'table') {
    return (
      <div className="animate-pulse space-y-4 p-2">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div className="h-6 bg-gray-200 dark:bg-slate-700 rounded w-1/4" />
          <div className="h-8 bg-gray-200 dark:bg-slate-700 rounded w-24" />
        </div>
        {/* Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 overflow-hidden">
          <div className="h-10 bg-gray-100 dark:bg-slate-700 border-b border-gray-200 dark:border-slate-600" />
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="h-12 border-b border-gray-100 dark:border-slate-700/50 flex items-center px-4"
            >
              <div className="h-3 bg-gray-200 dark:bg-slate-700 rounded w-1/4" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Default: generic page skeleton
  return (
    <div className="animate-pulse space-y-6 p-2">
      {/* Title bar */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-6 bg-gray-200 dark:bg-slate-700 rounded w-48" />
          <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-72" />
        </div>
        <div className="h-9 bg-gray-200 dark:bg-slate-700 rounded w-28" />
      </div>
      {/* Content blocks */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5">
        <div className="space-y-3">
          <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-full" />
          <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-5/6" />
          <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-3/4" />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5 h-32">
          <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-1/3 mb-3" />
          <div className="h-3 bg-gray-200 dark:bg-slate-700 rounded w-full mb-2" />
          <div className="h-3 bg-gray-200 dark:bg-slate-700 rounded w-2/3" />
        </div>
        <div className="bg-white dark:bg-slate-800 rounded-xl border border-gray-200 dark:border-slate-700 p-5 h-32">
          <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-1/3 mb-3" />
          <div className="h-3 bg-gray-200 dark:bg-slate-700 rounded w-full mb-2" />
          <div className="h-3 bg-gray-200 dark:bg-slate-700 rounded w-2/3" />
        </div>
      </div>
    </div>
  )
}
