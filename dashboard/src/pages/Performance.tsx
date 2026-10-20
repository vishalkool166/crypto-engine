import { useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, TrendingUp, TrendingDown, Target, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { pnlColor, scoreToColor } from '@/lib/tokens'
import {
  usePerformanceSummary, useFactorAnalysis,
  useSignalHistory, useRunBacktest,
  usePerformanceByVersion, usePerformanceByRegime,
} from '@/hooks/usePerformance'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import KPICard from '@/components/ui/KPICard'
import EmptyState from '@/components/ui/EmptyState'
import { LockedSection } from '@/components/ui/TierGate'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import EquityCurve from '@/components/performance/EquityCurve'
import GradeBreakdown from '@/components/performance/GradeBreakdown'
import SignalHistoryTable from '@/components/performance/SignalHistoryTable'
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
} from 'recharts'

const ACTION_STYLES: Record<string, { text: string; bg: string; border: string }> = {
  avoid:       { text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]', border: 'border-[hsl(var(--chart-2)/0.2)]' },
  reduce_size: { text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]', border: 'border-[hsl(var(--chart-4)/0.2)]' },
  normal:      { text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]', border: 'border-[hsl(var(--chart-1)/0.2)]' },
}

export default function Performance() {
  const { hasFeature, isAdmin }         = useAuthStore()
  const { isDemoMode }                  = useDemoStore()
  const [backtestCoin, setBacktestCoin] = useState('')
  const [runCoin,      setRunCoin]      = useState<string | null>(null)

  const showPerformance = hasFeature('show_performance') || isAdmin
  const showFactors     = hasFeature('show_factors')     || isAdmin
  const showBacktest    = hasFeature('backtest_access')  || isAdmin

  const { perf, isLoading, equityCurve, gradeStats } = usePerformanceSummary()
  const { data: factors }                             = useFactorAnalysis()
  const { data: history, isLoading: histLoading }     = useSignalHistory({ limit: 500 })
  const { data: btResult, isLoading: btLoading }      = useRunBacktest(runCoin)
  const { data: versionPerf }                         = usePerformanceByVersion()
  const { data: regimePerf }                          = usePerformanceByRegime()

  if (isLoading) return <PageSkeleton />

  if (!showPerformance) {
    return (
      <div className="p-4 md:p-6">
        <div className="mb-6">
          <h1 className="text-base font-semibold text-foreground">Performance</h1>
        </div>
        <LockedSection
          requiredTier = "pro"
          title        = "Performance Analytics"
          description  = "Upgrade to Pro to access win rate, equity curve, and trade history"
          rows         = {5}
        />
      </div>
    )
  }

  if (!perf) {
    return (
      <div className="p-4 md:p-6">
        <div className="mb-6">
          <h1 className="text-base font-semibold text-foreground">Performance</h1>
        </div>
        <EmptyState
          icon        = {BarChart3}
          title       = "No closed trades yet"
          description = "Performance data appears after your first closed trade"
        />
      </div>
    )
  }

  const pieData = [
    { name: 'Wins',   value: perf.wins,   fill: 'hsl(var(--chart-1))' },
    { name: 'Losses', value: perf.losses, fill: 'hsl(var(--muted))'   },
  ]

  const versionList = Array.isArray(versionPerf) ? versionPerf : []
  const regimeList  = Array.isArray(regimePerf)  ? regimePerf  : []

  return (
    <div className="p-4 md:p-6 space-y-6">

      <div>
        <h1 className="text-base font-semibold text-foreground">Performance</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {perf.closed} closed signals · All-time analytics
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
        <KPICard
          title          = "Win Rate"
          value          = {formatPercent(perf.win_rate, false)}
          sub            = {`${perf.wins}W / ${perf.losses}L`}
          icon           = {Target}
          valueClassName = {perf.win_rate >= 50 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'}
        />
        <KPICard
          title          = "Total PnL"
          value          = {formatCurrency(perf.total_pnl)}
          sub            = {`${perf.closed} closed`}
          icon           = {perf.total_pnl_pos ? TrendingUp : TrendingDown}
          valueClassName = {perf.total_pnl_pos ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'}
        />
        <KPICard
          title = "Profit Factor"
          value = {(perf.profit_factor ?? 0).toFixed(2)}
          sub   = {`Gross P: ${formatCurrency(perf.gross_profit, 0)}`}
          icon  = {BarChart3}
        />
        <KPICard
          title          = "Max Drawdown"
          value          = {formatPercent(perf.max_drawdown, false)}
          sub            = {`Peak: ${formatCurrency(perf.peak_equity)}`}
          icon           = {AlertTriangle}
          valueClassName = {
            perf.max_drawdown > 20 ? 'text-[hsl(var(--chart-2))]' :
            perf.max_drawdown > 10 ? 'text-[hsl(var(--chart-4))]' :
            'text-foreground'
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <EquityCurve equityCurve={equityCurve} totalPnl={perf.total_pnl} />
        </div>
        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-6 py-4">
            <p className="text-sm font-semibold text-foreground">Win / Loss</p>
          </div>
          <div className="flex flex-col items-center justify-center p-4 h-56">
            {perf.closed === 0 ? (
              <EmptyState title="No closed trades" compact />
            ) : (
              <>
                <ResponsiveContainer width="100%" height={140}>
                  <PieChart>
                    <Pie
                      data        = {pieData}
                      cx          = "50%"
                      cy          = "50%"
                      innerRadius = {42}
                      outerRadius = {60}
                      paddingAngle= {2}
                      dataKey     = "value"
                      startAngle  = {90}
                      endAngle    = {-270}
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} strokeWidth={0} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <p className="value-md text-foreground -mt-2">
                  {formatPercent(perf.win_rate, false)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {perf.wins}W / {perf.losses}L
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      <GradeBreakdown aplus={gradeStats.aplus} a={gradeStats.a} b={gradeStats.b} />

      {versionList.length > 0 && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="border-b border-border px-6 py-4">
            <p className="text-sm font-semibold text-foreground">Performance by Version</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[400px]">
              <thead className="border-b border-border">
                <tr>
                  {['Version', 'Trades', 'Win Rate', 'PnL'].map(h => (
                    <th key={h} className="table-header-cell">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {versionList.map((v: { version: string; total: number; win_rate: number; pnl: number }) => (
                  <tr key={v.version} className="table-row">
                    <td className="table-cell font-mono text-xs font-semibold text-foreground">{v.version}</td>
                    <td className="table-cell font-mono text-xs text-muted-foreground">{v.total}</td>
                    <td className="table-cell">
                      <span className={cn('font-mono text-xs', v.win_rate >= 50 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')}>
                        {(v.win_rate ?? 0).toFixed(1)}%
                      </span>
                    </td>
                    <td className="table-cell">
                      <span className={cn('font-mono text-xs', pnlColor(v.pnl))}>
                        {formatCurrency(v.pnl)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {regimeList.length > 0 && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="border-b border-border px-6 py-4">
            <p className="text-sm font-semibold text-foreground">Performance by Regime</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px]">
              <thead className="border-b border-border">
                <tr>
                  {['Regime', 'Trades', 'Win Rate', 'PnL', 'Recommendation'].map(h => (
                    <th key={h} className="table-header-cell">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {regimeList.map((r: { regime: string; total: number; win_rate: number; pnl: number; action: string }) => {
                  const actionStyle = ACTION_STYLES[r.action] ?? ACTION_STYLES.normal
                  return (
                    <tr key={r.regime} className="table-row">
                      <td className="table-cell font-medium text-sm capitalize">{r.regime.replace(/_/g, ' ')}</td>
                      <td className="table-cell font-mono text-xs text-muted-foreground">{r.total}</td>
                      <td className="table-cell">
                        <span className={cn('font-mono text-xs', r.win_rate >= 50 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')}>
                          {(r.win_rate ?? 0).toFixed(1)}%
                        </span>
                      </td>
                      <td className="table-cell">
                        <span className={cn('font-mono text-xs', pnlColor(r.pnl))}>
                          {formatCurrency(r.pnl)}
                        </span>
                      </td>
                      <td className="table-cell">
                        <span className={cn('inline-flex items-center rounded border px-1.5 py-px text-xs font-medium capitalize', actionStyle.text, actionStyle.bg, actionStyle.border)}>
                          {r.action.replace(/_/g, ' ')}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showFactors && factors && (factors as { total?: number }).total && (factors as { total: number }).total > 0 ? (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="border-b border-border px-6 py-4 flex items-center justify-between flex-wrap gap-2">
            <p className="text-sm font-semibold text-foreground">Factor Analysis</p>
            <span className={cn(
              'text-xs px-2 py-0.5 rounded-md font-medium border',
              (factors as { reliable?: boolean }).reliable
                ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.06)] text-[hsl(var(--chart-1))]'
                : 'border-[hsl(var(--chart-4)/0.2)] bg-[hsl(var(--chart-4)/0.06)] text-[hsl(var(--chart-4))]'
            )}>
              {(factors as { reliability?: string }).reliability}
            </span>
          </div>
          <div className="p-6 space-y-3">
            {(factors as { table?: Array<{ factor: string; win_rate_present: number | null; edge: number | null }> }).table?.map(row => (
              <div key={row.factor} className="space-y-1">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <span className="text-xs text-foreground capitalize">{row.factor.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-4">
                    {row.win_rate_present !== null && (
                      <span className="text-xs text-muted-foreground">
                        Present: <span className={cn('font-mono font-medium', scoreToColor(row.win_rate_present))}>
                          {(row.win_rate_present ?? 0).toFixed(0)}%
                        </span>
                      </span>
                    )}
                    {row.edge !== null && (
                      <span className={cn(
                        'text-xs font-mono font-semibold',
                        row.edge > 10 ? 'text-[hsl(var(--chart-1))]' :
                        row.edge > 0  ? 'text-[hsl(var(--chart-3))]' :
                        'text-[hsl(var(--chart-2))]'
                      )}>
                        {row.edge > 0 ? '+' : ''}{(row.edge ?? 0).toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
                <div className="h-1 w-full rounded-full bg-muted overflow-hidden">
                  <motion.div
                    initial    = {{ width: 0 }}
                    animate    = {{ width: `${row.win_rate_present ?? 0}%` }}
                    transition = {{ duration: 0.5, ease: 'easeOut' }}
                    className  = {cn(
                      'h-full rounded-full',
                      (row.win_rate_present ?? 0) >= 60 ? 'bg-[hsl(var(--chart-1))]' :
                      (row.win_rate_present ?? 0) >= 45 ? 'bg-[hsl(var(--chart-4))]' :
                      'bg-[hsl(var(--chart-2))]'
                    )}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : !showFactors ? (
        <LockedSection
          requiredTier = "elite"
          title        = "Factor Analysis"
          description  = "See which confluence factors actually drive wins"
          rows         = {4}
        />
      ) : null}

      {showBacktest ? (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="border-b border-border px-6 py-4">
            <p className="text-sm font-semibold text-foreground">Backtest</p>
          </div>
          <div className="p-6 space-y-4">
            <div className="flex items-center gap-2 flex-wrap">
              <input
                value       = {backtestCoin}
                onChange    = {e => setBacktestCoin(e.target.value.toUpperCase())}
                placeholder = "BTC"
                className   = "h-9 w-24 rounded-md border border-border bg-background px-3 text-sm font-mono text-foreground placeholder:text-muted-foreground outline-none focus:border-foreground/40 transition-colors"
              />
              <button
                onClick   = {() => setRunCoin(backtestCoin || null)}
                disabled  = {!backtestCoin || btLoading}
                className = "flex items-center gap-1.5 rounded-md bg-foreground px-3 py-2 text-xs font-medium text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
              >
                {btLoading ? (
                  <span className="flex items-center gap-1.5">
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Running
                  </span>
                ) : 'Run Backtest'}
              </button>
              {runCoin && (
                <button
                  onClick   = {() => { setRunCoin(null); setBacktestCoin('') }}
                  className = "text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
            {btResult && (
              <div className="rounded-md border border-border bg-muted/30 p-4 space-y-1">
                {(btResult as { error?: string }).error ? (
                  <p className="text-xs text-[hsl(var(--chart-2))]">{(btResult as { error: string }).error}</p>
                ) : (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {[
                      { label: 'Trades',   value: String((btResult as { total_trades?: number }).total_trades ?? 0) },
                      { label: 'Win Rate', value: formatPercent((btResult as { win_rate?: number }).win_rate ?? 0, false) },
                      { label: 'PnL',      value: formatCurrency((btResult as { total_pnl?: number }).total_pnl ?? 0) },
                      { label: 'Max DD',   value: formatPercent((btResult as { max_drawdown?: number }).max_drawdown ?? 0, false) },
                    ].map(item => (
                      <div key={item.label}>
                        <p className="label-xs">{item.label}</p>
                        <p className="text-sm font-mono font-semibold text-foreground mt-0.5">{item.value}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      ) : (
        <LockedSection
          requiredTier = "elite"
          title        = "Backtest Engine"
          description  = "Run historical backtests on any coin in your universe"
          rows         = {2}
        />
      )}

      <SignalHistoryTable signals={history ?? []} isLoading={histLoading} />

    </div>
  )
}
