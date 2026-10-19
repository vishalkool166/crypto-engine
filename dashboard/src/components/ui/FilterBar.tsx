import { useRef } from 'react'
import { Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface FilterOption {
  label: string
  value: string
}

interface FilterBarProps {
  filters?:       FilterOption[]
  active?:        string
  onFilter?:      (value: string) => void
  search?:        string
  onSearch?:      (value: string) => void
  placeholder?:   string
  searchWidth?:   string
  className?:     string
  right?:         React.ReactNode
}

export default function FilterBar({
  filters,
  active,
  onFilter,
  search,
  onSearch,
  placeholder  = 'Search...',
  searchWidth  = 'w-36',
  className,
  right,
}: FilterBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div className={cn(
      'flex items-center gap-2 flex-wrap',
      className
    )}>
      {filters && filters.length > 0 && onFilter && (
        <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
          {filters.map(f => (
            <button
              key       = {f.value}
              onClick   = {() => onFilter(f.value)}
              className = {cn(
                'px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap',
                active === f.value
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground bg-background'
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {onSearch !== undefined && (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground pointer-events-none" />
          <input
            ref         = {inputRef}
            value       = {search ?? ''}
            onChange    = {e => onSearch(e.target.value)}
            placeholder = {placeholder}
            className   = {cn(
              'h-8 rounded-md border border-border bg-background',
              'pl-8 pr-7 text-xs text-foreground',
              'placeholder:text-muted-foreground',
              'outline-none focus:border-foreground/40 transition-colors',
              searchWidth
            )}
          />
          {search && (
            <button
              onClick   = {() => { onSearch(''); inputRef.current?.focus() }}
              className = "absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      )}

      {right && (
        <div className="ml-auto">
          {right}
        </div>
      )}
    </div>
  )
}