import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  RefreshCw, TrendingUp, TrendingDown, Clock,
  CheckCircle, XCircle, AlertTriangle, ChevronDown,
  Activity, BarChart3, Flag,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDateTime, formatTimeAgo } from '@/lib/utils'
import {
  useIndianStatus, useIndianSignals, useIndianPerformance,
  useSetupOrb, useTriggerIndianScan, useIndianSignalJourney,
  useRefreshIndianData,
} from '@/hooks/useIndian'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import EmptyState from '@/components/ui/EmptyState'
import CollapsibleSection from '@/components/ui/CollapsibleSection'
import KPICard from '@/components/ui/KPICard'
import TradeJourneyChart from '@/components/ui/TradeJourneyChart'
import { useAuthStore } from '@/stores/authStore'
import { useNavigate } from 'react-router-dom'
import type {
  IndianInstrumentConfig, IndianOrbLevel,
  IndianOpenSignal, IndianSignal, IndianPerformance,
} from '@/types'

const RUPEES_PER_POINT = 30

function DirectionBadge({ direction }: { direction: string }) {
  const isLong = direction === 'LONG'
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold',
      isLong
        ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.08)] text-[hsl(var(--chart-1))]'
        : 'border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.08)] text-[hsl(var(--chart-2))]'
    )}>
      {isLong ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
      {direction}
    </span>
  )
}

function OutcomeBadge({ outcome }: { outcome: string }) {
  const config = {
    win:     { text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]', border: 'border-[hsl(var(--chart-1)/0.2)]', label: 'Win'     },
    loss:    { text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]', border: 'border-[hsl(var(--chart-2)/0.2)]', label: 'Loss'    },
    timeout: { text: 'text-muted-foreground',       bg: 'bg-muted',                       border: 'border-border',                    label: 'Timeout' },
    pending: { text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]', border: 'border-[hsl(var(--chart-4)/0.2)]', label: 'Pending' },
  }
  const cfg = config[outcome as keyof typeof config] ?? config.pending
  return (
    <span className={cn(
      'inline-flex items-center rounded border px-1.5 py-px text-xs font-medium',
      cfg.text, cfg.bg, cfg.border
    )}>
      {cfg.label}
    </span>
  )
}

function RangeRow({
  label, value, threshold, suffix = 'pts',
}: {
  label: string; value: number; threshold: number; suffix?: string
}) {
  const ok = value >= threshold
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className={cn(
          'text-xs font-mono font-semibold',
          ok ? 'text-[hsl(var(--chart-1))]' : 'text-muted-foreground'
        )}>
          {value > 0 ? `${value.toFixed(0)} ${suffix}` : '—'}
        </span>
        <span className="text-xs text-muted-foreground">/ {threshold}+</span>
        {ok
          ? <CheckCircle className="h-3.5 w-3.5 text-[hsl(var(--chart-1))]" />
          : <XCircle     className="h-3.5 w-3.5 text-muted-foreground" />
        }
      </div>
    </div>
  )
}

function OrbCard({ name, orb, preRange, prevRange, instCfg }: {
  name:      string
  orb:       IndianOrbLevel | null
  preRange:  number
  prevRange: number
  instCfg:   IndianInstrumentConfig
}) {
  const orbOk  = orb ? orb.size >= instCfg.min_orb && orb.size <= instCfg.max_orb : false
  const volOk  = preRange >= instCfg.min_pre_range || prevRange >= instCfg.min_prev_range
  const isLong = instCfg.direction === 'LONG'

  if (!orb) {
    return (
      <div className="px-6 py-4 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground">{name}</span>
            <DirectionBadge direction={instCfg.direction} />
            <span className="label-xs">Lot {instCfg.lot_size}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          <span>ORB not set — available after 9:35am IST</span>
        </div>
      </div>
    )
  }

  return (
    <div className="px-6 py-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">{name}</span>
          <DirectionBadge direction={instCfg.direction} />
          <span className="label-xs">Lot {instCfg.lot_size}</span>
        </div>
        <span className={cn(
          'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
          orbOk
            ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.08)] text-[hsl(var(--chart-1))]'
            : 'border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.08)] text-[hsl(var(--chart-2))]'
        )}>
          {orbOk ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
          {orb.size < instCfg.min_orb
            ? `Too Tight (<${instCfg.min_orb})`
            : orb.size > instCfg.max_orb
            ? `Too Wide (>${instCfg.max_orb})`
            : 'Valid ORB'
          }
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <p className="label-xs">High</p>
          <p className="text-sm font-mono font-semibold text-foreground mt-0.5">
            {orb.high.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="label-xs">Low</p>
          <p className="text-sm font-mono font-semibold text-foreground mt-0.5">
            {orb.low.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="label-xs">Range</p>
          <p className={cn(
            'text-sm font-mono font-semibold mt-0.5',
            orbOk ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
          )}>
            {orb.size.toFixed(0)} pts
          </p>
        </div>
      </div>

      <div className="rounded-md border border-border bg-muted/20 px-3 divide-y divide-border">
        <RangeRow
          label     = "Pre-range (9:15–11am)"
          value     = {preRange}
          threshold = {instCfg.min_pre_range}
        />
        <RangeRow
          label     = "Prev day range"
          value     = {prevRange}
          threshold = {instCfg.min_prev_range}
        />
        <div className="flex items-center justify-between py-2.5">
          <span className="text-xs text-muted-foreground">Volatility Filter</span>
          <div className="flex items-center gap-1.5">
            {volOk
              ? <CheckCircle className="h-3.5 w-3.5 text-[hsl(var(--chart-1))]" />
              : <XCircle     className="h-3.5 w-3.5 text-[hsl(var(--chart-2))]" />
            }
            <span className={cn(
              'text-xs font-mono font-semibold',
              volOk ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
            )}>
              {volOk ? 'Pass' : 'Fail'}
            </span>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          SL {instCfg.sl_mult}x · TP {instCfg.tp_mult}x · Entry {instCfg.entry_start_h}am–12pm · Skip wk {instCfg.skip_weeks.join(',')}
        </span>
        <span className="font-mono">
          {isLong
            ? `above ${(orb.high + 10).toFixed(0)}`
            : `below ${(orb.low  - 10).toFixed(0)}`
          }
        </span>
      </div>
    </div>
  )
}

function OpenSignalCard({ signal }: { signal: IndianOpenSignal }) {
  const [expanded, setExpanded] = useState(false)
  const { data: journeyData }   = useIndianSignalJourney(expanded ? signal.id : null)

  const pnl      = signal.live_pnl_pts ?? 0
  const rupees   = signal.live_rupees  ?? 0
  const pnlColor = pnl >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
  const pnlSign  = pnl >= 0 ? '+' : ''
  const progress = signal.progress_pct ?? 0

  return (
    <motion.div
      initial   = {{ opacity: 0, y: 4 }}
      animate   = {{ opacity: 1, y: 0 }}
      className = "rounded-lg border border-[hsl(var(--chart-4)/0.2)] bg-card overflow-hidden"
    >
      <div
        className = "px-6 py-4 cursor-pointer hover:bg-muted/20 transition-colors space-y-3"
        onClick   = {() => setExpanded(e => !e)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <DirectionBadge direction={signal.direction} />
            <span className="text-sm font-mono font-semibold text-foreground">
              {signal.instrument}
            </span>
            <span className={cn(
              'inline-flex items-center rounded border px-1.5 py-px text-xs font-medium',
              'border-[hsl(var(--chart-4)/0.2)] bg-[hsl(var(--chart-4)/0.08)] text-[hsl(var(--chart-4))]'
            )}>
              Live
            </span>
          </div>
          <div className="flex items-center gap-3">
            {signal.current_price && (
              <div className="text-right">
                <p className="text-xs font-mono font-semibold text-foreground">
                  {signal.current_price.toFixed(2)}
                </p>
                <p className={cn('text-xs font-mono font-semibold', pnlColor)}>
                  {pnlSign}{pnl.toFixed(0)} pts
                </p>
              </div>
            )}
            <ChevronDown className={cn(
              'h-4 w-4 text-muted-foreground transition-transform duration-200',
              expanded && 'rotate-180'
            )} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="label-xs">Entry</p>
            <p className="text-sm font-mono font-semibold text-foreground mt-0.5">
              {signal.entry.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="label-xs">Stop Loss</p>
            <p className="text-sm font-mono font-semibold text-[hsl(var(--chart-2))] mt-0.5">
              {signal.sl.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="label-xs">Take Profit</p>
            <p className="text-sm font-mono font-semibold text-[hsl(var(--chart-1))] mt-0.5">
              {signal.tp1.toFixed(2)}
            </p>
          </div>
        </div>

        {progress > 0 && (
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="label-xs">Progress to TP</span>
              <span className={cn('text-xs font-mono font-semibold', pnlColor)}>
                {progress.toFixed(1)}%
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <motion.div
                initial    = {{ width: 0 }}
                animate    = {{ width: `${Math.min(100, progress)}%` }}
                transition = {{ duration: 0.5 }}
                className  = {cn(
                  'h-full rounded-full',
                  pnl >= 0 ? 'bg-[hsl(var(--chart-1))]' : 'bg-[hsl(var(--chart-2))]'
                )}
              />
            </div>
          </div>
        )}

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            ORB <span className="font-mono text-foreground">
              {signal.orb_low.toFixed(0)} — {signal.orb_high.toFixed(0)}
            </span>
            {' '}· <span className="font-mono text-foreground">
              {signal.orb_size.toFixed(0)} pts
            </span>
          </span>
          <div className="flex items-center gap-3">
            {signal.duration && (
              <span className="text-xs text-muted-foreground">{signal.duration}</span>
            )}
            {rupees !== 0 && (
              <span className={cn('text-xs font-mono font-semibold', pnlColor)}>
                {pnlSign}₹{Math.abs(rupees).toLocaleString()} / lot
              </span>
            )}
          </div>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial    = {{ height: 0, opacity: 0 }}
            animate    = {{ height: 'auto', opacity: 1 }}
            exit       = {{ height: 0, opacity: 0 }}
            transition = {{ duration: 0.2 }}
            className  = "overflow-hidden border-t border-border"
          >
            <div className="px-6 py-4">
              {journeyData?.journey && journeyData.journey.length > 0 ? (
                <TradeJourneyChart
                  journey   = {journeyData.journey}
                  market    = "indian"
                  height    = {180}
                  direction = {signal.direction as 'LONG' | 'SHORT'}
                />
              ) : (
                <EmptyState
                  title       = "Collecting journey data"
                  description = "Updates every 5 minutes"
                  compact
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function ClosedSignalCard({ signal }: { signal: IndianSignal }) {
  const [expanded, setExpanded] = useState(false)
  const { data: journeyData }   = useIndianSignalJourney(expanded ? signal.id : null)

  const pnl      = signal.pnl_pts ?? 0
  const rupees   = Math.round(pnl * RUPEES_PER_POINT)
  const isPending= signal.outcome === 'pending'
  const isWin    = signal.outcome === 'win'
  const isLoss   = signal.outcome === 'loss'
  const pnlColor = pnl > 0
    ? 'text-[hsl(var(--chart-1))]'
    : pnl < 0
    ? 'text-[hsl(var(--chart-2))]'
    : 'text-muted-foreground'

  return (
    <motion.div
      initial   = {{ opacity: 0, y: 4 }}
      animate   = {{ opacity: 1, y: 0 }}
      className = {cn(
        'rounded-lg border bg-card overflow-hidden',
        isWin     ? 'border-[hsl(var(--chart-1)/0.2)]' :
        isLoss    ? 'border-[hsl(var(--chart-2)/0.2)]' :
        isPending ? 'border-[hsl(var(--chart-4)/0.2)]' :
        'border-border'
      )}
    >
      <div
        className = "px-6 py-4 cursor-pointer hover:bg-muted/20 transition-colors space-y-3"
        onClick   = {() => setExpanded(e => !e)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <DirectionBadge direction={signal.direction} />
            <span className="text-sm font-mono font-semibold text-foreground">
              {signal.instrument}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <OutcomeBadge outcome={signal.outcome} />
            {!isPending && (
              <span className={cn('text-sm font-mono font-semibold', pnlColor)}>
                {pnl > 0 ? '+' : ''}{pnl.toFixed(0)} pts
              </span>
            )}
            <ChevronDown className={cn(
              'h-4 w-4 text-muted-foreground transition-transform duration-200',
              expanded && 'rotate-180'
            )} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="label-xs">Entry</p>
            <p className="text-sm font-mono font-semibold text-foreground mt-0.5">
              {signal.entry.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="label-xs">Stop Loss</p>
            <p className="text-sm font-mono font-semibold text-[hsl(var(--chart-2))] mt-0.5">
              {signal.sl.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="label-xs">Take Profit</p>
            <p className="text-sm font-mono font-semibold text-[hsl(var(--chart-1))] mt-0.5">
              {signal.tp1.toFixed(2)}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            ORB <span className="font-mono text-foreground">
              {signal.orb_low.toFixed(0)} — {signal.orb_high.toFixed(0)}
            </span>
            {' '}· <span className="font-mono text-foreground">
              {signal.orb_size.toFixed(0)} pts
            </span>
          </span>
          <div className="flex items-center gap-3">
            {signal.timestamp && (
              <span className="text-xs text-muted-foreground">
                {formatTimeAgo(signal.timestamp)}
              </span>
            )}
            {!isPending && pnl !== 0 && (
              <span className={cn('text-xs font-mono font-semibold', pnlColor)}>
                {rupees > 0 ? '+' : ''}₹{Math.abs(rupees).toLocaleString()} / lot
              </span>
            )}
          </div>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial    = {{ height: 0, opacity: 0 }}
            animate    = {{ height: 'auto', opacity: 1 }}
            exit       = {{ height: 0, opacity: 0 }}
            transition = {{ duration: 0.2 }}
            className  = "overflow-hidden border-t border-border"
          >
            <div className="px-6 py-4">
              {journeyData?.journey && journeyData.journey.length > 0 ? (
                <TradeJourneyChart
                  journey   = {journeyData.journey}
                  market    = "indian"
                  height    = {180}
                  direction = {signal.direction as 'LONG' | 'SHORT'}
                />
              ) : (
                <EmptyState
                  title       = {signal.outcome === 'pending'
                    ? 'Collecting journey data'
                    : 'No journey data'
                  }
                  description = {signal.outcome === 'pending'
                    ? 'Updates every 5 minutes'
                    : 'Trade opened before tracking was enabled'
                  }
                  compact
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function PerformanceTab({ perf }: { perf: IndianPerformance | null }) {
  if (!perf || perf.total === 0) {
    return (
      <EmptyState
        icon        = {BarChart3}
        title       = "No closed signals yet"
        description = "Performance data appears after first signal closes"
        compact
      />
    )
  }

  const totalRupees = Math.round((perf.total_pts ?? 0) * RUPEES_PER_POINT)
  const pnlPos      = (perf.total_pts ?? 0) >= 0
  const profRate    = perf.profitable_rate ?? perf.win_rate ?? 0
  const DAY_NAMES   = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KPICard
          title = "Total Signals"
          value = {String(perf.total ?? 0)}
          sub   = {`${perf.wins ?? 0}W ${perf.losses ?? 0}L ${perf.timeouts ?? 0}T`}
        />
        <KPICard
          title          = "Profitable Rate"
          value          = {`${profRate}%`}
          sub            = "wins + positive timeouts"
          valueClassName = {profRate >= 50
            ? 'text-[hsl(var(--chart-1))]'
            : 'text-[hsl(var(--chart-2))]'
          }
        />
        <KPICard
          title          = "Total Points"
          value          = {`${(perf.total_pts ?? 0) > 0 ? '+' : ''}${(perf.total_pts ?? 0).toFixed(0)}`}
          sub            = {`₹${pnlPos ? '+' : ''}${Math.abs(totalRupees).toLocaleString()} / lot`}
          valueClassName = {pnlPos
            ? 'text-[hsl(var(--chart-1))]'
            : 'text-[hsl(var(--chart-2))]'
          }
        />
        <KPICard
          title = "Profit Factor"
          value = {String(perf.profit_factor ?? 0)}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <KPICard
          title          = "Avg Win"
          value          = {`+${(perf.avg_win_pts ?? 0).toFixed(0)} pts`}
          sub            = {`₹+${Math.round((perf.avg_win_pts ?? 0) * RUPEES_PER_POINT).toLocaleString()} / lot`}
          valueClassName = "text-[hsl(var(--chart-1))]"
        />
        <KPICard
          title          = "Avg Loss"
          value          = {`${(perf.avg_loss_pts ?? 0).toFixed(0)} pts`}
          sub            = {`₹${Math.round((perf.avg_loss_pts ?? 0) * RUPEES_PER_POINT).toLocaleString()} / lot`}
          valueClassName = "text-[hsl(var(--chart-2))]"
        />
      </div>

      {perf.by_direction && Object.keys(perf.by_direction).length > 0 && (
        <CollapsibleSection title="By Direction" count={Object.keys(perf.by_direction).length} defaultOpen>
          <div className="divide-y divide-border">
            {Object.entries(perf.by_direction).map(([dir, data]) => {
              const isLong = dir === 'LONG'
              const rupees = Math.round((data.pnl_pts ?? 0) * RUPEES_PER_POINT)
              const pColor = (data.pnl_pts ?? 0) >= 0
                ? 'text-[hsl(var(--chart-1))]'
                : 'text-[hsl(var(--chart-2))]'
              return (
                <div key={dir} className="flex items-center justify-between px-6 py-3.5">
                  <div className="flex items-center gap-2.5">
                    {isLong
                      ? <TrendingUp   className="h-4 w-4 text-[hsl(var(--chart-1))]" />
                      : <TrendingDown className="h-4 w-4 text-[hsl(var(--chart-2))]" />
                    }
                    <span className="text-sm font-medium text-foreground">{dir}</span>
                    <span className="label-xs">{data.total ?? 0} signals</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className={cn(
                      'text-sm font-mono font-semibold',
                      (data.win_rate ?? 0) >= 40
                        ? 'text-[hsl(var(--chart-1))]'
                        : 'text-[hsl(var(--chart-2))]'
                    )}>
                      {data.win_rate ?? 0}% WR
                    </span>
                    <span className={cn('text-sm font-mono font-semibold', pColor)}>
                      {(data.pnl_pts ?? 0) > 0 ? '+' : ''}{(data.pnl_pts ?? 0).toFixed(0)} pts
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </CollapsibleSection>
      )}

      {perf.by_day && Object.keys(perf.by_day).length > 0 && (
        <CollapsibleSection title="By Day of Week" defaultOpen>
          <div className="divide-y divide-border">
            {DAY_NAMES.filter(d => perf.by_day[d]).map(day => {
              const data = perf.by_day[day]
              return (
                <div key={day} className="flex items-center justify-between px-6 py-3.5">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-foreground w-24">{day}</span>
                    <span className="label-xs">{data.total ?? 0} signals</span>
                  </div>
                  <span className={cn(
                    'text-sm font-mono font-semibold',
                    (data.win_rate ?? 0) >= 40
                      ? 'text-[hsl(var(--chart-1))]'
                      : 'text-[hsl(var(--chart-2))]'
                  )}>
                    {data.win_rate ?? 0}% WR
                  </span>
                </div>
              )
            })}
          </div>
        </CollapsibleSection>
      )}
    </div>
  )
}

function HistoryTab({ signals, isLoading }: { signals: IndianSignal[]; isLoading: boolean }) {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const { data: journeyData }        = useIndianSignalJourney(selectedId)
  const selectedSignal               = signals.find(s => s.id === selectedId)
  const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-foreground" />
      </div>
    )
  }

  if (signals.length === 0) {
    return (
      <EmptyState
        icon        = {Activity}
        title       = "No signals yet"
        description = "Signals appear here after market hours"
        compact
      />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px]">
        <thead className="border-b border-border">
          <tr>
            {['Date', 'Day', 'Instrument', 'Direction', 'Entry', 'SL', 'TP', 'ORB', 'Outcome', 'Points', 'Rupees'].map(h => (
              <th key={h} className="table-header-cell">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {signals.map((s, i) => {
            const pnl        = s.pnl_pts ?? 0
            const rupees     = Math.round(pnl * RUPEES_PER_POINT)
            const pnlColor   = pnl > 0
              ? 'text-[hsl(var(--chart-1))]'
              : pnl < 0
              ? 'text-[hsl(var(--chart-2))]'
              : 'text-muted-foreground'
            const isLong     = s.direction === 'LONG'
            const dayName    = s.day_of_week !== null ? DAY_NAMES[s.day_of_week] : '—'
            const isSelected = selectedId === s.id

            return (
              <>
                <motion.tr
                  key        = {s.id}
                  initial    = {{ opacity: 0 }}
                  animate    = {{ opacity: 1 }}
                  transition = {{ delay: Math.min(i * 0.02, 0.3) }}
                  onClick    = {() => setSelectedId(isSelected ? null : s.id)}
                  className  = {cn('table-row cursor-pointer', isSelected && 'bg-muted/20')}
                >
                  <td className="table-cell text-xs text-muted-foreground">
                    {s.timestamp ? formatDateTime(s.timestamp).slice(0, 10) : '—'}
                  </td>
                  <td className="table-cell text-xs text-muted-foreground">{dayName}</td>
                  <td className="table-cell text-xs font-medium text-foreground">{s.instrument}</td>
                  <td className="table-cell">
                    <span className={cn(
                      'inline-flex items-center gap-1 text-xs font-medium',
                      isLong ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
                    )}>
                      {isLong
                        ? <TrendingUp   className="h-3 w-3" />
                        : <TrendingDown className="h-3 w-3" />
                      }
                      {s.direction}
                    </span>
                  </td>
                  <td className="table-cell font-mono text-xs text-foreground">
                    {(s.entry ?? 0).toFixed(2)}
                  </td>
                  <td className="table-cell font-mono text-xs text-[hsl(var(--chart-2))]">
                    {(s.sl ?? 0).toFixed(2)}
                  </td>
                  <td className="table-cell font-mono text-xs text-[hsl(var(--chart-1))]">
                    {(s.tp1 ?? 0).toFixed(2)}
                  </td>
                  <td className="table-cell font-mono text-xs text-muted-foreground">
                    {(s.orb_size ?? 0).toFixed(0)} pts
                  </td>
                  <td className="table-cell">
                    <OutcomeBadge outcome={s.outcome} />
                  </td>
                  <td className="table-cell">
                    <span className={cn('font-mono text-xs font-semibold', pnlColor)}>
                      {s.outcome === 'pending'
                        ? '—'
                        : `${pnl > 0 ? '+' : ''}${pnl.toFixed(0)}`
                      }
                    </span>
                  </td>
                  <td className="table-cell">
                    <span className={cn('font-mono text-xs font-semibold', pnlColor)}>
                      {s.outcome === 'pending'
                        ? '—'
                        : `${rupees > 0 ? '+' : ''}₹${Math.abs(rupees).toLocaleString()}`
                      }
                    </span>
                  </td>
                </motion.tr>

                {isSelected && (
                  <tr key={`journey-${s.id}`}>
                    <td colSpan={11} className="p-0">
                      <AnimatePresence>
                        <motion.div
                          initial    = {{ height: 0, opacity: 0 }}
                          animate    = {{ height: 'auto', opacity: 1 }}
                          exit       = {{ height: 0, opacity: 0 }}
                          transition = {{ duration: 0.2 }}
                          className  = "overflow-hidden border-b border-border bg-muted/10 px-6 py-4"
                        >
                          {journeyData?.journey && journeyData.journey.length > 0 ? (
                            <TradeJourneyChart
                              journey   = {journeyData.journey}
                              market    = "indian"
                              height    = {160}
                              direction = {selectedSignal?.direction as 'LONG' | 'SHORT' ?? 'LONG'}
                            />
                          ) : (
                            <p className="text-xs text-muted-foreground text-center py-4">
                              No journey data for this signal
                            </p>
                          )}
                        </motion.div>
                      </AnimatePresence>
                    </td>
                  </tr>
                )}
              </>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function India() {
  const { isAdmin }   = useAuthStore()
  const navigate      = useNavigate()
  const [tab, setTab] = useState<'today' | 'performance' | 'history'>('today')

  const { data: status,  isLoading: statusLoading  } = useIndianStatus()
  const { data: signals, isLoading: signalsLoading } = useIndianSignals(100)
  const { data: perf,    isLoading: perfLoading    } = useIndianPerformance()
  const setupOrb    = useSetupOrb()
  const triggerScan = useTriggerIndianScan()
  const refreshData = useRefreshIndianData()

  if (!isAdmin) {
    navigate('/', { replace: true })
    return null
  }

  if (statusLoading) return <PageSkeleton />

  const marketOpen        = status?.market_open        ?? false
  const orbReady          = status?.orb_ready          ?? false
  const timeIst           = status?.time_ist           ?? '—'
  const orbLevels         = status?.orb_levels         ?? {}
  const preRanges         = status?.pre_ranges         ?? {}
  const prevRanges        = status?.prev_ranges        ?? {}
  const todaySignals      = status?.signals            ?? []
  const openSignals       = status?.open_signals       ?? []
  const rateLimited       = status?.rate_limited       ?? false
  const dataAgeSecs       = status?.data_age_secs      ?? 999
  const instrumentsConfig = status?.instruments_config ?? {}
  const allInstruments    = Object.keys(instrumentsConfig)

  const dataAgeStr = dataAgeSecs < 60
    ? `${Math.round(dataAgeSecs)}s ago`
    : `${Math.floor(dataAgeSecs / 60)}m ago`

  const allReady = allInstruments.every(name => {
    const cfg  = instrumentsConfig[name]
    if (!cfg) return false
    const orb  = orbLevels[name]
    const pre  = preRanges[name]  ?? 0
    const prev = prevRanges[name] ?? 0
    return orb
      ? orb.size >= cfg.min_orb && orb.size <= cfg.max_orb &&
        (pre >= cfg.min_pre_range || prev >= cfg.min_prev_range)
      : false
  })

  const willTrade   = orbReady && marketOpen && allReady
  const closedToday = todaySignals.filter(s => s.outcome !== 'pending')

  const TABS = [
    { id: 'today',       label: 'Today'       },
    { id: 'performance', label: 'Performance' },
    { id: 'history',     label: 'History'     },
  ]

  return (
    <div className="p-4 md:p-6 space-y-6">

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <Flag className="h-4 w-4 text-muted-foreground" />
            <h1 className="text-base font-semibold text-foreground">Indian Market</h1>
            <div className={cn(
              'flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium',
              marketOpen
                ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.08)] text-[hsl(var(--chart-1))]'
                : 'border-border bg-muted text-muted-foreground'
            )}>
              <span className={cn(
                'h-1.5 w-1.5 rounded-full',
                marketOpen ? 'bg-[hsl(var(--chart-1))] animate-pulse-dot' : 'bg-muted-foreground'
              )} />
              {marketOpen ? 'Market Open' : 'Market Closed'}
            </div>
          </div>
          <div className="flex items-center gap-3 mt-0.5">
            <p className="text-xs text-muted-foreground">
              {allInstruments.length > 0 ? allInstruments.join(' · ') : 'Loading...'} · Paper Tracking · {timeIst}
            </p>
            {dataAgeSecs < 999 && (
              <span className={cn(
                'text-xs',
                dataAgeSecs < 120 ? 'text-[hsl(var(--chart-1))]' :
                dataAgeSecs < 360 ? 'text-[hsl(var(--chart-4))]' :
                'text-[hsl(var(--chart-2))]'
              )}>
                Data: {dataAgeStr}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick   = {() => refreshData.mutate()}
            disabled  = {refreshData.isPending || rateLimited}
            className = "flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', refreshData.isPending && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick   = {() => setupOrb.mutate()}
            disabled  = {setupOrb.isPending || orbReady}
            className = "flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', setupOrb.isPending && 'animate-spin')} />
            Setup ORB
          </button>
          <button
            onClick   = {() => triggerScan.mutate()}
            disabled  = {triggerScan.isPending || !orbReady}
            className = "flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', triggerScan.isPending && 'animate-spin')} />
            Scan Now
          </button>
        </div>
      </div>

      {rateLimited && (
        <div className="rounded-lg border border-[hsl(var(--chart-4)/0.2)] bg-[hsl(var(--chart-4)/0.06)] px-4 py-3 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-[hsl(var(--chart-4))] shrink-0" />
          <p className="text-xs text-[hsl(var(--chart-4))]">
            AngelOne rate limited — showing cached data. Auto-refreshes in ~2 minutes.
          </p>
        </div>
      )}

      <div className="rounded-lg border border-border bg-card px-4 py-3">
        <div className="flex items-center gap-6 flex-wrap">
          {[
            { label: 'Market',         value: marketOpen ? 'Open' : 'Closed',   color: marketOpen ? 'text-[hsl(var(--chart-1))]' : 'text-muted-foreground' },
            { label: 'ORB',            value: orbReady   ? 'Ready' : 'Waiting', color: orbReady   ? 'text-[hsl(var(--chart-1))]' : 'text-muted-foreground' },
            { label: 'Instruments',    value: `${allInstruments.length} active`, color: 'text-foreground' },
            { label: 'Signals Today',  value: String(todaySignals.length),       color: 'text-foreground' },
            { label: 'Open',           value: String(openSignals.length),        color: openSignals.length > 0 ? 'text-[hsl(var(--chart-4))]' : 'text-foreground' },
            { label: 'Ready to Trade', value: willTrade ? 'Yes' : 'No',         color: willTrade ? 'text-[hsl(var(--chart-1))]' : 'text-muted-foreground' },
          ].map(item => (
            <div key={item.label} className="flex items-center gap-2">
              <span className="label-xs">{item.label}</span>
              <span className={cn('text-sm font-mono font-semibold', item.color)}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-px rounded-md border border-border overflow-hidden w-fit">
        {TABS.map(t => (
          <button
            key       = {t.id}
            onClick   = {() => setTab(t.id as typeof tab)}
            className = {cn(
              'px-4 py-2 text-xs font-medium transition-colors',
              tab === t.id
                ? 'bg-foreground text-background'
                : 'text-muted-foreground hover:text-foreground bg-background'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'today' && (
        <div className="space-y-4">

          {openSignals.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm font-semibold text-foreground">
                Open Positions
                <span className="ml-2 text-xs text-muted-foreground font-normal">
                  {openSignals.length} active
                </span>
              </p>
              {openSignals.map(s => (
                <OpenSignalCard key={s.id} signal={s} />
              ))}
            </div>
          )}

          <CollapsibleSection title="ORB Levels" count={allInstruments.length} defaultOpen>
            {allInstruments.length === 0 ? (
              <div className="px-6 py-4 flex items-center gap-2 text-xs text-muted-foreground">
                <Clock className="h-3.5 w-3.5" />
                Loading instrument configuration...
              </div>
            ) : (
              <div className="divide-y divide-border">
                {allInstruments.map(name => (
                  <OrbCard
                    key       = {name}
                    name      = {name}
                    orb       = {orbLevels[name] ?? null}
                    preRange  = {preRanges[name]  ?? 0}
                    prevRange = {prevRanges[name] ?? 0}
                    instCfg   = {instrumentsConfig[name]}
                  />
                ))}
              </div>
            )}
          </CollapsibleSection>

          <CollapsibleSection title="Today's Signals" count={closedToday.length} defaultOpen>
            {closedToday.length === 0 ? (
              <div className="px-6 py-4">
                <p className="text-sm text-muted-foreground">
                  {orbReady && willTrade
                    ? 'No signal yet — watching from 11am IST'
                    : orbReady
                    ? 'Conditions not met — check ORB levels above'
                    : 'No signals today'
                  }
                </p>
              </div>
            ) : (
              <div className="p-4 space-y-3">
                {closedToday.map(s => (
                  <ClosedSignalCard key={s.id} signal={s} />
                ))}
              </div>
            )}
          </CollapsibleSection>

        </div>
      )}

      {tab === 'performance' && (
        perfLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-foreground" />
          </div>
        ) : (
          <PerformanceTab perf={perf ?? null} />
        )
      )}

      {tab === 'history' && (
        <CollapsibleSection title="Signal History" count={signals?.length ?? 0} defaultOpen>
          <div className="px-6 py-2 border-b border-border">
            <p className="text-xs text-muted-foreground">
              Click any row to see journey chart · Paper tracking only
            </p>
          </div>
          <HistoryTab signals={signals ?? []} isLoading={signalsLoading} />
        </CollapsibleSection>
      )}

    </div>
  )
}