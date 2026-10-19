import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { formatPrice } from '@/lib/utils'

interface TradeProgressBarProps {
  entry:       number
  sl:          number
  tp1:         number
  tp2?:        number | null
  current:     number
  isShort:     boolean
  showLabels?: boolean
  className?:  string
}

function clamp(v: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, v))
}

export default function TradeProgressBar({
  entry,
  sl,
  tp1,
  tp2,
  current,
  isShort,
  showLabels = false,
  className,
}: TradeProgressBarProps) {
  const hasTP2 = tp2 !== null && tp2 !== undefined && tp2 > 0

  // LEFT is always SL, RIGHT is always TP
  // Long:  left = SL (low price),  right = TP (high price) → ascending
  // Short: left = SL (high price), right = TP (low price)  → descending
  const leftEdge  = sl
  const rightEdge = hasTP2 ? tp2! : tp1

  // For long:  range = tp - sl (positive, ascending)
  // For short: range = tp - sl (negative, descending)
  const range = rightEdge - leftEdge

  if (range === 0) return null

  const toPercent = (price: number) =>
    clamp(((price - leftEdge) / range) * 100)

  const entryPct   = toPercent(entry)
  const currentPct = toPercent(current)

  const inProfit = isShort ? current < entry : current > entry

  const fillColor = inProfit
    ? 'hsl(var(--chart-1))'
    : 'hsl(var(--chart-2))'

  // Left of entry = loss zone (toward SL), Right of entry = profit zone (toward TP)
  const background = `linear-gradient(to right,
    hsl(var(--chart-2) / 0.15) 0%,
    hsl(var(--chart-2) / 0.15) ${entryPct}%,
    hsl(var(--chart-1) / 0.12) ${entryPct}%,
    hsl(var(--chart-1) / 0.12) 100%
  )`

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="relative h-2 w-full rounded-full overflow-hidden bg-muted">
        <div
          className="absolute inset-0"
          style={{ background }}
        />
        <motion.div
          className  = "absolute top-0 left-0 h-full rounded-full"
          initial    = {{ width: 0 }}
          animate    = {{ width: `${currentPct}%` }}
          transition = {{ duration: 0.4, ease: 'easeOut' }}
          style      = {{ background: fillColor, opacity: 0.85 }}
        />
        <div
          className="absolute top-0 h-full w-0.5 bg-foreground/30"
          style={{ left: `${entryPct}%` }}
        />
      </div>

      {showLabels && (
        <div className="relative h-4">
          <span className="absolute left-0 text-[10px] text-[hsl(var(--chart-2))] font-medium">
            {formatPrice(sl)}
          </span>
          <span
            className="absolute text-[10px] text-muted-foreground -translate-x-1/2"
            style={{ left: `${entryPct}%` }}
          >
            {formatPrice(entry)}
          </span>
          <span className="absolute right-0 text-[10px] text-[hsl(var(--chart-1))] font-medium">
            {formatPrice(tp1)}
          </span>
        </div>
      )}
    </div>
  )
}