import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { engineApi } from '@/lib/endpoints'
import { useAuthStore } from '@/stores/authStore'
import { toast } from 'sonner'

export function useEngineHealth() {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:        ['engine-health'],
    queryFn:         () => engineApi.health().then(r => r.data),
    enabled:         isAdmin,
    refetchInterval: isAdmin ? 15_000 : false,
    staleTime:       10_000,
  })
}

export function useRejectionStats() {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:        ['engine-rejections'],
    queryFn:         () => engineApi.rejections().then(r => r.data),
    enabled:         isAdmin,
    refetchInterval: isAdmin ? 30_000 : false,
    staleTime:       15_000,
  })
}

export function useRejectionsByCoin(coin: string | null) {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:  ['engine-rejections-coin', coin],
    queryFn:   () => engineApi.rejectionsByCoin(coin!).then(r => r.data),
    enabled:   isAdmin && !!coin,
    staleTime: 30_000,
  })
}

export function useEngineTraces(limit = 50) {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:        ['engine-traces', limit],
    queryFn:         () => engineApi.traces(limit).then(r => r.data),
    enabled:         isAdmin,
    refetchInterval: isAdmin ? 30_000 : false,
    staleTime:       15_000,
  })
}

export function useTracesByCoin(coin: string | null) {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:  ['engine-traces-coin', coin],
    queryFn:   () => engineApi.tracesByCoin(coin!).then(r => r.data),
    enabled:   isAdmin && !!coin,
    staleTime: 30_000,
  })
}

export function useRelativeStrength() {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:        ['engine-rs'],
    queryFn:         () => engineApi.relativeStrength().then(r => r.data),
    enabled:         isAdmin,
    refetchInterval: isAdmin ? 15_000 : false,
    staleTime:       10_000,
  })
}

export function useFilterAnalysis() {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:        ['engine-filter-analysis'],
    queryFn:         () => engineApi.filterAnalysis().then(r => r.data),
    enabled:         isAdmin,
    refetchInterval: isAdmin ? 60_000 : false,
    staleTime:       30_000,
  })
}

export function useMLValidation() {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:        ['engine-ml-validation'],
    queryFn:         () => engineApi.mlValidation().then(r => r.data),
    enabled:         isAdmin,
    refetchInterval: isAdmin ? 60_000 : false,
    staleTime:       30_000,
  })
}

export function useMonthlyReport(year?: number, month?: number) {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:  ['engine-monthly-report', year, month],
    queryFn:   () => engineApi.monthlyReport(year, month).then(r => r.data),
    enabled:   isAdmin,
    staleTime: 300_000,
  })
}

export function useMonthlyHistory(months = 3) {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:  ['engine-monthly-history', months],
    queryFn:   () => engineApi.monthlyHistory(months).then(r => r.data),
    enabled:   isAdmin,
    staleTime: 300_000,
  })
}

export function useFilterReport() {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:        ['engine-filter-report'],
    queryFn:         () => engineApi.filterReport().then(r => r.data),
    enabled:         isAdmin,
    refetchInterval: isAdmin ? 60_000 : false,
    staleTime:       30_000,
  })
}

export function useResetRejections() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (totp_code: string) => engineApi.resetRejections(totp_code),
    onSuccess: () => {
      toast.success('Rejection stats reset')
      queryClient.invalidateQueries({ queryKey: ['engine-rejections']      })
      queryClient.invalidateQueries({ queryKey: ['engine-health']          })
      queryClient.invalidateQueries({ queryKey: ['engine-filter-analysis'] })
    },
    onError: () => toast.error('Failed to reset — invalid TOTP'),
  })
}

export function useEngineScore(coin: string | null) {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:  ['engine-score', coin],
    queryFn:   () => engineApi.score(coin!).then(r => r.data),
    enabled:   isAdmin && !!coin,
    staleTime: 30_000,
  })
}

export function useEngineConfidence(coin: string | null) {
  const { isAdmin } = useAuthStore()

  return useQuery({
    queryKey:  ['engine-confidence', coin],
    queryFn:   () => engineApi.confidence(coin!).then(r => r.data),
    enabled:   isAdmin && !!coin,
    staleTime: 30_000,
  })
}