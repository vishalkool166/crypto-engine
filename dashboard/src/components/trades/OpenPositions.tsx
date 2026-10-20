import { motion } from 'framer-motion'
import { ShieldAlert } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatPrice, formatCurrency, formatPercent } from '@/lib/utils'
import { getDirectionConfig, getHealthConfig, pnlColor } from '@/lib/tokens'
import GradeTag from '@/components/ui/GradeTag'
import TradeProgressBar from '@/components/ui/TradeProgressBar'
import EmptyState from '@/components/ui/EmptyState'
import { Activity } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { Trade } from '@/types'

function useTimer(openedAt: string | null | undefined): string {
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 1000)
    return () => clearInterval(id)
  }, [])
  if (!openedAt) return '—'
  try {
    const dt   = new Date(openedAt.includes('Z') || openedAt.includes('+') ? openedAt : openedAt + 'Z')
    const diff = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 1000))
    const h    = Math.floor(diff / 3600)
    const m    = Math.floor((diff % 3600) / 60)
    const s    = diff % 60
    return h > 0 ? `${h}h ${m}m` : `${m}m ${s}s`
  } catch { return '—' }
}

interface TradeRowProps {
  trade:       Trade
  index:       number
  selected:    boolean
  onClick:     () => void
  onForceSell: () => void
}

function TradeRow({ trade, index, selected, onClick, onForceSell }: TradeRowProps) {
  const timer   = useTimer(trade.opened_at)
  const pnl     = trade.profit_abs ?? 0
  const dirCfg  = getDirectionConfig(trade.direction)
  const DirIcon = dirCfg?.icon
  const health  = trade.health
  const hCfg    = health ? getHealthConfig(health.state) : null

  return (
    <motion.div
      initial    = {{ opacity: 0, y: 4 }}
      animate    = {{ opacity: 1, y: 0 }}
      transition = {{ delay: index * 0.04 }}
      onClick    = {onClick}
      className  = {cn(
        'p-6 cursor-pointer hover:bg-muted/20 transition-colors space-y-4',
        selected && 'bg-muted/20',
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GradeTag grade={trade.grade as never} />
          {dirCfg && DirIcon && (
            <span className={cn(
              'inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium',
              dirCfg.bg, dirCfg.text, dirCfg.border
            )}>
              <DirIcon className="h-3 w-3" />
              {trade.coin}USDT
            </span>
          )}
          {hCfg && (
            <span className={cn('text-xs font-medium flex items-center gap-1', hCfg.text)}>
              <span className={cn('h-1.5 w-1.5 rounded-full', hCfg.dot)} />
              {health?.state}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-muted-foreground">{timer}</span>
          <span className={cn('font-mono text-sm font-semibold', pnlColor(pnl))}>
            {formatCurrency(pnl)}
          </span>
          <button
            onClick   = {e => { e.stopPropagation(); onForceSell() }}
            className = "flex items-center gap-1 rounded-md border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-2 py-1 text-xs font-medium text-[hsl(var(--chart-2))] hover:bg-[hsl(var(--chart-2)/0.12)] transition-colors"
          >
            <ShieldAlert className="h-3 w-3" />
            <span className="hidden sm:inline">Sell</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <LevelItem label="Entry"   value={formatPrice(trade.entry_price)}   />
        <LevelItem label="Current" value={formatPrice(trade.current_price)} color={pnlColor(pnl)} />
        <LevelItem label="SL"      value={trade.sl_price  ? formatPrice(trade.sl_price)  : '—'} color="text-[hsl(var(--chart-2))]" />
        <LevelItem label="TP"      value={trade.tp1_price ? formatPrice(trade.tp1_price) : '—'} color="text-[hsl(var(--chart-1))]" />
      </div>

      {trade.entry_price && trade.sl_price && trade.tp1_price && trade.current_price && (
        <TradeProgressBar
          entry   = {trade.entry_price}
          sl      = {trade.sl_price}
          tp1     = {trade.tp1_price}
          current = {trade.current_price}
          isShort = {trade.is_short}
        />
      )}

      {health && (health.failures.length > 0 || health.warnings.length > 0) && (
        <p className={cn(
          'text-xs rounded-md px-3 py-2',
          health.failures.length > 0
            ? 'bg-[hsl(var(--chart-2)/0.06)] text-[hsl(var(--chart-2))]'
            : 'bg-[hsl(var(--chart-4)/0.06)] text-[hsl(var(--chart-4))]'
        )}>
          {health.failures[0] ?? health.warnings[0]}
        </p>
      )}
    </motion.div>
  )
}

function LevelItem({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <p className="label-xs">{label}</p>
      <p className={cn('text-xs font-mono font-semibold text-foreground mt-0.5', color)}>
        {value}
      </p>
    </div>
  )
}

interface Props {
  trades:          Trade[]
  selectedTradeId: number | null
  onSelect:        (trade: Trade) => void
  onForceSell:     (trade: Trade) => void
}

export default function OpenPositions({ trades, selectedTradeId, onSelect, onForceSell }: Props) {
  if (trades.length === 0) {
    return (
      <EmptyState
        icon        = {Activity}
        title       = "No open trades"
        description = "Positions appear here when trades open"
        compact
      />
    )
  }

  return (
    <div className="divide-y divide-border">
      {trades.map((trade, i) => (
        <TradeRow
          key         = {trade.trade_id}
          trade       = {trade}
          index       = {i}
          selected    = {selectedTradeId === trade.trade_id}
          onClick     = {() => onSelect(trade)}
          onForceSell = {() => onForceSell(trade)}
        />
      ))}
    </div>
  )
}