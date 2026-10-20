import {
  createContext,
  useEffect,
  useRef,
  ReactNode,
} from 'react'
import { useWsStore } from '@/stores/wsStore'
import { useAuthStore } from '@/stores/authStore'

// Cloudflare Pages is not the WebSocket host. Derive AWS socket origin from API.
const WS_URL = (import.meta.env.VITE_WS_URL || (import.meta.env.VITE_API_URL ?? '').replace(/^http/, 'ws')).replace(/\/$/, '')
const BASE_DELAY          = 1_000
const MAX_DELAY           = 30_000

interface WebSocketContextValue {
  send: (data: string) => void
}

const WebSocketContext = createContext<WebSocketContextValue>({ send: () => {} })

export default function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef             = useRef<WebSocket | null>(null)
  const reconnectRef      = useRef<ReturnType<typeof setTimeout> | null>(null)
  const delayRef          = useRef(BASE_DELAY)
  const mountedRef        = useRef(true)
  const connectRef        = useRef<() => void>(() => {})
  const scheduleRef       = useRef<() => void>(() => {})

  const { setStatus, setPayload, incrementReconnect, resetReconnect } = useWsStore()
  const { isAuthenticated } = useAuthStore()

  const connect = () => {
    if (!mountedRef.current)                          return
    if (!isAuthenticated)                             return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')

    const ws      = new WebSocket(`${WS_URL}/ws/dashboard`)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      setStatus('connected')
      resetReconnect()
      delayRef.current = BASE_DELAY
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      try {
        const payload = JSON.parse(event.data)
        setPayload(payload)
      } catch {
        // Ignore malformed frames; a later valid frame can still update the dashboard.
      }
    }

    ws.onerror = () => {
      if (!mountedRef.current) return
      setStatus('error')
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setStatus('disconnected')
      wsRef.current = null
      scheduleRef.current()
    }
  }

  const schedule = () => {
    if (!mountedRef.current) return
    incrementReconnect()
    reconnectRef.current = setTimeout(() => {
      delayRef.current = Math.min(delayRef.current * 2, MAX_DELAY)
      connectRef.current()
    }, delayRef.current)
  }

  const send = (data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data)
    }
  }

  connectRef.current = connect
  scheduleRef.current = schedule

  useEffect(() => {
    mountedRef.current = true
    if (isAuthenticated) connectRef.current()

    return () => {
      mountedRef.current = false
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [isAuthenticated])

  return (
    <WebSocketContext.Provider value={{ send }}>
      {children}
    </WebSocketContext.Provider>
  )
}
