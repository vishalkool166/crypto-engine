import { cn } from '@/lib/utils'

interface InfoRowProps {
  label:      string
  value:      React.ReactNode
  mono?:      boolean
  valueClass?: string
  sub?:       string
  subClass?:  string
  border?:    boolean
}

export default function InfoRow({
  label,
  value,
  mono       = false,
  valueClass,
  sub,
  subClass,
  border     = false,
}: InfoRowProps) {
  return (
    <div className={cn(
      'flex items-start justify-between gap-3 py-1.5',
      border && 'border-t border-border pt-2 mt-1'
    )}>
      <span className="text-xs text-muted-foreground shrink-0 mt-0.5">
        {label}
      </span>
      <div className="text-right min-w-0">
        {typeof value === 'string' || typeof value === 'number' ? (
          <span className={cn(
            'text-xs font-medium text-foreground',
            mono && 'font-mono',
            valueClass
          )}>
            {value}
          </span>
        ) : (
          value
        )}
        {sub && (
          <p className={cn('text-xs text-muted-foreground mt-0.5', subClass)}>
            {sub}
          </p>
        )}
      </div>
    </div>
  )
}