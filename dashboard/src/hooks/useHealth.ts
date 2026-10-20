import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { systemApi } from '@/lib/endpoints'
import { useWsStore } from '@/stores/wsStore'
import { useDemoStore } from '@/demo/demoStore'
import { mockSummary, mockTicker } from '@/demo/mockData'

export function useHealth() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['health'],
    queryFn:         () => systemApi.health().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 15_000 : false,
    staleTime:       10_000,
  })
}

export function useWsStatus() {
  const { isDemoMode } = useDemoStore()

  return useQuery({
    queryKey:        ['ws-status'],
    queryFn:         () => systemApi.wsStatus().then(r => r.data),
    enabled:         !isDemoMode,
    refetchInterval: !isDemoMode ? 10_000 : false,
    staleTime:       5_000,
  })
}

export function useSystemStatus() {
  const { isDemoMode }              = useDemoStore()
  const { status: wsStatus }        = useWsStore()
  const { data: health, isLoading } = useHealth()
  const { data: wsData }            = useWsStatus()

  if (isDemoMode) {
    return {
      isLoading:      false,
      wsConnected:    true,
      redisConnected: true,
      engineOk:       true,
      mlEnabled:      true,
      mlProgress: {
        closed:   138,
        required: 100,
        pct:      100,
        message:  'ML model active — 138 closed trades',
      },
      tradingMode:  'paper' as const,
      coinsCount:   24,
      grades:       ['A+', 'A', 'B'],
      wsStreams: {
        markPrice: true,
        userData:  true,
        kline:     true,
        ticker:    true,
        cached:    24,
      },
      system: {
        cpuPct:      24.8,
        ramPct:      48.2,
        ramUsedMb:   1964,
        ramTotalMb:  4096,
        diskPct:     38.4,
        diskUsedGb:  19.2,
        diskTotalGb: 50.0,
        uptimeStr:   '14d 6h 22m',
        containers:  [
          { name: 'signal-engine', status: 'running', mem_mb: 412,  mem_pct: 10.1, cpu_pct: 8.4 },
          { name: 'redis',         status: 'running', mem_mb: 84,   mem_pct: 2.1,  cpu_pct: 0.4 },
        ],
      },
      alerts: [],
    }
  }

  const system = health?.system

  return {
    isLoading,
    wsConnected:    wsStatus === 'connected',
    redisConnected: health?.redis_connected    ?? false,
    engineOk:       health?.status === 'ok',
    mlEnabled:      health?.ml_status?.ml_enabled ?? false,
    mlProgress: {
      closed:   health?.ml_status?.closed_trades ?? 0,
      required: health?.ml_status?.required      ?? 100,
      pct:      health?.ml_status
        ? Math.min(100, Math.round((health.ml_status.closed_trades / health.ml_status.required) * 100))
        : 0,
      message: health?.ml_status?.message ?? '',
    },
    tradingMode:  health?.trading_mode ?? 'paper',
    coinsCount:   health?.coins_count  ?? 0,
    grades:       health?.grades       ?? [],
    wsStreams: {
      markPrice: wsData?.mark_price_connected  ?? false,
      userData:  wsData?.user_data_connected   ?? false,
      kline:     wsData?.kline_ws_connected    ?? false,
      ticker:    wsData?.ticker_ws_connected   ?? false,
      cached:    wsData?.prices_cached         ?? 0,
    },
    system: system ? {
      cpuPct:      system.cpu_pct,
      ramPct:      system.ram_pct,
      ramUsedMb:   system.ram_used_mb,
      ramTotalMb:  system.ram_total_mb,
      diskPct:     system.disk_pct,
      diskUsedGb:  system.disk_used_gb,
      diskTotalGb: system.disk_total_gb,
      uptimeStr:   system.uptime_str,
      containers:  system.containers ?? [],
    } : null,
    alerts: _buildAlerts(health, system),
  }
}

function _buildAlerts(health: unknown, system: unknown): string[] {
  const alerts: string[] = []
  const h = health as Record<string, unknown> | undefined
  const s = system as Record<string, unknown> | undefined
  if (!h?.redis_connected)               alerts.push('Redis disconnected')
  if (s && (s.cpu_pct  as number) > 90)  alerts.push(`CPU critical: ${s.cpu_pct}%`)
  if (s && (s.ram_pct  as number) > 90)  alerts.push(`RAM critical: ${s.ram_pct}%`)
  if (s && (s.disk_pct as number) > 85)  alerts.push(`Disk high: ${s.disk_pct}%`)
  return alerts
}

export function useScanStatus() {
  const { isDemoMode }                = useDemoStore()
  const { summary: realSummary }      = useWsStore()
  const [countdown, setCountdown]     = useState('—')

  const summary = isDemoMode ? mockSummary : realSummary

  useEffect(() => {
    const update = () => {
      const epoch = summary?.next_scan_epoch ?? 0
      if (!epoch) { setCountdown('—'); return }
      const diff = epoch - Date.now()
      const secs = Math.max(0, Math.floor(diff / 1000))
      const mins = Math.floor(secs / 60)
      const s    = secs % 60
      setCountdown(secs <= 0 ? 'Now' : `${mins}:${s.toString().padStart(2, '0')}`)
    }
    update()
    const id = setInterval(update, 1_000)
    return () => clearInterval(id)
  }, [summary?.next_scan_epoch])

  return {
    countdown,
    mode:          summary?.mode          ?? 'paper',
    coinsCount:    summary?.coins_count   ?? 0,
    watchingCount: summary?.watching_count ?? 0,
    inTradeCount:  summary?.in_trade_count ?? 0,
    cooldownCount: summary?.cooldown_count ?? 0,
    grades:        summary?.grades        ?? [],
    isDemoMode,
  }
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