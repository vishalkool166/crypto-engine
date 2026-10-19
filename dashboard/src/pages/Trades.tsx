import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { RefreshCw, Wifi, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { pnlColor } from '@/lib/tokens'
import {
  useTradeSummary, useDailyPnl,
  useCoinPerformance, useWsStatusTrades, useForceSell,
} from '@/hooks/useTrades'
import { useIndianStatus } from '@/hooks/useIndian'
import { useTradePage } from '@/hooks/useTradePage'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import TotpModal from '@/components/modals/TotpModal'
import OpenPositions from '@/components/trades/OpenPositions'
import TradeDrawer from '@/components/trades/TradeDrawer'
import KPICard from '@/components/ui/KPICard'
import FilterBar from '@/components/ui/FilterBar'
import Pagination from '@/components/ui/Pagination'
import GradeTag from '@/components/ui/GradeTag'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import { LockedSection } from '@/components/ui/TierGate'
import { getDirectionConfig, getCloseReasonConfig, pnlColor as pnlColorFn } from '@/lib/tokens'
import { formatDateTime, formatDuration } from '@/lib/utils'
import { motion as m } from 'framer-motion'
import { DollarSign, Target, TrendingUp, TrendingDown, Activity } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { toast } from 'sonner'
import type { Trade, CoinPerformance, DailyEntry } from '@/types'

const GRADE_FILTERS   = [
  { label: 'All', value: 'all' },
  { label: 'A+',  value: 'A+' },
  { label: 'A',   value: 'A'  },
  { label: 'B',   value: 'B'  },
]
const OUTCOME_FILTERS = [
  { label: 'All',  value: 'all'  },
  { label: 'Win',  value: 'win'  },
  { label: 'Loss', value: 'loss' },
]

function IndianSummaryCard({ status }: { status: {
  market_open:   boolean
  open_signals:  Array<{
    id:           number
    instrument:   string
    direction:    string
    live_pnl_pts: number | null
    live_rupees:  number | null
    duration:     string | null
  }>
  signals_today: number
} | undefined }) {
  const navigate = useNavigate()

  if (!status) return null

  const openSignals = status.open_signals ?? []
  const hasOpen     = openSignals.length > 0

  if (!status.market_open && !hasOpen) return null

  return (
    <motion.div
      initial    = {{ opacity: 0, y: -4 }}
      animate    = {{ opacity: 1, y: 0  }}
      onClick    = {() => navigate('/india')}
      className  = "rounded-lg border border-border bg-card px-4 py-3 cursor-pointer hover:bg-muted/30 transition-colors"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-sm">🇮🇳</span>
          <div>
            <p className="text-xs font-semibold text-foreground">Indian Market</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {hasOpen
                ? `${openSignals.length} active signal${openSignals.length !== 1 ? 's' : ''}`
                : status.market_open
                ? 'Market open — watching'
                : 'Market closed'
              }
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {hasOpen && openSignals.map(s => {
            const pnl    = s.live_pnl_pts ?? 0
            const rupees = s.live_rupees  ?? 0
            const pColor = pnl >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
            const sign   = pnl >= 0 ? '+' : ''
            const isLong = s.direction === 'LONG'
            return (
              <div key={s.id} className="text-right">
                <p className="text-xs font-mono font-semibold text-foreground">
                  {s.instrument} {isLong ? '📈' : '📉'}
                </p>
                <p className={cn('text-xs font-mono font-semibold', pColor)}>
                  {sign}{pnl.toFixed(0)} pts · {sign}₹{Math.abs(rupees).toLocaleString()}
                </p>
              </div>
            )
          })}
          <span className="text-xs text-muted-foreground">View →</span>
        </div>
      </div>
    </motion.div>
  )
}

export default function Trades() {
  const queryClient                       = useQueryClient()
  const { hasFeature, isAdmin }           = useAuthStore()
  const { isDemoMode }                    = useDemoStore()
  const navigate                          = useNavigate()
  const [totpOpen,      setTotpOpen]      = useState(false)
  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null)
  const [drawerTrade,   setDrawerTrade]   = useState<Trade | null>(null)

  const showPositions = hasFeature('show_positions') || isAdmin

  const {
    trades, profit, balance, isLoading,
    freeBalance, totalBalance, totalPnl, winRate, tradeCount,
    totalUnrealized, openCount,
  } = useTradeSummary()

  const { data: indianStatus }            = useIndianStatus()
  const { data: daily }                   = useDailyPnl(7)
  const { data: performance }             = useCoinPerformance()
  const { data: wsStatus }                = useWsStatusTrades()
  const forceSell                         = useForceSell()

  const {
    filters, setFilter, page, setPage,
    paginated, total, pageSize, isHistoryLoading, historyError,
  } = useTradePage()

  const wsConnected = (wsStatus?.mark_price_connected && wsStatus?.user_data_connected) ?? false

  const dailyData = (daily?.data ?? []).map((d: DailyEntry) => ({
    date: d.date.slice(5),
    pnl:  parseFloat((d.profit_abs ?? 0).toFixed(2)),
  }))

  if (isLoading) return <PageSkeleton />

  if (!showPositions) {
    return (
      <div className="p-4 md:p-6">
        <div className="mb-6">
          <h1 className="text-base font-semibold text-foreground">Trades</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Live positions and history</p>
        </div>
        <LockedSection
          requiredTier = "pro"
          title        = "Live Positions"
          description  = "Upgrade to Pro to view open trades, trade history, and performance analytics"
          rows         = {4}
        />
      </div>
    )
  }

  return (
    <div className="flex h-full overflow-hidden">
      <div className={cn(
        'flex flex-1 flex-col overflow-y-auto transition-all duration-300',
        drawerTrade ? 'lg:mr-96' : ''
      )}>
        <div className="p-4 md:p-6 space-y-6">

          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-base font-semibold text-foreground">Trades</h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                {isDemoMode ? 'Demo — Simulated Positions' : 'Binance Futures'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className={cn(
                'flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium',
                wsConnected
                  ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.06)] text-[hsl(var(--chart-1))]'
                  : 'border-border bg-muted text-muted-foreground'
              )}>
                {wsConnected ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                {wsConnected ? 'Live' : 'Disconnected'}
              </div>
              {!isDemoMode && (
                <button
                  onClick   = {() => {
                    queryClient.invalidateQueries({ queryKey: ['trades-open']   })
                    queryClient.invalidateQueries({ queryKey: ['trades-profit'] })
                  }}
                  className = "flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Refresh
                </button>
              )}
            </div>
          </div>

          <IndianSummaryCard status={indianStatus as {
            market_open:   boolean
            open_signals:  Array<{ id: number; instrument: string; direction: string; live_pnl_pts: number | null; live_rupees: number | null; duration: string | null }>
            signals_today: number
          } | undefined} />

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <KPICard
              title = "Free Balance"
              value = {formatCurrency(freeBalance)}
              sub   = {`${openCount} open trade${openCount !== 1 ? 's' : ''}`}
              icon  = {DollarSign}
            />
            <KPICard
              title = "Total Balance"
              value = {formatCurrency(totalBalance)}
              sub   = "incl. margin used"
              icon  = {Target}
            />
            <KPICard
              title          = "All-time PnL"
              value          = {formatCurrency(totalPnl)}
              sub            = "net realized"
              icon           = {totalPnl >= 0 ? TrendingUp : TrendingDown}
              valueClassName = {totalPnl >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'}
            />
            <KPICard
              title = "Win Rate"
              value = {winRate > 0 ? formatPercent(winRate, false) : '—'}
              sub   = {`${tradeCount} trades`}
              icon  = {Activity}
            />
          </div>

          <div className="rounded-lg border border-border bg-card overflow-hidden">
            <div className="border-b border-border px-6 py-4">
              <p className="text-sm font-semibold text-foreground">
                Open Positions
                <span className="ml-2 label-xs">{trades.length}</span>
              </p>
            </div>
            <OpenPositions
              trades          = {trades}
              selectedTradeId = {drawerTrade?.trade_id ?? null}
              onSelect        = {t => setDrawerTrade(drawerTrade?.trade_id === t.trade_id ? null : t)}
              onForceSell     = {t => { setSelectedTrade(t); setTotpOpen(true) }}
            />
          </div>

          {dailyData.length > 0 && (
            <div className="rounded-lg border border-border bg-card">
              <div className="border-b border-border px-6 py-4">
                <p className="text-sm font-semibold text-foreground">Daily PnL — Last 7 Days</p>
              </div>
              <div className="p-4 h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dailyData} barSize={16}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} tickFormatter={v => `$${v}`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '6px', fontSize: '12px' }}
                      formatter={(v: number) => [formatCurrency(v), 'Net PnL']}
                    />
                    <Bar dataKey="pnl" radius={[3, 3, 0, 0]}>
                      {dailyData.map((d: { pnl: number }, i: number) => (
                        <Cell key={i} fill={d.pnl >= 0 ? 'hsl(var(--chart-1))' : 'hsl(var(--chart-2))'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          <div className="rounded-lg border border-border bg-card overflow-hidden">
            <div className="border-b border-border px-6 py-4 flex items-center justify-between flex-wrap gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">Trade History</p>
                <p className="text-xs text-muted-foreground mt-0.5">{total} closed trades</p>
              </div>
              <FilterBar
                filters     = {GRADE_FILTERS}
                active      = {filters.grade}
                onFilter    = {v => setFilter('grade', v)}
                search      = {filters.coin}
                onSearch    = {v => setFilter('coin', v)}
                placeholder = "Filter coin..."
                right       = {
                  <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
                    {OUTCOME_FILTERS.map(f => (
                      <button
                        key       = {f.value}
                        onClick   = {() => setFilter('outcome', f.value)}
                        className = {cn(
                          'px-2.5 py-1.5 text-xs font-medium transition-colors',
                          filters.outcome === f.value
                            ? 'bg-foreground text-background'
                            : 'text-muted-foreground hover:text-foreground bg-background'
                        )}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                }
              />
            </div>

            {isHistoryLoading ? (
              <div className="py-10 text-center text-sm text-muted-foreground" role="status">Loading trade history…</div>
            ) : historyError ? (
              <div className="py-10 text-center text-sm text-destructive" role="alert">Trade history is unavailable. Try refreshing the page.</div>
            ) : paginated.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-center px-6">
                <p className="text-sm font-medium text-foreground">No matching closed trades</p>
                <p className="text-xs text-muted-foreground mt-1">Change filters to see other completed trades.</p>
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[520px]">
                    <thead className="border-b border-border">
                      <tr>
                        {['Coin', 'Grade', 'Net PnL', 'Reason', 'Duration', 'Closed'].map(h => (
                          <th key={h} className="table-header-cell">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {paginated.map((trade, i) => {
                        const pnl       = trade.pnl ?? 0
                        const dirCfg    = getDirectionConfig(trade.direction)
                        const DirIcon   = dirCfg?.icon
                        const reasonCfg = getCloseReasonConfig(trade.close_reason)
                        return (
                          <m.tr
                            key        = {trade.trade_id}
                            initial    = {{ opacity: 0 }}
                            animate    = {{ opacity: 1 }}
                            transition = {{ delay: Math.min(i * 0.02, 0.3) }}
                            onClick    = {() => setDrawerTrade(drawerTrade?.trade_id === trade.trade_id ? null : trade)}
                            className  = {cn('table-row cursor-pointer', drawerTrade?.trade_id === trade.trade_id && 'bg-muted/20')}
                          >
                            <td className="table-cell">
                              <div className="flex items-center gap-2">
                                {dirCfg && DirIcon && (
                                  <span className={cn('inline-flex items-center gap-1 text-xs font-medium', dirCfg.text)}>
                                    <DirIcon className="h-3 w-3" />
                                    {trade.coin}
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="table-cell"><GradeTag grade={trade.grade as never} /></td>
                            <td className="table-cell">
                              <span className={cn('font-mono text-xs font-semibold', pnlColorFn(pnl))}>
                                {formatCurrency(pnl)}
                              </span>
                            </td>
                            <td className="table-cell">
                              {reasonCfg ? (
                                <span className={cn('rounded px-1.5 py-px text-xs font-medium', reasonCfg.bg, reasonCfg.text)}>
                                  {reasonCfg.label}
                                </span>
                              ) : (
                                <span className="text-muted-foreground text-xs">—</span>
                              )}
                            </td>
                            <td className="table-cell font-mono text-muted-foreground text-xs">
                              {trade.duration_hours ? formatDuration(trade.duration_hours) : trade.duration ?? '—'}
                            </td>
                            <td className="table-cell text-muted-foreground text-xs">
                              {formatDateTime(trade.closed_at)}
                            </td>
                          </m.tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <Pagination page={page} total={total} pageSize={pageSize} onChange={setPage} />
              </>
            )}
          </div>

          {performance && (performance as CoinPerformance[]).length > 0 && (
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="border-b border-border px-6 py-4">
                <p className="text-sm font-semibold text-foreground">Per-Coin Performance</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[400px]">
                  <thead className="border-b border-border">
                    <tr>
                      {['Coin', 'W / L', 'Win Rate', 'Net PnL'].map(h => (
                        <th key={h} className="table-header-cell">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {(performance as CoinPerformance[]).map(row => (
                      <tr key={row.coin} className="table-row">
                        <td className="table-cell font-mono font-semibold">{row.coin}</td>
                        <td className="table-cell">
                          <span className="text-[hsl(var(--chart-1))] font-mono text-xs">{row.wins}W</span>
                          <span className="text-muted-foreground text-xs"> / </span>
                          <span className="text-[hsl(var(--chart-2))] font-mono text-xs">{row.losses}L</span>
                        </td>
                        <td className="table-cell">
                          <span className={cn('font-mono text-xs', row.win_rate >= 50 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')}>
                            {(row.win_rate ?? 0).toFixed(1)}%
                          </span>
                        </td>
                        <td className="table-cell">
                          <span className={cn('font-mono text-xs', pnlColorFn(row.profit_abs))}>
                            {formatCurrency(row.profit_abs)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </div>
      </div>

      <AnimatePresence>
        {drawerTrade && (
          <motion.div
            initial    = {{ x: '100%', opacity: 0 }}
            animate    = {{ x: 0, opacity: 1 }}
            exit       = {{ x: '100%', opacity: 0 }}
            transition = {{ duration: 0.25, ease: 'easeInOut' }}
            className  = "fixed right-0 top-0 h-full w-full max-w-sm border-l border-border bg-card overflow-y-auto z-40 shadow-2xl"
          >
            <TradeDrawer
              trade       = {drawerTrade}
              onClose     = {() => setDrawerTrade(null)}
              onForceSell = {() => { setSelectedTrade(drawerTrade); setTotpOpen(true) }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <TotpModal
        open        = {totpOpen}
        title       = "Confirm Force Sell"
        description = {selectedTrade ? `Close ${selectedTrade.coin}USDT ${selectedTrade.direction}` : ''}
        destructive
        loading     = {forceSell.isPending}
        onClose     = {() => { setTotpOpen(false); setSelectedTrade(null) }}
        onConfirm   = {async (code) => {
          if (!selectedTrade) return
          if (isDemoMode) {
            toast.success('Position closed (demo)')
            setTotpOpen(false)
            setSelectedTrade(null)
            setDrawerTrade(null)
            return
          }
          await forceSell.mutateAsync({ trade_id: selectedTrade.trade_id, totp_code: code })
          toast.success('Position closed')
          setTotpOpen(false)
          setSelectedTrade(null)
          setDrawerTrade(null)
        }}
      />
    </div>
  )
}