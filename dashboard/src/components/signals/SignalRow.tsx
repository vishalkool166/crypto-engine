import { motion } from 'framer-motion'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatPrice, formatPercent } from '@/lib/utils'
import { getDirectionConfig, getStateConfig, scoreToColor } from '@/lib/tokens'
import GradeTag from '@/components/ui/GradeTag'
import type { RadarItem } from '@/types'

interface Props {
  item:     RadarItem
  index?:   number
  selected: boolean
  onSelect: () => void
}

export default function SignalRow({ item, index = 0, selected, onSelect }: Props) {
  const dirCfg   = getDirectionConfig(item.direction)
  const DirIcon  = dirCfg?.icon
  const stateCfg = getStateConfig(item.state ?? 'idle')

  return (
    <motion.div
      initial    = {{ opacity: 0 }}
      animate    = {{ opacity: 1 }}
      transition = {{ delay: Math.min(index * 0.01, 0.2) }}
      onClick    = {onSelect}
      className  = {cn(
        'flex items-center justify-between px-6 py-3.5',
        'cursor-pointer hover:bg-muted/30 transition-colors',
        selected && 'bg-muted/20',
      )}
    >
      <div className="flex items-center gap-4 min-w-0">
        <span className="font-mono font-semibold text-foreground text-sm w-14 shrink-0">
          {item.coin}
        </span>

        {item.grade && item.grade !== '--'
          ? <GradeTag grade={item.grade} />
          : <span className="w-8 text-xs text-muted-foreground/40">—</span>
        }

        {dirCfg && item.direction !== '--' ? (
          <span className={cn(
            'hidden sm:inline-flex items-center gap-1 rounded border px-1.5 py-px text-xs font-medium shrink-0',
            dirCfg.bg, dirCfg.text, dirCfg.border
          )}>
            <DirIcon className="h-3 w-3" />
            {item.direction}
          </span>
        ) : (
          <span className="hidden sm:block w-14 text-xs text-muted-foreground/40">—</span>
        )}

        <div className="hidden md:flex items-center gap-1.5">
          <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', stateCfg.dot)} />
          <span className={cn('text-xs', stateCfg.text)}>{stateCfg.label}</span>
        </div>

        {item.regime && item.regime !== '--' && (
          <span className="hidden lg:block text-xs text-muted-foreground truncate max-w-[120px]">
            {item.regime}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4 shrink-0">
        <div className="hidden sm:block text-right">
          <p className="text-xs font-mono text-foreground">
            {formatPrice(item.price)}
          </p>
          <p className={cn(
            'text-xs font-mono',
            (item.change ?? 0) >= 0
              ? 'text-[hsl(var(--chart-1))]'
              : 'text-[hsl(var(--chart-2))]'
          )}>
            {formatPercent(item.change ?? 0)}
          </p>
        </div>

        {(item.score ?? 0) > 0 ? (
          <span className={cn(
            'text-xs font-mono font-semibold w-8 text-right',
            scoreToColor(item.score ?? 0)
          )}>
            {item.score}
          </span>
        ) : (
          <span className="w-8" />
        )}

        {selected
          ? <ChevronDown  className="h-4 w-4 text-muted-foreground shrink-0" />
          : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        }
      </div>
    </motion.div>
  )
}
