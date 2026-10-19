import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { tradesApi } from '@/lib/endpoints'
import { useDemoStore } from '@/demo/demoStore'
import { mockClosedTrades } from '@/demo/mockData'
import type { Trade } from '@/types'

export type TradeFilterKey = 'grade' | 'outcome' | 'coin'
export const TRADE_PAGE_SIZE = 25

export function useTradePage() {
  const { isDemoMode } = useDemoStore()
  const [page, setPage] = useState(0)
  const [filters, setFilters] = useState({ grade: 'all', outcome: 'all', coin: '' })
  const setFilter = (key: TradeFilterKey, value: string) => {
    setFilters(previous => ({ ...previous, [key]: value }))
    setPage(0)
  }
  const params = { limit: TRADE_PAGE_SIZE, offset: page * TRADE_PAGE_SIZE,
    grade: filters.grade === 'all' ? undefined : filters.grade,
    outcome: filters.outcome === 'all' ? undefined : filters.outcome,
    coin: filters.coin.trim() || undefined,
  }
  const history = useQuery({
    queryKey: ['trades-history-page', params],
    queryFn: () => tradesApi.history(params).then(r => r.data),
    enabled: !isDemoMode,
    staleTime: 30_000,
    refetchInterval: !isDemoMode ? 60_000 : false,
  })
  const demoFiltered = mockClosedTrades.filter(t =>
    (filters.grade === 'all' || t.grade === filters.grade) &&
    (filters.outcome === 'all' || t.outcome === filters.outcome) &&
    (!filters.coin || t.coin.toLowerCase().includes(filters.coin.toLowerCase()))
  )
  const pageData = isDemoMode
    ? demoFiltered.slice(page * TRADE_PAGE_SIZE, (page + 1) * TRADE_PAGE_SIZE)
    : history.data?.trades ?? []
  return {
    filters, setFilter, page, setPage,
    paginated: pageData as Trade[],
    total: isDemoMode ? demoFiltered.length : history.data?.trades_count ?? 0,
    pageSize: TRADE_PAGE_SIZE,
    isHistoryLoading: !isDemoMode && history.isLoading,
    historyError: !isDemoMode && history.isError,
  }
}
