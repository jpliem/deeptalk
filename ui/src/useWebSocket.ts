import { useEffect, useRef, useCallback } from 'react'
import { wsUrl } from './ws'

type MessageHandler<T> = (data: T) => void

/**
 * WebSocket hook with automatic reconnection (exponential backoff).
 * Tries to reconnect on close/error with backoff up to 30s.
 */
export function useWebSocket<T>(
  path: string,
  sessionId: string,
  onMessage: MessageHandler<T>,
  wsBase?: string,
): { close: () => void } {
  const wsRef = useRef<WebSocket | null>(null)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage
  const retriesRef = useRef(0)
  const closedRef = useRef(false)

  const connect = useCallback(() => {
    if (closedRef.current) return
    const ws = new WebSocket(wsUrl(path, sessionId, wsBase))
    wsRef.current = ws

    ws.onmessage = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as T
        onMessageRef.current(data)
      } catch {
        // skip malformed messages
      }
    }

    ws.onclose = () => {
      wsRef.current = null
      if (closedRef.current) return
      const delay = Math.min(1000 * 2 ** retriesRef.current, 30000)
      retriesRef.current += 1
      setTimeout(connect, delay)
    }

    ws.onerror = () => {
      // onclose will fire after onerror, triggering reconnect
      ws.close()
    }
  }, [path, sessionId, wsBase])

  useEffect(() => {
    closedRef.current = false
    retriesRef.current = 0
    connect()
    return () => {
      closedRef.current = true
      wsRef.current?.close()
    }
  }, [connect])

  return {
    close: () => {
      closedRef.current = true
      wsRef.current?.close()
    },
  }
}
