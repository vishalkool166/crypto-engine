import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CollapsibleSectionProps {
  title:        string
  count?:       number
  defaultOpen?: boolean
  className?:   string
  headerClass?: string
  children:     React.ReactNode
  badge?:       React.ReactNode
  action?:      React.ReactNode
}

export default function CollapsibleSection({
  title,
  count,
  defaultOpen = false,
  className,
  headerClass,
  children,
  badge,
  action,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className={cn('rounded-lg border border-border bg-card overflow-hidden', className)}>
      <button
        onClick   = {() => setOpen(o => !o)}
        className = {cn(
          'flex w-full items-center justify-between px-6 py-4',
          'hover:bg-muted/20 transition-colors',
          headerClass
        )}
      >
        <div className="flex items-center gap-2.5">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          {count !== undefined && (
            <span className="inline-flex items-center justify-center rounded-full bg-muted px-2 py-px text-xs font-medium text-muted-foreground min-w-[20px]">
              {count}
            </span>
          )}
          {badge}
        </div>
        <div className="flex items-center gap-3">
          {action && (
            <div onClick={e => e.stopPropagation()}>
              {action}
            </div>
          )}
          <ChevronDown className={cn(
            'h-4 w-4 text-muted-foreground transition-transform duration-200',
            open && 'rotate-180'
          )} />
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial    = {{ height: 0, opacity: 0 }}
            animate    = {{ height: 'auto', opacity: 1 }}
            exit       = {{ height: 0, opacity: 0 }}
            transition = {{ duration: 0.2, ease: 'easeInOut' }}
            className  = "overflow-hidden"
          >
            <div className="border-t border-border">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}