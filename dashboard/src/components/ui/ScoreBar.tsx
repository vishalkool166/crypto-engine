import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { scoreToBarColor, scoreToColor } from '@/lib/tokens'

interface ScoreBarProps {
  score:      number
  max?:       number
  label?:     string
  showValue?: boolean
  size?:      'sm' | 'md'
  className?: string
  animate?:   boolean
}

export default function ScoreBar({
  score,
  max       = 100,
  label,
  showValue = true,
  size      = 'md',
  className,
  animate   = true,
}: ScoreBarProps) {
  const pct      = Math.min(100, Math.max(0, (score / max) * 100))
  const barColor = scoreToBarColor(score)
  const txtColor = scoreToColor(score)

  return (
    <div className={cn('space-y-1', className)}>
      {(label || showValue) && (
        <div className="flex items-center justify-between gap-2">
          {label && (
            <span className="text-xs text-muted-foreground capitalize">
              {label}
            </span>
          )}
          {showValue && (
            <span className={cn('text-xs font-mono font-medium', txtColor)}>
              {score}/{max}
            </span>
          )}
        </div>
      )}
      <div
        className={cn(
          'w-full rounded-full bg-muted overflow-hidden',
          size === 'sm' ? 'h-1' : 'h-1.5'
        )}
      >
        {animate ? (
          <motion.div
            initial    = {{ width: 0 }}
            animate    = {{ width: `${pct}%` }}
            transition = {{ duration: 0.5, ease: 'easeOut' }}
            className  = {cn('h-full rounded-full', barColor)}
          />
        ) : (
          <div
            className = {cn('h-full rounded-full', barColor)}
            style     = {{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  )
}