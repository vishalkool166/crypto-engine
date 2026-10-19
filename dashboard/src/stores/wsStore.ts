import { create } from 'zustand'
import type { WsPayload, Summary, TickerItem, Trade } from '@/types'

type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface WsState {
  status:         WsStatus
  lastPayload:    WsPayload | null
  summary:        Summary | null
  ticker:         TickerItem[]
  openTrades:     Trade[]
  lastUpdated:    number | null
  reconnectCount: number
  setStatus:      (status: WsStatus) => void
  setPayload:     (payload: WsPayload) => void
  incrementReconnect: () => void
  resetReconnect:     () => void
}

export const useWsStore = create<WsState>((set) => ({
  status:         'disconnected',
  lastPayload:    null,
  summary:        null,
  ticker:         [],
  openTrades:     [],
  lastUpdated:    null,
  reconnectCount: 0,

  setStatus: (status) => set({ status }),

  setPayload: (payload) => {
    const updates: Partial<WsState> = {
      lastPayload: payload,
      lastUpdated: Date.now(),
    }

    if (payload.summary) {
      updates.summary = payload.summary
    }

    if (payload.ticker && payload.ticker.length > 0) {
      updates.ticker = payload.ticker
    }

    if (payload.open_trades) {
      updates.openTrades = payload.open_trades
    }

    set(updates)
  },

  incrementReconnect: () =>
    set((s) => ({ reconnectCount: s.reconnectCount + 1 })),

  resetReconnect: () => set({ reconnectCount: 0 }),
}))