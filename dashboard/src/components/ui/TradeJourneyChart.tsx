import { useMemo } from 'react'
import {
  ComposedChart, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Area,
} from 'recharts'
import { cn } from '@/lib/utils'
import { format } from 'date-fns'

interface JourneyPoint {
  timestamp:   string | null
  price:       number
  pnl_pts:     number | null
  pnl_pct:     number | null
  is_entry:    boolean
  is_exit:     boolean
  entry_price: number
  sl_price:    number | null
  tp_price:    number | null
}

interface Props {
  journey:    JourneyPoint[]
  market?:    'crypto' | 'indian'
  direction?: 'LONG' | 'SHORT'
  className?: string
  height?:    number
}

interface ChartPoint {
  time:        string
  price:       number
  pnl_pts:     number
  pnl_pct:     number
  is_entry:    boolean
  is_exit:     boolean
  profit_side: number | null
  loss_side:   number | null
}

function formatTime(ts: string | null): string {
  if (!ts) return ''
  try {
    return format(new Date(ts.includes('Z') || ts.includes('+') ? ts : ts + 'Z'), 'HH:mm')
  } catch {
    return ''
  }
}

function formatPrice(price: number): string {
  if (price >= 1000) return price.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (price >= 1)    return price.toFixed(2)
  return price.toFixed(6)
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartPoint }> }) => {
  if (!active || !payload?.length) return null
  const d        = payload[0].payload
  const pnlColor = d.pnl_pts >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
  const sign     = d.pnl_pts >= 0 ? '+' : ''

  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-lg text-xs space-y-1">
      <p className="text-muted-foreground">{d.time}</p>
      <p className="font-mono font-semibold text-foreground">{formatPrice(d.price)}</p>
      <p className={cn('font-mono font-semibold', pnlColor)}>
        {sign}{d.pnl_pct.toFixed(3)}%
      </p>
      {d.is_entry && <p className="text-[hsl(var(--chart-3))] font-medium">Entry</p>}
      {d.is_exit  && <p className="text-[hsl(var(--chart-4))] font-medium">Exit</p>}
    </div>
  )
}

export default function TradeJourneyChart({ journey, direction = 'LONG', className, height = 200 }: Props) {
  const isShort = direction === 'SHORT'

  const chartData = useMemo((): ChartPoint[] => {
    if (!journey || journey.length === 0) return []

    const sampled = journey.length > 200
      ? journey.filter((_, i) =>
          i === 0 ||
          i === journey.length - 1 ||
          journey[i].is_entry ||
          journey[i].is_exit ||
          i % Math.floor(journey.length / 200) === 0
        )
      : journey

    return sampled.map(p => {
      const entry   = p.entry_price
      const price   = p.price
      const pnl_pts = p.pnl_pts ?? 0
      const pnl_pct = p.pnl_pct ?? 0

      const inProfit = isShort ? price <= entry : price >= entry
      const inLoss   = isShort ? price >  entry : price <  entry

      return {
        time:        formatTime(p.timestamp),
        price,
        pnl_pts,
        pnl_pct,
        is_entry:    p.is_entry,
        is_exit:     p.is_exit,
        profit_side: inProfit ? price : null,
        loss_side:   inLoss   ? price : null,
      }
    })
  }, [journey, isShort])

  if (chartData.length === 0) {
    return (
      <div
        className = {cn('flex items-center justify-center rounded-lg border border-border bg-muted/30', className)}
        style     = {{ height }}
      >
        <p className="text-xs text-muted-foreground">No journey data yet</p>
      </div>
    )
  }

  const entry    = journey[0]?.entry_price ?? 0
  const sl       = journey[0]?.sl_price    ?? null
  const tp       = journey[0]?.tp_price    ?? null
  const prices   = chartData.map(d => d.price)
  const minPrice = Math.min(...prices, ...(sl ? [sl] : [])) * 0.9995
  const maxPrice = Math.max(...prices, ...(tp ? [tp] : [])) * 1.0005

  return (
    <div className={cn('', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="gradProfit" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="hsl(var(--chart-1))" stopOpacity={0.15} />
              <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0}    />
            </linearGradient>
            <linearGradient id="gradLoss" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="hsl(var(--chart-2))" stopOpacity={0}    />
              <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0.15} />
            </linearGradient>
          </defs>

          <CartesianGrid
            strokeDasharray = "3 3"
            stroke          = "hsl(var(--border))"
            vertical        = {false}
          />

          <XAxis
            dataKey  = "time"
            tick     = {{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            axisLine = {false}
            tickLine = {false}
            interval = "preserveStartEnd"
          />

          <YAxis
            domain        = {[minPrice, maxPrice]}
            tick          = {{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            axisLine      = {false}
            tickLine      = {false}
            tickFormatter = {v => formatPrice(v)}
            width         = {60}
          />

          <Tooltip content={<CustomTooltip />} />

          <ReferenceLine
            y               = {entry}
            stroke          = "hsl(var(--foreground))"
            strokeWidth     = {1}
            strokeDasharray = "4 4"
            label           = {{ value: 'Entry', position: 'insideTopRight', fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
          />

          {sl && (
            <ReferenceLine
              y               = {sl}
              stroke          = "hsl(var(--chart-2))"
              strokeWidth     = {1}
              strokeDasharray = "4 4"
              label           = {{ value: 'SL', position: 'insideTopRight', fontSize: 10, fill: 'hsl(var(--chart-2))' }}
            />
          )}

          {tp && (
            <ReferenceLine
              y               = {tp}
              stroke          = "hsl(var(--chart-1))"
              strokeWidth     = {1}
              strokeDasharray = "4 4"
              label           = {{ value: 'TP', position: 'insideTopRight', fontSize: 10, fill: 'hsl(var(--chart-1))' }}
            />
          )}

          <Area
            type         = "monotone"
            dataKey      = "profit_side"
            stroke       = "hsl(var(--chart-1))"
            strokeWidth  = {1.5}
            fill         = "url(#gradProfit)"
            dot          = {false}
            connectNulls = {false}
            baseValue    = {entry}
          />

          <Area
            type         = "monotone"
            dataKey      = "loss_side"
            stroke       = "hsl(var(--chart-2))"
            strokeWidth  = {1.5}
            fill         = "url(#gradLoss)"
            dot          = {false}
            connectNulls = {false}
            baseValue    = {entry}
          />

        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}