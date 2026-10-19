import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?:        LucideIcon
  title:        string
  description?: string
  action?:      React.ReactNode
  className?:   string
  compact?:     boolean
}

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'py-8 px-4' : 'py-16 px-6',
        className
      )}
    >
      {Icon && (
        <div
          className={cn(
            'flex items-center justify-center rounded-lg border border-border bg-muted mb-4',
            compact ? 'h-9 w-9' : 'h-12 w-12'
          )}
        >
          <Icon
            className={cn(
              'text-muted-foreground',
              compact ? 'h-4 w-4' : 'h-5 w-5'
            )}
          />
        </div>
      )}

      <p
        className={cn(
          'font-medium text-foreground',
          compact ? 'text-sm' : 'text-sm'
        )}
      >
        {title}
      </p>

      {description && (
        <p
          className={cn(
            'text-muted-foreground mt-1 max-w-xs',
            compact ? 'text-xs' : 'text-sm'
          )}
        >
          {description}
        </p>
      )}

      {action && (
        <div className="mt-4">
          {action}
        </div>
      )}
    </div>
  )
}