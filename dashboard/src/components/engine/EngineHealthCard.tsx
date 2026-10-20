import { motion } from 'framer-motion'
import { Activity } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useEngineHealth } from '@/hooks/useEngine'

function StatItem({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn('text-xs font-mono font-semibold', color ?? 'text-foreground')}>
        {value}
      </span>
    </div>
  )
}

export default function EngineHealthCard() {
  const { data: health, isLoading } = useEngineHealth()

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-5 space-y-3">
        <div className="h-4 w-32 rounded shimmer" />
        <div className="h-3 w-full rounded shimmer" />
        <div className="h-3 w-3/4 rounded shimmer" />
      </div>
    )
  }

  if (!health) return null

  const signalRateColor =
    health.signal_rate >= 3 ? 'text-[hsl(var(--chart-1))]' :
    health.signal_rate >= 1 ? 'text-[hsl(var(--chart-4))]' :
    'text-[hsl(var(--chart-2))]'

  const btcColor =
    health.btc_cls === 'bull' ? 'text-[hsl(var(--chart-1))]' :
    health.btc_cls === 'bear' ? 'text-[hsl(var(--chart-2))]' :
    'text-muted-foreground'

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center gap-2.5 border-b border-border px-5 py-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted">
          <Activity className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
        <p className="text-sm font-semibold text-foreground">Engine Health</p>
        <div className="ml-auto flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--chart-1))] animate-pulse-dot" />
          <span className="text-xs text-[hsl(var(--chart-1))]">Live</span>
        </div>
      </div>

      <div className="p-5 space-y-1">
        <StatItem label="Coins Scanned"   value={health.coins_scanned} />
        <StatItem label="Signals Today"   value={health.signals_today} />
        <StatItem label="Total Scans"     value={health.total_scans} />
        <StatItem
          label = "Signal Rate"
          value = {`${health.signal_rate}%`}
          color = {signalRateColor}
        />
        <StatItem label="Avg Scan Time"   value={`${health.avg_scan_ms}ms`} />
        <StatItem label="Avg Score"       value={`${health.avg_score}/100`} />
        <StatItem label="Dominant Regime" value={health.dominant_regime} />
        <StatItem
          label = "BTC"
          value = {`${health.btc_cls} · ADX ${(health.btc_adx ?? 0).toFixed(0)}`}
          color = {btcColor}
        />
      </div>

      {health.top_rejections && health.top_rejections.length > 0 && (
        <div className="border-t border-border px-5 py-4 space-y-2">
          <p className="label-xs">Top Rejections</p>
          {health.top_rejections.slice(0, 3).map((r, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{r.reason.replace(/_/g, ' ')}</span>
                <span className="text-xs font-mono text-foreground">{r.pct}%</span>
              </div>
              <div className="h-1 w-full rounded-full bg-muted overflow-hidden">
                <motion.div
                  initial    = {{ width: 0 }}
                  animate    = {{ width: `${r.pct}%` }}
                  transition = {{ duration: 0.5, ease: 'easeOut', delay: i * 0.1 }}
                  className  = {cn(
                    'h-full rounded-full',
                    r.pct > 30 ? 'bg-[hsl(var(--chart-2))]' :
                    r.pct > 15 ? 'bg-[hsl(var(--chart-4))]' :
                    'bg-muted-foreground/40'
                  )}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
