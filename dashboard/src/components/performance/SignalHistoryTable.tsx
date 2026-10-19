import { motion } from 'framer-motion'
import { BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatCurrency, formatPrice, formatTimeAgo } from '@/lib/utils'
import { pnlColor, getDirectionConfig, getOutcomeConfig } from '@/lib/tokens'
import GradeTag from '@/components/ui/GradeTag'
import EmptyState from '@/components/ui/EmptyState'
import FilterBar from '@/components/ui/FilterBar'
import Pagination from '@/components/ui/Pagination'
import { useSignalPage } from '@/hooks/useSignalPage'
import type { Signal } from '@/types'

const GRADE_FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'A+',  value: 'A+' },
  { label: 'A',   value: 'A'  },
  { label: 'B',   value: 'B'  },
]

const OUTCOME_FILTERS = [
  { label: 'All',     value: 'all'     },
  { label: 'Win',     value: 'win'     },
  { label: 'Loss',    value: 'loss'    },
  { label: 'Pending', value: 'pending' },
]

export default function SignalHistoryTable() {
  const {
    filters, setFilter, page, setPage, paginated, total, pageSize, isLoading, isError,
  } = useSignalPage()

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="border-b border-border px-6 py-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">Signal History</p>
          <p className="text-xs text-muted-foreground mt-0.5">{total} signals</p>
        </div>
        <FilterBar
          filters     = {GRADE_FILTERS}
          active      = {filters.grade}
          onFilter    = {v => setFilter('grade', v)}
          search      = {filters.coin}
          onSearch    = {v => setFilter('coin', v)}
          placeholder = "Filter coin..."
          right       = {
            <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
              {OUTCOME_FILTERS.map(f => (
                <button
                  key       = {f.value}
                  onClick   = {() => setFilter('outcome', f.value)}
                  className = {cn(
                    'px-2.5 py-1.5 text-xs font-medium transition-colors',
                    filters.outcome === f.value
                      ? 'bg-foreground text-background'
                      : 'text-muted-foreground hover:text-foreground bg-background'
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          }
        />
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-foreground" />
        </div>
      ) : isError ? (
        <div className="py-10 text-center text-sm text-destructive" role="alert">Signal history is unavailable. Try again later.</div>
      ) : paginated.length === 0 ? (
        <EmptyState
          icon        = {BarChart3}
          title       = "No signals found"
          description = "Try adjusting filters"
          compact
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px]">
              <thead className="border-b border-border">
                <tr>
                  {['Coin', 'Grade', 'Direction', 'Entry', 'Exit', 'PnL', 'Result', 'Age'].map(h => (
                    <th key={h} className="table-header-cell">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {paginated.map((s: Signal, i: number) => {
                  const dirCfg     = getDirectionConfig(s.direction)
                  const DirIcon    = dirCfg?.icon
                  const outcomeCfg = getOutcomeConfig(s.outcome)
                  const spnl       = s.pnl ?? 0

                  return (
                    <motion.tr
                      key        = {s.id}
                      initial    = {{ opacity: 0 }}
                      animate    = {{ opacity: 1 }}
                      transition = {{ delay: Math.min(i * 0.01, 0.2) }}
                      className  = "table-row"
                    >
                      <td className="table-cell font-mono font-semibold">{s.coin}</td>
                      <td className="table-cell"><GradeTag grade={s.grade} /></td>
                      <td className="table-cell">
                        {dirCfg && DirIcon ? (
                          <span className={cn('inline-flex items-center gap-1 text-xs font-medium', dirCfg.text)}>
                            <DirIcon className="h-3 w-3" />
                            {s.direction}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="table-cell font-mono text-xs">
                        {s.entry ? formatPrice(s.entry) : '—'}
                      </td>
                      <td className="table-cell font-mono text-xs">
                        {s.exit_price ? formatPrice(s.exit_price) : '—'}
                      </td>
                      <td className="table-cell">
                        <span className={cn('font-mono text-xs font-semibold', pnlColor(spnl))}>
                          {s.outcome !== 'pending' ? formatCurrency(spnl) : '—'}
                        </span>
                      </td>
                      <td className="table-cell">
                        <span className={cn(
                          'inline-flex items-center rounded border px-1.5 py-px text-xs font-medium',
                          outcomeCfg.bg, outcomeCfg.text, outcomeCfg.border
                        )}>
                          {outcomeCfg.label}
                        </span>
                      </td>
                      <td className="table-cell text-muted-foreground text-xs">
                        {formatTimeAgo(s.timestamp)}
                      </td>
                    </motion.tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Pagination
            page     = {page}
            total    = {total}
            pageSize = {pageSize}
            onChange = {setPage}
          />
        </>
      )}
    </div>
  )
}