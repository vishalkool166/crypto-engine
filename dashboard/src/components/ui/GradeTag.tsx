import { cn } from '@/lib/utils'
import { getGradeConfig } from '@/lib/tokens'

interface GradeTagProps {
  grade:      string | null | undefined
  size?:      'sm' | 'md' | 'lg'
  className?: string
}

const sizes = {
  sm: 'text-[10px] px-1.5 py-px',
  md: 'text-xs px-2 py-0.5',
  lg: 'text-sm px-2.5 py-1',
}

export default function GradeTag({
  grade,
  size      = 'md',
  className,
}: GradeTagProps) {
  const g   = grade ?? '--'
  const cfg = getGradeConfig(g)

  return (
    <span
      className={cn(
        'inline-flex items-center justify-center rounded border font-mono font-semibold tracking-wide',
        cfg.text,
        cfg.bg,
        cfg.border,
        sizes[size],
        className
      )}
    >
      {cfg.label}
    </span>
  )
}