import { useState, useMemo } from 'react'
import type { Signal } from '@/types'

export interface SignalFilters {
  outcome: string
  grade:   string
  coin:    string
}

const DEFAULT_FILTERS: SignalFilters = {
  outcome: 'all',
  grade:   'all',
  coin:    '',
}

const PAGE_SIZE = 20

export function useFilteredSignals(signals: Signal[] | undefined) {
  const [filters, setFilters] = useState<SignalFilters>(DEFAULT_FILTERS)
  const [page,    setPage]    = useState(0)

  const all = useMemo(() => signals ?? [], [signals])

  const filtered = useMemo(() => {
    return all.filter(s => {
      if (filters.outcome !== 'all' && s.outcome !== filters.outcome) return false
      if (filters.grade   !== 'all' && s.grade   !== filters.grade)   return false
      if (filters.coin    && !s.coin.toLowerCase().includes(filters.coin.toLowerCase())) return false
      return true
    })
  }, [all, filters])

  const paginated = useMemo(() =>
    filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [filtered, page]
  )

  const setFilter = <K extends keyof SignalFilters>(
    key:   K,
    value: SignalFilters[K]
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