import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PaginationProps {
  page:       number
  total:      number
  pageSize:   number
  onChange:   (page: number) => void
  className?: string
}

export default function Pagination({
  page,
  total,
  pageSize,
  onChange,
  className,
}: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize)
  const from       = Math.min(page * pageSize + 1, total)
  const to         = Math.min((page + 1) * pageSize, total)

  if (total <= pageSize || pageSize < 1) return null

  return (
    <div className={cn(
      'flex items-center justify-between border-t border-border px-6 py-3',
      className
    )}>
      <p className="text-xs text-muted-foreground">
        {from}–{to} of {total}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick   = {() => onChange(page - 1)}
          disabled  = {page <= 0}
          aria-label = "Previous page"
          className = "flex h-7 w-7 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        <div className="flex items-center gap-1">
          {Array.from({ length: Math.min(totalPages, 5) }).map((_, i) => {
            let pageNum = i
            if (totalPages > 5) {
              if (page <= 2) {
                pageNum = i
              } else if (page >= totalPages - 3) {
                pageNum = totalPages - 5 + i
              } else {
                pageNum = page - 2 + i
              }
            }
            return (
              <button
                key       = {pageNum}
                onClick   = {() => onChange(pageNum)}
                aria-label = {`Page ${pageNum + 1}`}
                aria-current = {pageNum === page ? 'page' : undefined}
                className = {cn(
                  'flex h-7 w-7 items-center justify-center rounded-md text-xs font-medium transition-colors',
                  pageNum === page
                    ? 'bg-foreground text-background'
                    : 'border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-accent'
                )}
              >
                {pageNum + 1}
              </button>
            )
          })}
        </div>
        <button
          onClick   = {() => onChange(page + 1)}
          disabled  = {page >= totalPages - 1}
          aria-label = "Next page"
          className = "flex h-7 w-7 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}