import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { useRelativeStrength } from '@/hooks/useEngine'
import EmptyState from '@/components/ui/EmptyState'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { RSRanking, RSTier } from '@/types'

const TIER_CONFIG: Record<RSTier, { label: string; text: string; bg: string; border: string }> = {
  high:   { label: 'High',   text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]', border: 'border-[hsl(var(--chart-1)/0.2)]' },
  medium: { label: 'Medium', text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]', border: 'border-[hsl(var(--chart-4)/0.2)]' },
  low:    { label: 'Low',    text: 'text-muted-foreground',       bg: 'bg-muted',                       border: 'border-border'                    },
}

function RSRow({ item, index }: { item: RSRanking; index: number }) {
  const tierCfg  = TIER_CONFIG[item.tier]
  const rsPos    = item.rs >= 0
  const RSIcon   = item.rs > 0.5 ? TrendingUp : item.rs < -0.5 ? TrendingDown : Minus

  return (
    <motion.tr
      initial    = {{ opacity: 0 }}
      animate    = {{ opacity: 1 }}
      transition = {{ delay: index * 0.02 }}
      className  = "table-row"
    >
      <td className="table-cell">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-muted-foreground w-5">{item.rank}</span>
          <span className="font-mono font-semibold text-foreground text-sm">{item.coin}</span>
        </div>
      </td>
      <td className="table-cell">
        <span className={cn(
          'inline-flex items-center rounded border px-1.5 py-px text-xs font-medium',
          tierCfg.text, tierCfg.bg, tierCfg.border
        )}>
          {tierCfg.label}
        </span>
      </td>
      <td className="table-cell">
        <div className="flex items-center gap-1.5">
          <RSIcon className={cn('h-3 w-3', rsPos ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')} />
          <span className={cn(
            'text-xs font-mono font-semibold',
            rsPos ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
          )}>
            {item.rs > 0 ? '+' : ''}{(item.rs ?? 0).toFixed(2)}%
          </span>
        </div>
      </td>
      <td className="table-cell">
        <span className={cn(
          'text-xs font-mono',
          item.vol_ratio >= 1.5 ? 'text-[hsl(var(--chart-1))]' :
          item.vol_ratio >= 1.0 ? 'text-foreground' :
          'text-muted-foreground'
        )}>
          {(item.vol_ratio ?? 0).toFixed(2)}x
        </span>
      </td>
      <td className="table-cell">
        <span className={cn(
          'text-xs font-mono',
          item.adx >= 30 ? 'text-[hsl(var(--chart-1))]' :
          item.adx >= 20 ? 'text-foreground' :
          'text-muted-foreground'
        )}>
          {(item.adx ?? 0).toFixed(0)}
        </span>
      </td>
      <td className="table-cell">
        <div className="flex items-center gap-1">
          <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden">
            <motion.div
              initial    = {{ width: 0 }}
              animate    = {{ width: `${Math.min(100, Math.max(0, (item.total_score + 30) / 60 * 100))}%` }}
              transition = {{ duration: 0.4, ease: 'easeOut' }}
              className  = {cn(
                'h-full rounded-full',
                item.total_score >= 20 ? 'bg-[hsl(var(--chart-1))]' :
                item.total_score >= 0  ? 'bg-[hsl(var(--chart-4))]' :
                'bg-[hsl(var(--chart-2))]'
              )}
            />
          </div>
          <span className="text-xs font-mono text-muted-foreground">
            {(item.total_score ?? 0).toFixed(1)}
          </span>
        </div>
      </td>
    </motion.tr>
  )
}

export default function RelativeStrength() {
  const { data: summary, isLoading } = useRelativeStrength()

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-5 space-y-3">
        <div className="h-4 w-48 rounded shimmer" />
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-8 w-full rounded shimmer" />
        ))}
      </div>
    )
  }

  const ranked = [
    ...(summary?.top_5    ?? []),
    ...(summary?.bottom_5 ?? []),
  ].filter((item, index, self) =>
    index === self.findIndex(t => t.coin === item.coin)
  )

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div>
          <p className="text-sm font-semibold text-foreground">Relative Strength</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {summary?.total ?? 0} coins ranked
          </p>
        </div>
        {summary && (
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--chart-1))]" />
              <span className="text-muted-foreground">High: {summary.high_tier}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--chart-4))]" />
              <span className="text-muted-foreground">Med: {summary.medium_tier}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground" />
              <span className="text-muted-foreground">Low: {summary.low_tier}</span>
            </div>
          </div>
        )}
      </div>

      {ranked.length === 0 ? (
        <EmptyState
          title       = "No ranking data"
          description = "Trigger a scan to populate rankings"
          compact
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px]">
            <thead className="border-b border-border">
              <tr>
                {['Coin', 'Tier', 'RS vs BTC', 'Vol Ratio', 'ADX', 'Score'].map(h => (
                  <th key={h} className="table-header-cell">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {ranked.map((item, i) => (
                <RSRow key={item.coin} item={item} index={i} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
