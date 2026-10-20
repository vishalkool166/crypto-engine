import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { mlApi } from '@/lib/endpoints'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { toast } from 'sonner'

const DEMO_VERSION_HISTORY = [
  {
    version:        'v5.2.1',
    created_at:     new Date(Date.now() - 2 * 86400000).toISOString(),
    change_reason:  'Sweep score threshold adjusted',
    changed_by:     'ml_engine',
    trade_count_at: 138,
    is_current:     true,
    parameters: {
      sweep_min_score:       0.72,
      zone_min_score:        0.68,
      grade_a_threshold:     70,
      grade_aplus_threshold: 82,
      sweep_max_age_hours:   12,
      base_risk_pct:         1.0,
      max_open_trades:       3,
      max_leverage:          10,
    },
  },
  {
    version:        'v5.2.0',
    created_at:     new Date(Date.now() - 8 * 86400000).toISOString(),
    change_reason:  'Zone score threshold adjusted',
    changed_by:     'ml_engine',
    trade_count_at: 96,
    is_current:     false,
    parameters: {
      sweep_min_score:       0.70,
      zone_min_score:        0.65,
      grade_a_threshold:     68,
      grade_aplus_threshold: 80,
      sweep_max_age_hours:   12,
      base_risk_pct:         1.0,
      max_open_trades:       3,
      max_leverage:          10,
    },
  },
]

const DEMO_ML_STATUS = {
  ml_enabled:    true,
  closed_trades: 138,
  required:      100,
  message:       'ML model active',
  cv_auc:        0.74,
  win_rate:      68.4,
  trained_at:    new Date(Date.now() - 2 * 3600000).toISOString(),
  top_features: [
    { feature: 'sweep_score',   importance: 0.284 },
    { feature: 'zone_score',    importance: 0.241 },
    { feature: 'entry_score',   importance: 0.198 },
    { feature: 'market_score',  importance: 0.164 },
    { feature: 'session_score', importance: 0.113 },
  ],
}

export function useMLStatus() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['ml-status'],
    queryFn:         () => mlApi.status().then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
    placeholderData: isDemoMode ? { ml_status: DEMO_ML_STATUS } : undefined,
  })
}

export function useAdaptationHistory(limit = 20) {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['adaptation-history', limit],
    queryFn:         () => mlApi.adaptationHistory(limit).then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? [] : undefined,
  })
}

export function usePendingRecommendations() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['pending-recommendations'],
    queryFn:         () => mlApi.pendingRecommendations().then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
    placeholderData: isDemoMode ? [] : undefined,
  })
}

export function useActiveCheckpoints() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['active-checkpoints'],
    queryFn:         () => mlApi.activeCheckpoints().then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? [] : undefined,
  })
}

export function useVersionHistory(limit = 10) {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['version-history', limit],
    queryFn:         () => mlApi.versionHistory(limit).then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? DEMO_VERSION_HISTORY : undefined,
  })
}

export function usePerformanceByVersion() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['perf-by-version'],
    queryFn:         () => mlApi.performanceByVersion().then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? [
      { version: 'v5.2.1', total: 42, wins: 30, losses: 12, win_rate: 71.4, pnl: 842.40 },
      { version: 'v5.2.0', total: 58, wins: 38, losses: 20, win_rate: 65.5, pnl: 1124.80 },
    ] : undefined,
  })
}

export function usePerformanceByRegime() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['perf-by-regime'],
    queryFn:         () => mlApi.performanceByRegime().then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? [
      { regime: 'trending_bullish', total: 48, wins: 38, losses: 10, win_rate: 79.2, pnl: 1284.40, action: 'normal'      },
      { regime: 'ranging',          total: 42, wins: 26, losses: 16, win_rate: 61.9, pnl: 524.20,  action: 'reduce_size' },
      { regime: 'choppy',           total: 10, wins: 4,  losses: 6,  win_rate: 40.0, pnl: -94.80,  action: 'avoid'       },
    ] : undefined,
  })
}

export function useCurrentParameters() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['current-parameters'],
    queryFn:         () => mlApi.currentParameters().then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
  })
}

export function useApproveRecommendation() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: (id: number) =>
      isDemoMode ? Promise.resolve() : mlApi.approveRecommendation(id).then(() => undefined),
    onSuccess: () => {
      toast.success(isDemoMode ? 'Approved (demo)' : 'Recommendation approved')
      if (!isDemoMode) {
        queryClient.invalidateQueries({ queryKey: ['pending-recommendations'] })
        queryClient.invalidateQueries({ queryKey: ['adaptation-history']      })
      }
    },
    onError: () => toast.error('Failed to approve'),
  })
}

export function useRejectRecommendation() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      isDemoMode ? Promise.resolve() : mlApi.rejectRecommendation(id, reason).then(() => undefined),
    onSuccess: () => {
      toast.success(isDemoMode ? 'Rejected (demo)' : 'Recommendation rejected')
      if (!isDemoMode) {
        queryClient.invalidateQueries({ queryKey: ['pending-recommendations'] })
      }
    },
    onError: () => toast.error('Failed to reject'),
  })
}

export function useManualRollback() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: (parameter: string) =>
      isDemoMode ? Promise.resolve() : mlApi.manualRollback(parameter).then(() => undefined),
    onSuccess: (_, parameter) => {
      toast.success(isDemoMode ? `${parameter} rolled back (demo)` : `${parameter} rolled back`)
      if (!isDemoMode) {
        queryClient.invalidateQueries({ queryKey: ['adaptation-history']   })
        queryClient.invalidateQueries({ queryKey: ['version-history']      })
        queryClient.invalidateQueries({ queryKey: ['current-parameters']   })
        queryClient.invalidateQueries({ queryKey: ['active-checkpoints']   })
      }
    },
    onError: () => { throw new Error('Rollback failed') },
  })
}
