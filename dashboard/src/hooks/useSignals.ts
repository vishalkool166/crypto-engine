import { useQuery } from '@tanstack/react-query'
import { useWsStore } from '@/stores/wsStore'
import { dashboardApi } from '@/lib/endpoints'
import { useDemoStore } from '@/demo/demoStore'
import { mockRadar, mockQueue, mockSignalHistory } from '@/demo/mockData'
import type { RadarItem, QueueItem } from '@/types'

export interface SignalFeed {
  live:          RadarItem[]
  watching:      RadarItem[]
  idle:          RadarItem[]
  all:           RadarItem[]
  queue:         QueueItem[]
  timestamp:     string
  isLoading:     boolean
  refetch:       () => void
  totalWatching: number
  hasActivity:   boolean
}

function categorize(radar: RadarItem[]): Pick<SignalFeed, 'live' | 'watching' | 'idle' | 'all'> {
  const live:     RadarItem[] = []
  const watching: RadarItem[] = []
  const idle:     RadarItem[] = []

  for (const item of radar) {
    const state    = item.state ?? 'idle'
    const grade    = item.grade ?? '--'
    const isSignal = item.tradeable && ['A+', 'A'].includes(grade)

    if (isSignal) {
      live.push(item)
    } else if (state === 'watching') {
      watching.push(item)
    } else {
      idle.push(item)
    }
  }

  live.sort((a, b)     => (b.score ?? 0) - (a.score ?? 0))
  watching.sort((a, b) => (b.score ?? 0) - (a.score ?? 0))

  return { live, watching, idle, all: radar }
}

export function useSignals(): SignalFeed {
  const { isDemoMode }  = useDemoStore()
  const { lastPayload } = useWsStore()

  const { data: apiData, isLoading, refetch } = useQuery({
    queryKey:        ['dashboard-signals'],
    queryFn:         () => dashboardApi.signals().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 30_000 : false,
    staleTime:       15_000,
  })

  const wsRadar  = !isDemoMode ? (lastPayload?.signals?.radar ?? []) : []
  const apiRadar = apiData?.radar ?? []
  const wsQueue  = !isDemoMode ? (lastPayload?.signals?.queue ?? []) : []
  const apiQueue = apiData?.queue ?? []

  const radar     = isDemoMode ? mockRadar : (wsRadar.length > 0 ? wsRadar : apiRadar)
  const queue     = isDemoMode ? mockQueue : (wsQueue.length > 0 ? wsQueue : apiQueue)
  const timestamp = isDemoMode ? new Date().toISOString() : (lastPayload?.signals?.timestamp ?? apiData?.timestamp ?? '')

  const categorized = categorize(radar)

  return {
    ...categorized,
    queue,
    timestamp,
    isLoading:     !isDemoMode && isLoading,
    refetch,
    totalWatching: categorized.watching.length,
    hasActivity:   categorized.live.length > 0 || categorized.watching.length > 0,
  }
}

export function useSignalHistory(params?: {
  limit?:   number
  grade?:   string
  outcome?: string
  coin?:    string
}) {
  const { limit = 50 } = params ?? {}
  const { isDemoMode }  = useDemoStore()

  return useQuery({
    queryKey:        ['signal-history', limit],
    queryFn:         () => dashboardApi.history(limit).then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 60_000 : false,
    staleTime:       30_000,
    placeholderData: isDemoMode ? mockSignalHistory : undefined,
  })
}

export function useCoinDetail(coin: string | null) {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:  ['coin-detail', coin],
    queryFn:   () => dashboardApi.coinDetail(coin!).then(r => r.data),
    enabled:   !isDemoMode && !!coin,
    staleTime: 30_000,
  })
}