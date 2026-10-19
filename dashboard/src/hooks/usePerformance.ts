import { useQuery } from '@tanstack/react-query'
import { dashboardApi, performanceApi, signalsApi } from '@/lib/endpoints'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { mockPerformance, mockSignalHistory } from '@/demo/mockData'

export function usePerformance() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['performance'],
    queryFn:         () => dashboardApi.performance().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? mockPerformance : undefined,
  })
}

export function useFactorAnalysis() {
  const { hasFeature, isAdmin } = useAuthStore()
  const { isDemoMode }          = useDemoStore()
  const enabled                 = !isDemoMode && (hasFeature('show_factors') || isAdmin)

  return useQuery({
    queryKey:  ['factor-analysis'],
    queryFn:   () => performanceApi.factorAnalysis().then(r => r.data),
    enabled,
    staleTime: 300_000,
  })
}

export function useBacktestHistory() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:  ['backtest-history'],
    queryFn:   () => performanceApi.backtestHistory().then(r => r.data),
    enabled:   !isDemoMode,
    staleTime: 300_000,
  })
}

export function useRunBacktest(coin: string | null) {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:  ['backtest', coin],
    queryFn:   () => performanceApi.backtest(coin!).then(r => r.data),
    enabled:   !isDemoMode && !!coin,
    staleTime: 300_000,
    retry:     false,
  })
}

export function useSignalHistory(params?: {
  limit?:   number
  grade?:   string
  outcome?: string
  coin?:    string
}) {
  const { limit = 50, grade, outcome, coin } = params ?? {}
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['signals-list', limit, grade, outcome, coin],
    queryFn:         () => signalsApi.list({
      limit,
      grade:   grade   !== 'all' ? grade   : undefined,
      outcome: outcome !== 'all' ? outcome : undefined,
      coin:    coin    || undefined,
    }).then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? mockSignalHistory : undefined,
  })
}

export function usePerformanceSummary() {
  const { isDemoMode }            = useDemoStore()
  const { data: perf, isLoading } = usePerformance()

  const resolved = isDemoMode ? mockPerformance : perf

  if (!resolved) {
    return {
      isLoading,
      perf:         null,
      winRate:      0,
      totalPnl:     0,
      profitFactor: 0,
      maxDrawdown:  0,
      closed:       0,
      equityCurve:  [] as Array<{ date: string; pnl: number; equity: number }>,
      gradeStats: {
        aplus: null as null | { win_rate: number; wins: number; total: number; pnl: number },
        a:     null as null | { win_rate: number; wins: number; total: number; pnl: number },
        b:     null as null | { win_rate: number; wins: number; total: number; pnl: number },
      },
    }
  }

  return {
    isLoading:    !isDemoMode && isLoading,
    perf:         resolved,
    winRate:      resolved.win_rate,
    totalPnl:     resolved.total_pnl,
    profitFactor: resolved.profit_factor,
    maxDrawdown:  resolved.max_drawdown,
    closed:       resolved.closed,
    equityCurve:  resolved.equity_curve ?? [],
    gradeStats: {
      aplus: resolved.aplus,
      a:     resolved.a,
      b:     resolved.b,
    },
  }
}

export function usePerformanceByVersion() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['perf-by-version'],
    queryFn:         () => import('@/lib/endpoints').then(m => m.mlApi.performanceByVersion()).then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
  })
}

export function usePerformanceByRegime() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['perf-by-regime'],
    queryFn:         () => import('@/lib/endpoints').then(m => m.mlApi.performanceByRegime()).then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
  })
}