import { useState } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Column<T> {
  key:              string
  header:           string
  cell:             (row: T) => React.ReactNode
  sortable?:        boolean
  className?:       string
  headerClassName?: string
  align?:           'left' | 'right' | 'center'
}

interface DataTableProps<T> {
  columns:       Column<T>[]
  data:          T[]
  keyExtractor:  (row: T) => string | number
  onRowClick?:   (row: T) => void
  loading?:      boolean
  emptyState?:   React.ReactNode
  className?:    string
  stickyHeader?: boolean
  compact?:      boolean
}

type SortDir = 'asc' | 'desc' | null

export default function DataTable<T>({
  columns,
  data,
  keyExtractor,
  onRowClick,
  loading      = false,
  emptyState,
  className,
  stickyHeader = false,
  compact      = false,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>(null)

  const handleSort = (key: string) => {
    if (sortKey !== key) { setSortKey(key); setSortDir('asc'); return }
    if (sortDir === 'asc') { setSortDir('desc'); return }
    setSortKey(null); setSortDir(null)
  }

  const cellPad = compact ? 'px-4 py-2.5' : 'px-4 py-3'

  return (
    <div className={cn('w-full overflow-auto', className)}>
      <table className="w-full text-sm">
        <thead
          className={cn(
            'border-b border-border',
            stickyHeader && 'sticky top-0 bg-card z-10'
          )}
        >
          <tr>
            {columns.map((col) => (
              <th
                key       = {col.key}
                onClick   = {() => col.sortable && handleSort(col.key)}
                className = {cn(
                  cellPad,
                  'label-xs',
                  col.align === 'right'  && 'text-right',
                  col.align === 'center' && 'text-center',
                  col.align !== 'right' && col.align !== 'center' && 'text-left',
                  col.sortable && 'cursor-pointer select-none hover:text-foreground transition-colors',
                  col.headerClassName
                )}
              >
                <div className={cn(
                  'flex items-center gap-1',
                  col.align === 'right'  && 'justify-end',
                  col.align === 'center' && 'justify-center',
                )}>
                  {col.header}
                  {col.sortable && (
                    sortKey === col.key
                      ? sortDir === 'asc'
                        ? <ChevronUp   className="h-3 w-3 text-foreground" />
                        : <ChevronDown className="h-3 w-3 text-foreground" />
                      : <ChevronsUpDown className="h-3 w-3 text-muted-foreground/40" />
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>

        <tbody className="divide-y divide-border">
          {loading ? (
            Array.from({ length: 8 }).map((_, i) => (
              <tr key={i} className="border-b border-border">
                {columns.map((col) => (
                  <td key={col.key} className={cellPad}>
                    <div className="h-4 w-full max-w-[120px] rounded shimmer" />
                  </td>
                ))}
              </tr>
            ))
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={columns.length}>
                {emptyState ?? (
                  <div className="flex items-center justify-center py-12">
                    <p className="text-sm text-muted-foreground">
                      No data available
                    </p>
                  </div>
                )}
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key       = {keyExtractor(row)}
                onClick   = {() => onRowClick?.(row)}
                className = {cn(
                  'transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-muted/40'
                )}
              >
                {columns.map((col) => (
                  <td
                    key       = {col.key}
                    className = {cn(
                      cellPad,
                      col.align === 'right'  && 'text-right',
                      col.align === 'center' && 'text-center',
                      col.className
                    )}
                  >
                    {col.cell(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}