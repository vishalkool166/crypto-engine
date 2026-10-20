import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { formatCurrency } from '@/lib/utils'
import { pnlColor } from '@/lib/tokens'
import GradeTag from '@/components/ui/GradeTag'
import ScoreBar from '@/components/ui/ScoreBar'
import type { GradeStats } from '@/types'

interface GradeItemProps {
  label: string
  stats: GradeStats | null
}

function GradeItem({ label, stats }: GradeItemProps) {
  return (
    <div className="p-6 space-y-3">
      <div className="flex items-center gap-2">
        <GradeTag grade={label} size="lg" />
        <span className="text-xs text-muted-foreground">
          {stats?.total ?? 0} trades
        </span>
      </div>
      {stats && stats.total > 0 ? (
        <div className="space-y-2">
          <ScoreBar score={stats.win_rate} label="Win Rate" />
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">PnL</span>
            <span className={cn('text-xs font-mono font-semibold', pnlColor(stats.pnl))}>
              {formatCurrency(stats.pnl)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Wins</span>
            <span className="text-xs font-mono text-foreground">
              {stats.wins}/{stats.total}
            </span>
          </div>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No data yet</p>
      )}
    </div>
  )
}

interface Props {
  aplus: GradeStats | null
  a:     GradeStats | null
  b:     GradeStats | null
}

export default function GradeBreakdown({ aplus, a, b }: Props) {
  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="border-b border-border px-6 py-4">
        <p className="text-sm font-semibold text-foreground">Grade Breakdown</p>
      </div>
      <div className="grid grid-cols-1 divide-y md:grid-cols-3 md:divide-x md:divide-y-0 divide-border">
        <GradeItem label="A+" stats={aplus} />
        <GradeItem label="A"  stats={a}     />
        <GradeItem label="B"  stats={b}     />
      </div>
    </div>
  )
}