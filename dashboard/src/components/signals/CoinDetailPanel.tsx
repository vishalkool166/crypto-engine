import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { formatPrice, formatCurrency } from '@/lib/utils'
import { getDirectionConfig } from '@/lib/tokens'
import GradeTag from '@/components/ui/GradeTag'
import { LockedSection } from '@/components/ui/TierGate'
import SignalCountdown from '@/components/ui/SignalCountdown'
import { useAuthStore } from '@/stores/authStore'
import { useSignalAccess } from '@/hooks/useSignalAccess'
import { useCoinDetail } from '@/hooks/useSignals'
import { useDemoStore } from '@/demo/demoStore'
import { mockRadar, mockQueue } from '@/demo/mockData'
import type { CoinDetail, RadarItem } from '@/types'

function DetailBox({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <p className="label-xs">{label}</p>
      <p className={cn('text-xs font-mono font-semibold text-foreground mt-1', valueClass)}>{value}</p>
    </div>
  )
}

function LevelBox({ label, value, color, sub }: { label: string; value: string; color: string; sub?: string }) {
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <p className="label-xs">{label}</p>
      <p className={cn('text-xs font-mono font-semibold mt-1', color)}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  )
}

function useDemoCoinDetail(coin: string | null) {
  if (!coin) return { data: null, isLoading: false }
  const radar = mockRadar.find(r => r.coin === coin)
  const queue = mockQueue.find(q => q.coin === coin)
  if (!radar) return { data: null, isLoading: false }

  const detail: CoinDetail = {
    coin:      radar.coin,
    grade:     radar.grade,
    score:     radar.score,
    direction: radar.direction,
    regime:    radar.regime,
    session:   radar.session,
    state:     radar.state,
    market: {
      price:      radar.price,
      change:     radar.change,
      change_pos: radar.change_pos,
      funding:    radar.funding,
    },
    signal: {
      entry:    queue?.entry    ?? null,
      sl:       queue?.sl       ?? null,
      tp1:      queue?.tp1      ?? null,
      sl_pct:   queue?.sl_pct   ?? null,
      risk_amt: queue?.risk_amt ?? null,
      leverage: queue?.leverage ?? null,
      stake:    queue?.stake    ?? null,
    },
  }

  return { data: detail, isLoading: false }
}

interface Props {
  coin:       string
  expanded:   boolean
  timestamp?: number | null
}

export default function CoinDetailPanel({ coin, expanded, timestamp }: Props) {
  const { hasFeature, isAdmin } = useAuthStore()
  const { isDemoMode }          = useDemoStore()
  const { isFree, canSeeSignal } = useSignalAccess()

  const showLevels = hasFeature('show_levels') || isAdmin

  const signalVisible = !isFree || canSeeSignal(timestamp)

  const realDetail = useCoinDetail(expanded && !isDemoMode ? coin : null)
  const demoDetail = useDemoCoinDetail(expanded && isDemoMode ? coin : null)
  const { data: detail } = isDemoMode ? demoDetail : realDetail

  return (
    <AnimatePresence>
      {expanded && (
        <motion.div
          initial    = {{ height: 0, opacity: 0 }}
          animate    = {{ height: 'auto', opacity: 1 }}
          exit       = {{ height: 0, opacity: 0 }}
          transition = {{ duration: 0.2 }}
          className  = "overflow-hidden border-t border-border bg-muted/10"
        >
          <div className="px-6 py-5 space-y-4">
            {!signalVisible ? (
              <SignalCountdown timestamp={timestamp} />
            ) : !detail ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-border border-t-foreground" />
                Loading...
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <DetailBox label="Price"   value={formatPrice(detail.market?.price)} />
                  <DetailBox
                    label      = "24h Change"
                    value      = {`${(detail.market?.change ?? 0) >= 0 ? '+' : ''}${(detail.market?.change ?? 0).toFixed(2)}%`}
                    valueClass = {(detail.market?.change ?? 0) >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'}
                  />
                  <DetailBox label="Score"   value={detail.score > 0 ? String(detail.score) : '—'} />
                  <DetailBox label="Funding" value={`${((detail.market?.funding ?? 0) * 100).toFixed(4)}%`} />
                </div>

                <div className="grid grid-cols-2 gap-3 md:grid-cols-2">
                  <DetailBox label="Regime"  value={detail.regime  || '—'} />
                  <DetailBox label="Session" value={detail.session || '—'} />
                </div>

                {showLevels && detail.signal?.entry && detail.signal.entry > 0 ? (
                  <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    <LevelBox
                      label = "Entry"
                      value = {formatPrice(detail.signal.entry)}
                      color = "text-foreground"
                    />
                    <LevelBox
                      label = "Stop Loss"
                      value = {formatPrice(detail.signal.sl)}
                      color = "text-[hsl(var(--chart-2))]"
                      sub   = {detail.signal.sl_pct ? `${detail.signal.sl_pct.toFixed(2)}%` : undefined}
                    />
                    <LevelBox
                      label = "Take Profit"
                      value = {formatPrice(detail.signal.tp1)}
                      color = "text-[hsl(var(--chart-1))]"
                    />
                    <LevelBox
                      label = "Risk"
                      value = {detail.signal.risk_amt ? formatCurrency(detail.signal.risk_amt) : '—'}
                      color = "text-muted-foreground"
                      sub   = {detail.signal.leverage ? `${detail.signal.leverage}x` : undefined}
                    />
                  </div>
                ) : !showLevels ? (
                  <LockedSection
                    requiredTier = "pro"
                    title        = "Entry Levels"
                    description  = "Upgrade to Pro to see entry, stop loss, and take profit levels"
                    rows         = {1}
                  />
                ) : null}
              </>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}