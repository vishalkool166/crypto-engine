import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useWsStore } from '@/stores/wsStore'
import { tradesApi } from '@/lib/endpoints'
import { useDemoStore } from '@/demo/demoStore'
import {
  mockOpenTrades, mockClosedTrades, mockBalance,
  mockProfit, mockDailyPnl, mockCoinPerformance,
} from '@/demo/mockData'
import api from '@/lib/api'

export function useOpenTrades() {
  const { isDemoMode }              = useDemoStore()
  const { openTrades: wsTrades }    = useWsStore()

  const { data: apiTrades, isLoading } = useQuery({
    queryKey:        ['trades-open'],
    queryFn:         () => tradesApi.open().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
  })

  const trades = isDemoMode
    ? mockOpenTrades
    : (wsTrades.length > 0 ? wsTrades : (apiTrades ?? []))

  const totalMargin     = trades.reduce((s, t) => s + (t.margin_used    ?? 0), 0)
  const totalUnrealized = trades.reduce((s, t) => s + (t.profit_abs     ?? 0), 0)
  const longCount       = trades.filter(t => !t.is_short).length
  const shortCount      = trades.filter(t =>  t.is_short).length

  return {
    trades,
    isLoading:     !isDemoMode && isLoading,
    totalMargin,
    totalUnrealized,
    longCount,
    shortCount,
    count:         trades.length,
  }
}

export function useTradeHistory(limit = 20, offset = 0) {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['trades-history', limit, offset],
    queryFn:         () => tradesApi.history(limit, offset).then(r => r.data),
    enabled:         !isDemoMode,
    staleTime:       30_000,
    refetchInterval: !isDemoMode ? 60_000 : false,
    placeholderData: isDemoMode
      ? { trades: mockClosedTrades, trades_count: mockClosedTrades.length, limit, offset }
      : undefined,
  })
}

export function useTradeProfit() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['trades-profit'],
    queryFn:         () => tradesApi.profit().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
    placeholderData: isDemoMode ? mockProfit : undefined,
  })
}

export function useTradeBalance() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['trades-balance'],
    queryFn:         () => tradesApi.balance().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 15_000 : false,
    staleTime:       10_000,
    placeholderData: isDemoMode ? mockBalance : undefined,
  })
}

export function useDailyPnl(days = 7) {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['trades-daily', days],
    queryFn:         () => tradesApi.daily(days).then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? { data: mockDailyPnl } : undefined,
  })
}

export function useCoinPerformance() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['trades-performance'],
    queryFn:         () => tradesApi.performance().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? mockCoinPerformance : undefined,
  })
}

export function useWsStatusTrades() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['trades-ws-status'],
    queryFn:         () => tradesApi.wsStatus().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 10_000 : false,
    staleTime:       5_000,
  })
}

export function useForceSell() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ trade_id, totp_code }: { trade_id: number; totp_code: string }) =>
      tradesApi.forceSell(trade_id, totp_code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trades-open']            })
      queryClient.invalidateQueries({ queryKey: ['trades-history'] })
      queryClient.invalidateQueries({ queryKey: ['trades-history-page'] })
      queryClient.invalidateQueries({ queryKey: ['trades-profit']          })
      queryClient.invalidateQueries({ queryKey: ['trades-balance']         })
    },
  })
}

export function useTradeSummary() {
  const { trades, isLoading: openLoading, totalUnrealized, count } = useOpenTrades()
  const { data: profit,  isLoading: profitLoading  }               = useTradeProfit()
  const { data: balance, isLoading: balanceLoading }               = useTradeBalance()
  const { isDemoMode }                                             = useDemoStore()

  const freeBalance  = balance?.free  ?? 0
  const totalBalance = balance?.total ?? 0
  const usedBalance  = balance?.used  ?? 0

  return {
    trades,
    profit,
    balance,
    totalUnrealized,
    openCount:    count,
    isLoading:    !isDemoMode && (openLoading || profitLoading || balanceLoading),
    freeBalance,
    totalBalance,
    usedBalance,
    totalPnl:     profit?.profit_all_coin ?? 0,
    winRate:      profit ? profit.winrate * 100 : 0,
    tradeCount:   profit?.trade_count ?? 0,
  }
}

export function useTradeJourney(tradeId: number | null) {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['trade-journey', tradeId],
    queryFn:         () => api.get(`/api/trades/${tradeId}/journey`).then(r => r.data),
    enabled:         !isDemoMode && !!tradeId,
    staleTime:       30_000,
    refetchInterval: 60_000,
  })
}
