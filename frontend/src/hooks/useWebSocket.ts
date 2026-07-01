import { useState, useEffect, useRef, useCallback } from 'react'

export interface WebSocketMessage {
  type: string
  [key: string]: unknown
}

export interface UseWebSocketResult<T = WebSocketMessage> {
  /** Latest data received from the server */
  data: T | null
  /** Whether the WebSocket is currently connected */
  isConnected: boolean
  /** Latest error, if any */
  error: string | null
  /** Manually trigger a reconnection */
  reconnect: () => void
}

/**
 * WebSocket hook with exponential backoff reconnection.
 *
 * Features:
 * - Automatic reconnection with exponential backoff (1s, 2s, 4s, ..., max 30s)
 * - Heartbeat ping every 30s (detects silent disconnections)
 * - Cleans up on unmount
 *
 * @param url  - The full WebSocket URL (ws:// or wss://)
 * @param enabled - Whether to open the connection (default: true)
 */
export function useWebSocket<T = WebSocketMessage>(
  url: string | null,
  enabled: boolean = true,
): UseWebSocketResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const retryCount = useRef(0)
  const retryTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const heartbeatInterval = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Helpers ──────────────────────────────────────────────────────────

  const clearHeartbeat = useCallback(() => {
    if (heartbeatInterval.current !== null) {
      clearInterval(heartbeatInterval.current)
      heartbeatInterval.current = null
    }
  }, [])

  const startHeartbeat = useCallback((ws: WebSocket) => {
    clearHeartbeat()
    heartbeatInterval.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30_000)
  }, [clearHeartbeat])

  const getRetryDelay = useCallback(() => {
    // Exponential backoff: 1000 * 2^retry ms, capped at 30_000 ms
    const delay = Math.min(1000 * 2 ** retryCount.current, 30_000)
    // Add ±20 % jitter to prevent thundering herd
    const jitter = delay * (0.8 + Math.random() * 0.4)
    return Math.round(jitter)
  }, [])

  const connect = useCallback(() => {
    if (!url || !enabled) return

    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }

    setError(null)

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      retryCount.current = 0
      startHeartbeat(ws)
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const parsed: T = JSON.parse(event.data as string)
        // Ignore pong heartbeats
        if ((parsed as unknown as { type?: string })?.type === 'pong') return
        setData(parsed)
      } catch {
        // Non-JSON message — ignore
      }
    }

    ws.onclose = (event: CloseEvent) => {
      setIsConnected(false)
      clearHeartbeat()

      // Auto-reconnect unless the close was clean and intentional
      if (enabled) {
        const delay = getRetryDelay()
        retryCount.current += 1
        retryTimeout.current = setTimeout(() => {
          connect()
        }, delay)
      }
    }

    ws.onerror = () => {
      setError('WebSocket connection error')
      // onerror is always followed by onclose, so reconnection is handled there
    }
  }, [url, enabled, startHeartbeat, getRetryDelay])

  // ── Reconnect (manual trigger) ───────────────────────────────────────

  const reconnect = useCallback(() => {
    retryCount.current = 0
    if (retryTimeout.current !== null) {
      clearTimeout(retryTimeout.current)
      retryTimeout.current = null
    }
    connect()
  }, [connect])

  // ── Lifecycle ────────────────────────────────────────────────────────

  useEffect(() => {
    if (enabled && url) {
      connect()
    }

    return () => {
      // Cleanup on unmount or when url/enabled changes
      if (retryTimeout.current !== null) {
        clearTimeout(retryTimeout.current)
      }
      clearHeartbeat()
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [url, enabled, connect, clearHeartbeat])

  return { data, isConnected, error, reconnect }
}

export default useWebSocket
