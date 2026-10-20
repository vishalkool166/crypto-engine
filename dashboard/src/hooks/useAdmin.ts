import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi, systemApi, coinsApi } from '@/lib/endpoints'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { mockCoins, mockAdminStats } from '@/demo/mockData'
import { toast } from 'sonner'

async function runUnlessDemo(isDemoMode: boolean, request: () => Promise<unknown>): Promise<void> {
  if (!isDemoMode) await request()
}

export function useAdminStats() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['admin-stats'],
    queryFn:         () => adminApi.stats().then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? mockAdminStats : undefined,
  })
}

export function useAdminOverview() {
  const { isAdmin }    = useAuthStore()
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['admin-overview'],
    queryFn:         () => adminApi.overview().then(r => r.data),
    enabled:         !isDemoMode && isAdmin,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
  })
}

export function useUsers(params?: { limit?: number; offset?: number; tier?: string; search?: string }) {
  const { limit = 20, offset = 0, tier, search = '' } = params ?? {}
  const { isDemoMode }                   = useDemoStore()

  return useQuery({
    queryKey:        ['admin-users', tier, limit, offset, search],
    queryFn:         () => adminApi.users({ limit, offset, tier: tier !== 'all' ? tier : undefined, search }).then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
    placeholderData: isDemoMode ? { total: 0, users: [] } : undefined,
  })
}

export function useUserDetail(id: number | null) {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:  ['admin-user', id],
    queryFn:   () => adminApi.userById(id!).then(r => r.data),
    enabled:   !isDemoMode && !!id,
    staleTime: 15_000,
  })
}

export function useUpdateTier() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: ({ id, tier }: { id: number; tier: string }) =>
      runUnlessDemo(isDemoMode, () => adminApi.updateTier(id, tier)),
    onSuccess: (_, { id }) => {
      if (isDemoMode) { toast.success('Tier updated (demo)'); return }
      toast.success('Tier updated')
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-user', id] })
    },
    onError: () => toast.error('Failed to update tier'),
  })
}

export function useDeactivateUser() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => runUnlessDemo(isDemoMode, () => adminApi.deactivate(id)),
    onSuccess: (_, id) => {
      if (isDemoMode) { toast.success('User deactivated (demo)'); return }
      toast.success('User deactivated')
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-user', id] })
    },
    onError: () => toast.error('Failed to deactivate user'),
  })
}

export function useReactivateUser() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => runUnlessDemo(isDemoMode, () => adminApi.reactivate(id)),
    onSuccess: (_, id) => {
      if (isDemoMode) { toast.success('User reactivated (demo)'); return }
      toast.success('User reactivated')
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-user', id] })
    },
    onError: () => toast.error('Failed to reactivate user'),
  })
}

export function useRevokeSession() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: (sessionId: string) => runUnlessDemo(isDemoMode, () => adminApi.revokeSession(sessionId)),
    onSuccess: () => {
      if (isDemoMode) { toast.success('Session revoked (demo)'); return }
      toast.success('Session revoked')
      queryClient.invalidateQueries({ queryKey: ['admin-user'] })
    },
    onError: () => toast.error('Failed to revoke session'),
  })
}

export function useRevokeAllSessions() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: (userId: number) => runUnlessDemo(isDemoMode, () => adminApi.revokeAllSessions(userId)),
    onSuccess: () => {
      if (isDemoMode) { toast.success('All sessions revoked (demo)'); return }
      toast.success('All sessions revoked')
      queryClient.invalidateQueries({ queryKey: ['admin-user'] })
    },
    onError: () => toast.error('Failed to revoke sessions'),
  })
}

export function useAuditLog(limit = 50, offset = 0, filters?: { search?: string; actions?: string; success?: boolean }) {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['audit-log', limit, offset, filters?.search, filters?.actions, filters?.success],
    queryFn:         () => adminApi.audit({ limit, offset, ...filters }).then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
  })
}

export function useSystemHealth() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['health'],
    queryFn:         () => systemApi.health().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 15_000 : false,
    staleTime:       10_000,
  })
}

export function useModeStatus() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['mode-status'],
    queryFn:         () => systemApi.modeStatus().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
    placeholderData: isDemoMode
      ? { mode: 'paper' as const, paper: true, grades: ['A+', 'A', 'B'], b_grade_live: false }
      : undefined,
  })
}

export function useToggleMode() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: ({ mode, totp_code }: { mode: string; totp_code: string }) =>
      runUnlessDemo(isDemoMode, () => systemApi.modeToggle(mode, totp_code)),
    onSuccess: (_, { mode }) => {
      if (isDemoMode) { toast.success(`Switched to ${mode} mode (demo)`); return }
      toast.success(`Switched to ${mode} mode`)
      queryClient.invalidateQueries({ queryKey: ['mode-status'] })
      queryClient.invalidateQueries({ queryKey: ['health']      })
    },
    onError: () => { throw new Error('Invalid TOTP or open trades exist') },
  })
}

export function useDockerPurge() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: async (totp_code: string) => {
      if (isDemoMode) return { freed_mb: 0 }
      const response = await systemApi.dockerPurge(totp_code)
      return response.data as { freed_mb: number }
    },
    onSuccess: (data) => {
      if (isDemoMode) { toast.success('Purge complete (demo)'); return }
      toast.success(`Purge complete — freed ${data.freed_mb}MB`)
      queryClient.invalidateQueries({ queryKey: ['health'] })
    },
    onError: () => { throw new Error('Invalid TOTP code') },
  })
}

export function useSyncOutcomes() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: () => runUnlessDemo(isDemoMode, () => systemApi.syncOutcomes()),
    onSuccess: () => {
      if (isDemoMode) { toast.success('Outcomes synced (demo)'); return }
      toast.success('Outcomes synced')
      queryClient.invalidateQueries({ queryKey: ['performance']  })
      queryClient.invalidateQueries({ queryKey: ['signals-list'] })
    },
    onError: () => toast.error('Sync failed'),
  })
}

export function useCoins() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['coins'],
    queryFn:         () => coinsApi.list().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
    placeholderData: isDemoMode ? mockCoins : undefined,
  })
}

export function useToggleCoin() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: ({ coin, enabled }: { coin: string; enabled: boolean }) =>
      runUnlessDemo(isDemoMode, () => coinsApi.toggle(coin, enabled)),
    onSuccess: (_, { coin, enabled }) => {
      toast.success(`${coin} ${enabled ? 'enabled' : 'disabled'}${isDemoMode ? ' (demo)' : ''}`)
      if (!isDemoMode) queryClient.invalidateQueries({ queryKey: ['coins'] })
    },
    onError: () => toast.error('Failed to update coin'),
  })
}

export function useRemoveCoin() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: (coin: string) => runUnlessDemo(isDemoMode, () => coinsApi.remove(coin)),
    onSuccess: (_, coin) => {
      toast.success(`${coin} removed${isDemoMode ? ' (demo)' : ''}`)
      if (!isDemoMode) queryClient.invalidateQueries({ queryKey: ['coins'] })
    },
    onError: () => toast.error('Failed to remove coin'),
  })
}

export function useAddCoin() {
  const { isDemoMode }  = useDemoStore()
  const queryClient     = useQueryClient()

  return useMutation({
    mutationFn: (coin: string) => runUnlessDemo(isDemoMode, () => coinsApi.add(coin)),
    onSuccess: (_, coin) => {
      toast.success(`${coin} added${isDemoMode ? ' (demo)' : ' — backfill started'}`)
      if (!isDemoMode) queryClient.invalidateQueries({ queryKey: ['coins'] })
    },
    onError: () => toast.error('Failed to add coin'),
  })
}
