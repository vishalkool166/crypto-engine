import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  label:      string
  text:       string
  bg?:        string
  border?:    string
  dot?:       boolean
  dotClass?:  string
  className?: string
}

export default function StatusBadge({
  label,
  text,
  bg        = 'bg-muted',
  border    = 'border-border',
  dot       = false,
  dotClass,
  className,
}: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded border px-2 py-0.5',
        'text-xs font-medium',
        text,
        bg,
        border,
        className
      )}
    >
      {dot && (
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full shrink-0',
            dotClass ?? 'bg-current'
          )}
        />
      )}
      {label}
    </span>
  )
}