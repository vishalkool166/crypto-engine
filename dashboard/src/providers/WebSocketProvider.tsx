import {
  createContext,
  useContext,
  useEffect,
  useRef,
  ReactNode,
} from 'react'
import { useWsStore } from '@/stores/wsStore'
import { useAuthStore } from '@/stores/authStore'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
const BASE_DELAY          = 1_000
const MAX_DELAY           = 30_000

interface WebSocketContextValue {
  send: (data: string) => void
}

const WebSocketContext = createContext<WebSocketContextValue>({ send: () => {} })

export function useWebSocket() {
  return useContext(WebSocketContext)
}

export default function WebSocketProvider({ children }: { children: ReactNode }) {
  const wsRef             = useRef<WebSocket | null>(null)
  const reconnectRef      = useRef<ReturnType<typeof setTimeout> | null>(null)
  const delayRef          = useRef(BASE_DELAY)
  const mountedRef        = useRef(true)

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
        setStatus('error')
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
      schedule()
    }
  }

  const schedule = () => {
    if (!mountedRef.current) return
    incrementReconnect()
    reconnectRef.current = setTimeout(() => {
      delayRef.current = Math.min(delayRef.current * 2, MAX_DELAY)
      connect()
    }, delayRef.current)
  }

  const send = (data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data)
    }
  }

  useEffect(() => {
    mountedRef.current = true
    if (isAuthenticated) connect()

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
