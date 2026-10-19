import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { useFilterReport } from '@/hooks/useEngine'
import EmptyState from '@/components/ui/EmptyState'
import { BarChart3, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import type { FilterBottleneck } from '@/types'

const SEVERITY_CONFIG = {
  critical: { text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]', border: 'border-[hsl(var(--chart-2)/0.2)]', icon: AlertTriangle },
  high:     { text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]', border: 'border-[hsl(var(--chart-4)/0.2)]', icon: AlertTriangle },
  medium:   { text: 'text-[hsl(var(--chart-3))]', bg: 'bg-[hsl(var(--chart-3)/0.08)]', border: 'border-[hsl(var(--chart-3)/0.2)]', icon: Info         },
  low:      { text: 'text-muted-foreground',       bg: 'bg-muted',                       border: 'border-border',                    icon: CheckCircle  },
}

function BottleneckRow({ item, index }: { item: FilterBottleneck; index: number }) {
  const cfg  = SEVERITY_CONFIG[item.severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.low
  const Icon = cfg.icon

  return (
    <motion.div
      initial    = {{ opacity: 0, x: -4 }}
      animate    = {{ opacity: 1, x: 0  }}
      transition = {{ delay: index * 0.04 }}
      className  = {cn('rounded-lg border p-4 space-y-2', cfg.bg, cfg.border)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className={cn('h-3.5 w-3.5 shrink-0', cfg.text)} />
          <span className="text-sm font-mono font-semibold text-foreground capitalize">
            {item.filter.replace(/_/g, ' ')}
          </span>
          <span className={cn(
            'inline-flex items-center rounded border px-1.5 py-px text-xs font-medium capitalize',
            cfg.text, cfg.bg, cfg.border
          )}>
            {item.severity}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-mono text-muted-foreground">{item.count}</span>
          <span className={cn('text-xs font-mono font-semibold', cfg.text)}>
            {item.pct}%
          </span>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted/50 overflow-hidden">
        <motion.div
          initial    = {{ width: 0 }}
          animate    = {{ width: `${item.pct}%` }}
          transition = {{ duration: 0.5, ease: 'easeOut', delay: index * 0.04 }}
          className  = {cn(
            'h-full rounded-full',
            item.severity === 'critical' ? 'bg-[hsl(var(--chart-2))]' :
            item.severity === 'high'     ? 'bg-[hsl(var(--chart-4))]' :
            item.severity === 'medium'   ? 'bg-[hsl(var(--chart-3))]' :
            'bg-muted-foreground/40'
          )}
        />
      </div>
      {item.action && (
        <p className="text-xs text-muted-foreground leading-relaxed">
          {item.action}
        </p>
      )}
    </motion.div>
  )
}

export default function FilterAnalysis() {
  const { data: report, isLoading } = useFilterReport()

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-20 w-full rounded-lg border border-border shimmer" />
        ))}
      </div>
    )
  }

  if (!report) {
    return (
      <EmptyState
        icon        = {BarChart3}
        title       = "No filter analysis data"
        description = "Run a scan to generate filter analysis"
        compact
      />
    )
  }

  const bottlenecks    = report.filter_analysis ?? []
  const recommendations= report.recommendations ?? []
  const totalScans     = report.total_scans     ?? 0
  const totalSignals   = report.total_signals   ?? 0
  const signalRate     = report.signal_rate     ?? 0

  const signalRateColor =
    signalRate >= 3 ? 'text-[hsl(var(--chart-1))]' :
    signalRate >= 1 ? 'text-[hsl(var(--chart-4))]' :
    'text-[hsl(var(--chart-2))]'

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-lg border border-border bg-card p-4 text-center">
          <p className="label-xs">Total Scans</p>
          <p className="text-lg font-mono font-semibold text-foreground mt-1">{totalScans}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 text-center">
          <p className="label-xs">Signals</p>
          <p className="text-lg font-mono font-semibold text-foreground mt-1">{totalSignals}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 text-center">
          <p className="label-xs">Signal Rate</p>
          <p className={cn('text-lg font-mono font-semibold mt-1', signalRateColor)}>
            {signalRate}%
          </p>
        </div>
      </div>

      {recommendations.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-semibold text-foreground">Recommendations</p>
          {recommendations.map((rec, i) => (
            <div
              key       = {i}
              className = {cn(
                'flex items-start gap-3 rounded-lg border p-3',
                rec.priority === 'critical' || rec.priority === 'high'
                  ? 'border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.04)]'
                  : 'border-border bg-muted/30'
              )}
            >
              <AlertTriangle className={cn(
                'h-3.5 w-3.5 shrink-0 mt-0.5',
                rec.priority === 'critical' || rec.priority === 'high'
                  ? 'text-[hsl(var(--chart-2))]'
                  : 'text-[hsl(var(--chart-4))]'
              )} />
              <p className="text-xs text-foreground leading-relaxed">{rec.message}</p>
            </div>
          ))}
        </div>
      )}

      {bottlenecks.length === 0 ? (
        <EmptyState
          icon        = {CheckCircle}
          title       = "No bottlenecks detected"
          description = "All filters are performing normally"
          compact
        />
      ) : (
        <div className="space-y-2">
          <p className="text-sm font-semibold text-foreground">
            Filter Bottlenecks
            <span className="ml-2 label-xs">{bottlenecks.length} filters</span>
          </p>
          {bottlenecks.map((item, i) => (
            <BottleneckRow key={item.filter} item={item} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}