import { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { DollarSign, Target, TrendingUp, TrendingDown, Users, RotateCcw, Zap, Radio, Lock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatCurrency, formatPercent, formatNumber } from '@/lib/utils'
import { useSignals } from '@/hooks/useSignals'
import { useTradeSummary } from '@/hooks/useTrades'
import { useAdminStats, useSyncOutcomes } from '@/hooks/useAdmin'
import { useSystemStatus, useScanStatus } from '@/hooks/useHealth'
import { useWsStore } from '@/stores/wsStore'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { useSignalAccess } from '@/hooks/useSignalAccess'
import { signalsApi } from '@/lib/endpoints'
import KPICard from '@/components/ui/KPICard'
import GradeTag from '@/components/ui/GradeTag'
import EngineHealthCard from '@/components/engine/EngineHealthCard'
import SignalCountdown from '@/components/ui/SignalCountdown'
import { getDirectionConfig } from '@/lib/tokens'
import { toast } from 'sonner'
import type { QueueItem } from '@/types'

export default function Home() {
  const navigate                       = useNavigate()
  const { isDemoMode }                 = useDemoStore()
  const { isAdmin, hasFeature }        = useAuthStore()
  const { isFree, canSeeSignal }       = useSignalAccess()

  const { live, watching, queue, isLoading: signalsLoading } = useSignals()
  const { totalPnl, winRate, tradeCount, freeBalance, openCount } = useTradeSummary()
  const { data: adminStats }                                   = useAdminStats()
  const { alerts, mlProgress }                                 = useSystemStatus()
  const { countdown, watchingCount, inTradeCount, cooldownCount } = useScanStatus()
  const syncMutation                                           = useSyncOutcomes()
  const { summary }                                            = useWsStore()

  const [scanning, setScanning] = useState(false)

  const showPositions   = hasFeature('show_positions')   || isAdmin
  const showPerformance = hasFeature('show_performance') || isAdmin

  const isLive     = summary?.mode === 'live'
  const topSignal  = queue.filter(i => ['A+', 'A'].includes(i.grade))[0] ?? null
  const topTimestamp = topSignal
    ? (live.find(r => r.coin === topSignal.coin)?.timestamp ?? null)
    : null

  const handleScan = async () => {
    if (isDemoMode) { toast.success('Scan triggered'); return }
    setScanning(true)
    try {
      await signalsApi.scan()
      toast.success('Scan triggered')
    } catch {
      toast.error('Scan failed')
    } finally {
      setScanning(false)
    }
  }

  const getPath = (path: string) => isDemoMode ? `/demo${path}` : path

  return (
    <div className="p-4 md:p-6 space-y-6">

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-foreground">Overview</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={cn(
              'h-1.5 w-1.5 rounded-full',
              isLive ? 'bg-[hsl(var(--chart-2))] animate-pulse-dot' : 'bg-[hsl(var(--chart-3))]'
            )} />
            <span className={cn('text-xs font-medium', isLive ? 'text-[hsl(var(--chart-2))]' : 'text-[hsl(var(--chart-3))]')}>
              {isLive ? 'Live Trading' : 'Paper Trading'}
            </span>
            <span className="text-xs text-muted-foreground">· Next scan {countdown}</span>
          </div>
        </div>
        {isAdmin && !isDemoMode && (
          <div className="flex items-center gap-2">
            <button
              onClick   = {() => syncMutation.mutate()}
              disabled  = {syncMutation.isPending}
              className = "flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
            >
              <RotateCcw className={cn('h-3.5 w-3.5', syncMutation.isPending && 'animate-spin')} />
              Sync
            </button>
            <button
              onClick   = {handleScan}
              disabled  = {scanning}
              className = "flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
            >
              <Zap className="h-3.5 w-3.5" />
              Scan Now
            </button>
          </div>
        )}
      </div>

      {alerts.length > 0 && (
        <div className="rounded-lg border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-4 py-3">
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {alerts.map((alert, i) => (
              <span key={i} className="text-xs font-medium text-[hsl(var(--chart-2))]">{alert}</span>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-border bg-card px-4 py-3">
        <div className="flex items-center gap-6 flex-wrap">
          {[
            { label: 'Watching',      value: watchingCount,                 color: 'text-[hsl(var(--chart-4))]' },
            { label: 'In Trade',      value: inTradeCount,                  color: 'text-[hsl(var(--chart-5))]' },
            { label: 'Cooldown',      value: cooldownCount,                 color: 'text-muted-foreground'       },
            { label: 'Coins',         value: summary?.coins_count ?? 0,     color: 'text-foreground'             },
            { label: 'Signals Today', value: summary?.total_signals ?? 0,   color: 'text-foreground'             },
            { label: 'Closed',        value: summary?.closed_signals ?? 0,  color: 'text-foreground'             },
            { label: 'Pending',       value: summary?.pending_signals ?? 0, color: 'text-[hsl(var(--chart-4))]' },
          ].map(item => (
            <div key={item.label} className="flex items-center gap-2">
              <span className="label-xs">{item.label}</span>
              <span className={cn('text-sm font-mono font-semibold', item.color)}>{item.value}</span>
            </div>
          ))}
        </div>
      </div>

      <HeroSection
        hasSignal     = {live.length > 0}
        topSignal     = {topSignal}
        topTimestamp  = {topTimestamp}
        watchingCount = {watchingCount}
        isLoading     = {signalsLoading}
        isFree        = {isFree}
        canSeeSignal  = {canSeeSignal}
        showLevels    = {hasFeature('show_levels') || isAdmin}
        onViewSignals = {() => navigate(getPath('/signals'))}
      />

      <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
        {showPositions ? (
          <KPICard
            title = "Free Balance"
            value = {formatCurrency(freeBalance)}
            sub   = {`${openCount} open trade${openCount !== 1 ? 's' : ''}`}
            icon  = {DollarSign}
          />
        ) : (
          <LockedKPI title="Free Balance" requiredTier="Pro" />
        )}

        {showPerformance ? (
          <KPICard
            title          = "Win Rate"
            value          = {winRate > 0 ? formatPercent(winRate, false) : '—'}
            sub            = {`${tradeCount} closed trades`}
            icon           = {Target}
            valueClassName = {winRate >= 50 ? 'text-[hsl(var(--chart-1))]' : winRate > 0 ? 'text-[hsl(var(--chart-2))]' : ''}
          />
        ) : (
          <LockedKPI title="Win Rate" requiredTier="Pro" />
        )}

        {showPerformance ? (
          <KPICard
            title          = "Total PnL"
            value          = {formatCurrency(totalPnl)}
            sub            = "All time net"
            icon           = {totalPnl >= 0 ? TrendingUp : TrendingDown}
            valueClassName = {totalPnl >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'}
          />
        ) : (
          <LockedKPI title="Total PnL" requiredTier="Pro" />
        )}

        {isAdmin && !isDemoMode && adminStats ? (
          <KPICard
            title = "Total Users"
            value = {formatNumber(adminStats.users.total)}
            sub   = {`+${adminStats.users.new_today} today`}
            icon  = {Users}
          />
        ) : (
          <KPICard
            title = "Watching"
            value = {String(watchingCount)}
            sub   = {`${summary?.coins_count ?? 0} coins monitored`}
            icon  = {Radio}
          />
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:gap-6 lg:grid-cols-2">
        <SignalQueue
          queue      = {queue}
          onNavigate = {() => navigate(getPath('/signals'))}
        />
        <MLProgress progress={mlProgress} />
      </div>

      {isAdmin && !isDemoMode && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <EngineHealthCard />
        </div>
      )}

    </div>
  )
}

function LockedKPI({ title, requiredTier }: { title: string; requiredTier: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-2">
      <p className="label-xs">{title}</p>
      <div className="flex items-center gap-1.5">
        <Lock className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">{requiredTier} required</span>
      </div>
      <a
        href      = "/pricing"
        className = "text-xs font-medium text-foreground underline underline-offset-2 hover:text-muted-foreground transition-colors"
      >
        Upgrade
      </a>
    </div>
  )
}

function HeroSection({
  hasSignal, topSignal, topTimestamp, watchingCount,
  isLoading, isFree, canSeeSignal, showLevels, onViewSignals,
}: {
  hasSignal:     boolean
  topSignal:     QueueItem | null
  topTimestamp:  number | null
  watchingCount: number
  isLoading:     boolean
  isFree:        boolean
  canSeeSignal:  (ts: string | number | null | undefined) => boolean
  showLevels:    boolean
  onViewSignals: () => void
}) {
  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="h-4 w-48 rounded shimmer mb-2" />
        <div className="h-3 w-64 rounded shimmer" />
      </div>
    )
  }

  if (hasSignal && topSignal) {
    const dirCfg        = getDirectionConfig(topSignal.direction)
    const DirIcon       = dirCfg?.icon
    const signalVisible = !isFree || canSeeSignal(topTimestamp)

    if (!signalVisible) {
      return (
        <div className="rounded-lg border border-border bg-card p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-3">
              <div className="flex items-center gap-2.5">
                <GradeTag grade={topSignal.grade} size="lg" />
                <span className="font-mono font-semibold text-foreground text-sm">{topSignal.coin}USDT</span>
              </div>
              <SignalCountdown timestamp={topTimestamp} />
            </div>
            <div className="shrink-0 text-right">
              <p className="text-xs text-muted-foreground">{topSignal.session}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{topSignal.regime}</p>
            </div>
          </div>
        </div>
      )
    }

    return (
      <motion.div
        initial   = {{ opacity: 0, y: 6 }}
        animate   = {{ opacity: 1, y: 0 }}
        onClick   = {onViewSignals}
        className = "rounded-lg border border-border bg-card p-6 cursor-pointer hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-3 min-w-0 flex-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <GradeTag grade={topSignal.grade} size="lg" />
              <span className="font-mono font-semibold text-foreground text-sm">{topSignal.coin}USDT</span>
              {dirCfg && DirIcon && (
                <span className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium', dirCfg.bg, dirCfg.text, dirCfg.border)}>
                  <DirIcon className="h-3 w-3" />
                  {topSignal.direction}
                </span>
              )}
              <span className="text-xs text-muted-foreground font-mono">Score {topSignal.score}</span>
            </div>
            {showLevels && topSignal.entry && (
              <div className="flex items-center gap-6">
                <div>
                  <p className="label-xs">Entry</p>
                  <p className="text-sm font-mono font-semibold text-foreground mt-0.5">
                    ${topSignal.entry.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                  </p>
                </div>
                {topSignal.sl && (
                  <div>
                    <p className="label-xs">Stop Loss</p>
                    <p className="text-sm font-mono font-semibold text-[hsl(var(--chart-2))] mt-0.5">
                      ${topSignal.sl.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                    </p>
                  </div>
                )}
                {topSignal.tp1 && (
                  <div>
                    <p className="label-xs">Take Profit</p>
                    <p className="text-sm font-mono font-semibold text-[hsl(var(--chart-1))] mt-0.5">
                      ${topSignal.tp1.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                    </p>
                  </div>
                )}
              </div>
            )}
            {!showLevels && (
              <div className="flex items-center gap-1.5">
                <Lock className="h-3 w-3 text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  Entry / SL / TP —{' '}
                  <a href="/pricing" className="underline underline-offset-2 hover:text-foreground transition-colors">
                    Upgrade to Pro
                  </a>
                </span>
              </div>
            )}
          </div>
          <div className="shrink-0 text-right">
            <p className="text-xs text-muted-foreground">{topSignal.session}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{topSignal.regime}</p>
            <p className="text-xs font-medium text-foreground mt-3">View signal</p>
          </div>
        </div>
      </motion.div>
    )
  }

  return (
    <div
      onClick   = {onViewSignals}
      className = "rounded-lg border border-border bg-card p-6 cursor-pointer hover:bg-muted/30 transition-colors"
    >
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-muted">
          <Radio className="h-4 w-4 text-muted-foreground" />
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">
            {watchingCount > 0
              ? `${watchingCount} coin${watchingCount !== 1 ? 's' : ''} in active watch`
              : 'Scanning market for setups'
            }
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {watchingCount > 0
              ? 'Waiting for trigger confirmation'
              : 'No setups detected — scanning every 15 minutes'
            }
          </p>
        </div>
      </div>
    </div>
  )
}

function SignalQueue({ queue, onNavigate }: { queue: QueueItem[]; onNavigate: () => void }) {
  const { hasFeature, isAdmin } = useAuthStore()
  const { canSeeSignal, isFree } = useSignalAccess()
  const showLevels               = hasFeature('show_levels') || isAdmin
  const filtered                 = queue.filter(i => ['A+', 'A'].includes(i.grade))

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-6 py-4">
        <p className="text-sm font-semibold text-foreground">Signal Queue</p>
        <div className="flex items-center gap-3">
          <span className="label-xs">{filtered.length} active</span>
          <button onClick={onNavigate} className="text-xs font-medium text-foreground hover:text-muted-foreground transition-colors">
            View all
          </button>
        </div>
      </div>
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-center px-6">
          <p className="text-sm font-medium text-foreground">No A+/A signals active</p>
          <p className="text-xs text-muted-foreground mt-1">
            {queue.length > 0
              ? `${queue.length} coin${queue.length !== 1 ? 's' : ''} watching — waiting for trigger`
              : 'Signals appear here when A+/A grades confirm'
            }
          </p>
          <button onClick={onNavigate} className="mt-3 text-xs font-medium text-foreground hover:text-muted-foreground transition-colors">
            View watching coins
          </button>
        </div>
      ) : (
        <div className="divide-y divide-border">
          {filtered.slice(0, 5).map((item, i) => {
            const dirCfg  = getDirectionConfig(item.direction)
            const DirIcon = dirCfg?.icon
            const visible = !isFree || canSeeSignal(null)

            return (
              <motion.div
                key        = {`${item.coin}-${i}`}
                initial    = {{ opacity: 0, x: -6 }}
                animate    = {{ opacity: 1, x: 0  }}
                transition = {{ delay: i * 0.04 }}
                onClick    = {visible ? onNavigate : undefined}
                className  = {cn(
                  'flex items-center justify-between px-6 py-3.5 transition-colors',
                  visible ? 'cursor-pointer hover:bg-muted/30' : 'cursor-default'
                )}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <GradeTag grade={item.grade} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-foreground text-sm">{item.coin}</span>
                      {dirCfg && DirIcon && visible && (
                        <span className={cn('inline-flex items-center gap-1 rounded border px-1.5 py-px text-xs font-medium', dirCfg.bg, dirCfg.text, dirCfg.border)}>
                          <DirIcon className="h-3 w-3" />
                          {item.direction}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">{item.session}</p>
                  </div>
                </div>
                {visible && (
                  <div className="text-right shrink-0 ml-3">
                    <p className="text-sm font-mono font-semibold text-foreground">{item.score}</p>
                    {showLevels && item.entry ? (
                      <p className="text-xs font-mono text-muted-foreground mt-0.5">
                        ${item.entry.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground mt-0.5">score</p>
                    )}
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function MLProgress({ progress }: { progress: { closed: number; required: number; pct: number; message: string } }) {
  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="border-b border-border px-6 py-4">
        <p className="text-sm font-semibold text-foreground">ML Gate Progress</p>
      </div>
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-foreground font-mono">{progress.closed} / {progress.required}</span>
          <span className={cn(
            'text-xs font-medium px-2 py-0.5 rounded-md border',
            progress.pct >= 100
              ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.08)] text-[hsl(var(--chart-1))]'
              : 'border-[hsl(var(--chart-4)/0.2)] bg-[hsl(var(--chart-4)/0.08)] text-[hsl(var(--chart-4))]'
          )}>
            {progress.pct >= 100 ? 'Active' : `${progress.pct}%`}
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <motion.div
            initial    = {{ width: 0 }}
            animate    = {{ width: `${progress.pct}%` }}
            transition = {{ duration: 0.8, ease: 'easeOut' }}
            className  = {cn('h-full rounded-full', progress.pct >= 100 ? 'bg-[hsl(var(--chart-1))]' : 'bg-[hsl(var(--chart-4))]')}
          />
        </div>
        <p className="text-xs text-muted-foreground">{progress.message}</p>
        <div className="rounded-md border border-border bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground leading-relaxed">
            ML activates after {progress.required} closed trades. It learns which setups win and filters low-probability signals automatically.
          </p>
        </div>
      </div>
    </div>
  )
}