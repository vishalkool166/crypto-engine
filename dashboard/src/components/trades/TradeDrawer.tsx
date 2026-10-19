import { X, ShieldAlert } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  formatPrice, formatCurrency, formatDateTime,
  formatDuration, formatPercent,
} from '@/lib/utils'
import { getDirectionConfig, getHealthConfig, getCloseReasonConfig, pnlColor } from '@/lib/tokens'
import TradeProgressBar from '@/components/ui/TradeProgressBar'
import TradeJourneyChart from '@/components/ui/TradeJourneyChart'
import { useTradeJourney } from '@/hooks/useTrades'
import type { Trade } from '@/types'

interface Props {
  trade:       Trade
  onClose:     () => void
  onForceSell: () => void
}

function Row({
  label,
  value,
  mono   = false,
  color,
  border = false,
}: {
  label:   string
  value:   string
  mono?:   boolean
  color?:  string
  border?: boolean
}) {
  return (
    <div className={cn(
      'flex items-center justify-between gap-3 py-1',
      border && 'border-t border-border pt-2 mt-1'
    )}>
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      <span className={cn('text-xs font-medium text-right', mono && 'font-mono', color ?? 'text-foreground')}>
        {value}
      </span>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-background p-4 space-y-1">
      <p className="label-xs mb-3">{title}</p>
      {children}
    </div>
  )
}

function JourneySection({ tradeId, direction }: { tradeId: number; direction: string }) {
  const { data, isLoading } = useTradeJourney(tradeId)
  const journey             = data?.journey ?? []

  return (
    <Section title="Trade Journey">
      {isLoading ? (
        <div className="flex items-center justify-center py-6">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-foreground" />
        </div>
      ) : journey.length === 0 ? (
        <p className="text-xs text-muted-foreground py-2">
          No journey data yet — collecting every 60 seconds
        </p>
      ) : (
        <TradeJourneyChart
          journey   = {journey}
          market    = "crypto"
          height    = {160}
          direction = {direction as 'LONG' | 'SHORT'}
        />
      )}
    </Section>
  )
}

export default function TradeDrawer({ trade, onClose, onForceSell }: Props) {
  const isOpen    = trade.is_open ?? false
  const pnl       = isOpen ? (trade.profit_abs ?? 0) : (trade.pnl ?? 0)
  const dirCfg    = getDirectionConfig(trade.direction)
  const DirIcon   = dirCfg?.icon
  const health    = trade.health
  const hCfg      = health ? getHealthConfig(health.state) : null
  const reasonCfg = getCloseReasonConfig(trade.close_reason)

  const entryFee   = trade.entry_commission   ?? 0
  const exitFee    = trade.exit_commission    ?? 0
  const fundingFee = Math.abs(trade.funding_fees_paid ?? 0)
  const totalCosts = entryFee + exitFee + fundingFee

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-border px-5 py-4 shrink-0">
        <div className="flex items-center gap-2.5">
          {dirCfg && DirIcon && (
            <span className={cn('font-mono font-semibold text-sm', dirCfg.text)}>
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
        <button
          onClick   = {onClose}
          className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        <div className={cn(
          'rounded-lg border p-5',
          pnl >= 0
            ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.04)]'
            : 'border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.04)]'
        )}>
          <p className="label-xs mb-1">{isOpen ? 'Unrealized PnL (Gross)' : 'Net PnL'}</p>
          <p className={cn('value-lg', pnlColor(pnl))}>{formatCurrency(pnl)}</p>
        </div>

        {trade.entry_price && trade.sl_price && trade.tp1_price && trade.current_price && (
          <TradeProgressBar
            entry      = {trade.entry_price}
            sl         = {trade.sl_price}
            tp1        = {trade.tp1_price}
            current    = {trade.current_price}
            isShort    = {trade.is_short}
            showLabels
          />
        )}

        <JourneySection tradeId={trade.trade_id} direction={trade.direction} />

        <Section title="Levels">
          <Row label="Entry"       value={formatPrice(trade.entry_price)}   mono />
          <Row label="Current"     value={formatPrice(trade.current_price)} mono />
          <Row label="Stop Loss"   value={trade.sl_price  ? formatPrice(trade.sl_price)  : '—'} mono color="text-[hsl(var(--chart-2))]" />
          <Row label="Take Profit" value={trade.tp1_price ? formatPrice(trade.tp1_price) : '—'} mono color="text-[hsl(var(--chart-1))]" />
        </Section>

        <Section title="Position">
          <Row label="Margin"   value={formatCurrency(trade.margin_used)} mono />
          <Row label="Leverage" value={`${trade.leverage}x`}             mono color="text-[hsl(var(--chart-3))]" />
          <Row label="Size"     value={formatCurrency((trade.margin_used ?? 0) * (trade.leverage ?? 1))} mono />
        </Section>

        <Section title="Execution">
          <Row label="Entry Fill" value={formatPrice(trade.actual_fill_entry ?? trade.entry_price)} mono />
          <Row label="Entry Role" value={trade.entry_role ?? 'taker'} />
          {(trade.slippage_entry_pct ?? 0) > 0.05 && (
            <Row
              label = "Entry Slip"
              value = {formatPercent(trade.slippage_entry_pct ?? 0)}
              mono
              color = {(trade.slippage_entry_pct ?? 0) > 0.1 ? 'text-[hsl(var(--chart-2))]' : 'text-[hsl(var(--chart-4))]'}
            />
          )}
          {trade.exit_price && (
            <>
              <Row label="Exit Fill" value={formatPrice(trade.actual_fill_exit ?? trade.exit_price)} mono />
              <Row label="Exit Role" value={trade.exit_role ?? '—'} />
              {(trade.slippage_exit_pct ?? 0) > 0.05 && (
                <Row
                  label = "Exit Slip"
                  value = {formatPercent(trade.slippage_exit_pct ?? 0)}
                  mono
                  color = {(trade.slippage_exit_pct ?? 0) > 0.1 ? 'text-[hsl(var(--chart-2))]' : 'text-[hsl(var(--chart-4))]'}
                />
              )}
            </>
          )}
          {reasonCfg && (
            <Row label="Close Reason" value={reasonCfg.label} />
          )}
        </Section>

        <Section title="Costs">
          <Row label="Entry Fee"   value={formatCurrency(-entryFee)}   mono color="text-muted-foreground" />
          <Row label="Exit Fee"    value={formatCurrency(-exitFee)}    mono color="text-muted-foreground" />
          <Row label="Funding"     value={formatCurrency(-fundingFee)} mono color="text-muted-foreground" />
          <Row label="Total Costs" value={formatCurrency(-totalCosts)} mono border />
        </Section>

        {((trade.mae !== null && trade.mae !== undefined) ||
          (trade.mfe !== null && trade.mfe !== undefined)) && (
          <Section title="Trade Quality">
            {trade.mae !== null && trade.mae !== undefined && (
              <Row
                label = "MAE"
                value = {`${(trade.mae ?? 0).toFixed(3)}%`}
                mono
                color = {trade.mae > 1.5 ? 'text-[hsl(var(--chart-2))]' : 'text-muted-foreground'}
              />
            )}
            {trade.mfe !== null && trade.mfe !== undefined && (
              <Row label="MFE" value={`${(trade.mfe ?? 0).toFixed(3)}%`} mono color="text-[hsl(var(--chart-1))]" />
            )}
            {trade.mae && trade.mfe && trade.mae > 0 && (
              <Row
                label = "MFE/MAE"
                value = {`${((trade.mfe ?? 0) / (trade.mae ?? 1)).toFixed(2)}x`}
                mono
                color = {trade.mfe / trade.mae >= 2 ? 'text-[hsl(var(--chart-1))]' : 'text-muted-foreground'}
              />
            )}
          </Section>
        )}

        <Section title="Context">
          <Row label="Grade"    value={trade.grade ?? '—'} />
          <Row label="Score"    value={`${trade.score_at_entry ?? 0}`}  mono />
          <Row label="Session"  value={trade.session_at_entry ?? '—'} />
          <Row label="Regime"   value={trade.regime_at_entry  ?? '—'} />
          <Row label="Version"  value={trade.system_version   ?? '—'} mono />
          <Row label="Opened"   value={formatDateTime(trade.opened_at)} />
          {trade.closed_at && (
            <Row label="Closed" value={formatDateTime(trade.closed_at)} />
          )}
          {trade.duration_hours && (
            <Row label="Duration" value={formatDuration(trade.duration_hours)} mono />
          )}
        </Section>

        {health && (health.failures.length > 0 || health.warnings.length > 0) && (
          <Section title="Health">
            {health.failures.map((f, i) => (
              <p key={i} className="text-xs text-[hsl(var(--chart-2))] py-0.5">{f}</p>
            ))}
            {health.warnings.map((w, i) => (
              <p key={i} className="text-xs text-[hsl(var(--chart-4))] py-0.5">{w}</p>
            ))}
          </Section>
        )}

        {isOpen && (
          <button
            onClick   = {onForceSell}
            className = "w-full flex items-center justify-center gap-2 rounded-lg border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-4 py-3 text-sm font-medium text-[hsl(var(--chart-2))] hover:bg-[hsl(var(--chart-2)/0.12)] transition-colors"
          >
            <ShieldAlert className="h-4 w-4" />
            Force Sell Position
          </button>
        )}
      </div>
    </div>
  )
}