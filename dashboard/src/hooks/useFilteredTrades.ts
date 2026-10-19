import { useState, useMemo } from 'react'
import type { Trade } from '@/types'

export interface TradeFilters {
  outcome: string
  grade:   string
  coin:    string
}

const DEFAULT_FILTERS: TradeFilters = {
  outcome: 'all',
  grade:   'all',
  coin:    '',
}

const PAGE_SIZE = 20

export function useFilteredTrades(trades: Trade[]) {
  const [filters, setFilters] = useState<TradeFilters>(DEFAULT_FILTERS)
  const [page,    setPage]    = useState(0)

  const closedOnly = useMemo(() =>
    trades.filter(t =>
      ['win', 'loss', 'timeout', 'cancelled', 'expired'].includes(t.outcome)
    ),
    [trades]
  )

  const filtered = useMemo(() => {
    return closedOnly.filter(t => {
      if (filters.outcome !== 'all' && t.outcome !== filters.outcome) return false
      if (filters.grade   !== 'all' && t.grade   !== filters.grade)   return false
      if (filters.coin    && !t.coin.toLowerCase().includes(filters.coin.toLowerCase())) return false
      return true
    })
  }, [closedOnly, filters])

  const paginated = useMemo(() =>
    filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [filtered, page]
  )

  const setFilter = <K extends keyof TradeFilters>(
    key:   K,
    value: TradeFilters[K]
  ) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(0)
  }

  const reset = () => {
    setFilters(DEFAULT_FILTERS)
    setPage(0)
  }

  return {
    filters,
    setFilter,
    reset,
    page,
    setPage,
    filtered,
    paginated,
    total:    filtered.length,
    pageSize: PAGE_SIZE,
  }
}