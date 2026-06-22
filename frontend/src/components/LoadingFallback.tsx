import { Loader2 } from 'lucide-react'

/**
 * LoadingFallback - Simple centered spinner for React.lazy Suspense boundaries.
 * Each lazy-loaded page shows this while its code chunk loads over the network.
 */
export default function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="animate-spin text-blue-600" size={32} />
    </div>
  )
}
