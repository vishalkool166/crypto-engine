import { useState } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { useRejectionStats } from '@/hooks/useEngine'
import EmptyState from '@/components/ui/EmptyState'
import { BarChart3 } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

const TABS = [
  { label: 'Total',  value: 'total'  },
  { label: 'Weekly', value: 'weekly' },
  { label: 'Daily',  value: 'daily'  },
]

function RejectionBar({ reason, count, pct, max }: { reason: string; count: number; pct: number; max: number }) {
  const severity =
    pct > 30 ? 'bg-[hsl(var(--chart-2))]' :
    pct > 15 ? 'bg-[hsl(var(--chart-4))]' :
    'bg-[hsl(var(--chart-3))]'

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-foreground truncate capitalize">
          {reason.replace(/_/g, ' ')}
        </span>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs font-mono text-muted-foreground">{count}</span>
          <span className={cn(
            'text-xs font-mono font-semibold w-10 text-right',
            pct > 30 ? 'text-[hsl(var(--chart-2))]' :
            pct > 15 ? 'text-[hsl(var(--chart-4))]' :
            'text-foreground'
          )}>
            {pct}%
          </span>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <motion.div
          initial    = {{ width: 0 }}
          animate    = {{ width: `${(count / max) * 100}%` }}
          transition = {{ duration: 0.5, ease: 'easeOut' }}
          className  = {cn('h-full rounded-full', severity)}
        />
      </div>
    </div>
  )
}

export default function RejectionStats() {
  const [tab, setTab]           = useState('total')
  const { data, isLoading }     = useRejectionStats()

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-5 space-y-3">
        <div className="h-4 w-40 rounded shimmer" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="space-y-1">
            <div className="h-3 w-full rounded shimmer" />
            <div className="h-1.5 w-full rounded shimmer" />
          </div>
        ))}
      </div>
    )
  }

  const totalStats  = data?.total
  const weeklyStats = data?.weekly
  const dailyStats  = data?.daily ?? []

  const activeStats = tab === 'total'
    ? totalStats?.by_reason
    : tab === 'weekly'
    ? (weeklyStats as { by_reason?: Record<string, { count: number; pct: number }> } | undefined)?.by_reason
    : null

  const summaryStats = tab === 'total' ? totalStats : tab === 'weekly' ? weeklyStats : null

  const chartData = dailyStats.slice(-7).map((d: { date: string; total: number }) => ({
    date:  d.date.slice(5),
    total: d.total,
  }))

  const entries = activeStats
    ? Object.entries(activeStats as Record<string, { count: number; pct: number }>)
        .sort(([, a], [, b]) => b.count - a.count)
        .slice(0, 10)
    : []

  const maxCount = entries.length > 0 ? entries[0][1].count : 1

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <p className="text-sm font-semibold text-foreground">Rejection Statistics</p>
        <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
          {TABS.map(t => (
            <button
              key       = {t.value}
              onClick   = {() => setTab(t.value)}
              className = {cn(
                'px-3 py-1.5 text-xs font-medium transition-colors',
                tab === t.value
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground bg-background'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {summaryStats && (
        <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
          {[
            { label: 'Total Scans',   value: (summaryStats as { total_scans?: number }).total_scans    ?? 0 },
            { label: 'Signals',       value: (summaryStats as { total_signals?: number }).total_signals ?? 0 },
            { label: 'Signal Rate',   value: `${(summaryStats as { signal_rate?: number }).signal_rate ?? 0}%` },
          ].map(item => (
            <div key={item.label} className="px-4 py-3 text-center">
              <p className="label-xs">{item.label}</p>
              <p className="text-sm font-mono font-semibold text-foreground mt-1">{item.value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="p-5">
        {tab === 'daily' ? (
          chartData.length === 0 ? (
            <EmptyState icon={BarChart3} title="No daily data" compact />
          ) : (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} barSize={20}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis
                    dataKey  = "date"
                    tick     = {{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine = {false}
                    tickLine = {false}
                  />
                  <YAxis
                    tick     = {{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine = {false}
                    tickLine = {false}
                  />
                  <Tooltip
                    contentStyle = {{
                      backgroundColor: 'hsl(var(--card))',
                      border:          '1px solid hsl(var(--border))',
                      borderRadius:    '6px',
                      fontSize:        '12px',
                    }}
                  />
                  <Bar dataKey="total" radius={[3, 3, 0, 0]}>
                    {chartData.map((_: unknown, i: number) => (
                      <Cell key={i} fill="hsl(var(--chart-3))" />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )
        ) : entries.length === 0 ? (
          <EmptyState icon={BarChart3} title="No rejection data yet" description="Data appears after first scan" compact />
        ) : (
          <div className="space-y-3">
            {entries.map(([reason, data]) => (
              <RejectionBar
                key    = {reason}
                reason = {reason}
                count  = {data.count}
                pct    = {data.pct}
                max    = {maxCount}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}