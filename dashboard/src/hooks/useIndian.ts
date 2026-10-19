import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { indianApi } from '@/lib/endpoints'
import { toast } from 'sonner'

export function useIndianStatus() {
  return useQuery({
    queryKey:        ['indian-status'],
    queryFn:         () => indianApi.status().then(r => r.data),
    refetchInterval: 30_000,
    staleTime:       15_000,
  })
}

export function useIndianSignals(limit = 50) {
  return useQuery({
    queryKey:        ['indian-signals', limit],
    queryFn:         () => indianApi.signals(limit).then(r => r.data),
    refetchInterval: 60_000,
    staleTime:       30_000,
  })
}

export function useIndianPerformance() {
  return useQuery({
    queryKey:        ['indian-performance'],
    queryFn:         () => indianApi.performance().then(r => r.data),
    refetchInterval: 120_000,
    staleTime:       60_000,
  })
}

export function useIndianOrb() {
  return useQuery({
    queryKey:        ['indian-orb'],
    queryFn:         () => indianApi.orb().then(r => r.data),
    refetchInterval: 60_000,
    staleTime:       30_000,
  })
}

export function useIndianSignalJourney(signalId: number | null) {
  return useQuery({
    queryKey:        ['indian-signal-journey', signalId],
    queryFn:         () => indianApi.journey(signalId!).then(r => r.data),
    enabled:         !!signalId,
    staleTime:       30_000,
    refetchInterval: 60_000,
  })
}

export function useSetupOrb() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => indianApi.setupOrb(),
    onSuccess:  () => {
      toast.success('ORB setup triggered')
      queryClient.invalidateQueries({ queryKey: ['indian-status'] })
      queryClient.invalidateQueries({ queryKey: ['indian-orb']    })
    },
    onError: () => toast.error('ORB setup failed'),
  })
}

export function useTriggerIndianScan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => indianApi.scan(),
    onSuccess:  () => {
      toast.success('Scan triggered')
      queryClient.invalidateQueries({ queryKey: ['indian-status']  })
      queryClient.invalidateQueries({ queryKey: ['indian-signals'] })
    },
    onError: () => toast.error('Scan failed'),
  })
}

export function useRefreshIndianData() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => indianApi.refresh(),
    onSuccess:  (data) => {
      const d = data.data
      if (d.rate_limited) {
        toast.error('Rate limited — try again in 2 minutes')
        return
      }
      toast.success('Data refreshed')
      queryClient.invalidateQueries({ queryKey: ['indian-status'] })
    },
    onError: () => toast.error('Refresh failed'),
  })
}