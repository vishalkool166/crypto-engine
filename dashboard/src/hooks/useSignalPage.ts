import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { signalsApi } from '@/lib/endpoints'
import { useDemoStore } from '@/demo/demoStore'
import { mockSignalHistory } from '@/demo/mockData'

const PAGE_SIZE = 25
export function useSignalPage() {
  const { isDemoMode } = useDemoStore()
  const [page, setPage] = useState(0)
  const [filters, setFilters] = useState({ grade: 'all', outcome: 'all', coin: '' })
  const setFilter = (key: 'grade'|'outcome'|'coin', value: string) => {
    setFilters(previous => ({ ...previous, [key]: value }))
    setPage(0)
  }
  const params = {
    limit: PAGE_SIZE, offset: page * PAGE_SIZE,
    grade: filters.grade === 'all' ? undefined : filters.grade,
    outcome: filters.outcome === 'all' ? undefined : filters.outcome,
    coin: filters.coin.trim() || undefined,
  }
  const history = useQuery({
    queryKey: ['signals-history-page', params],
    queryFn: () => signalsApi.page(params).then(r => r.data),
    enabled: !isDemoMode,
    staleTime: 30_000, refetchInterval: !isDemoMode ? 60_000 : false,
  })
  const filteredDemo = mockSignalHistory.filter(s =>
    (filters.grade === 'all' || s.grade === filters.grade) &&
    (filters.outcome === 'all' || s.outcome === filters.outcome) &&
    (!filters.coin || s.coin.toLowerCase().includes(filters.coin.toLowerCase()))
  )
  return {
    filters, setFilter, page, setPage, pageSize: PAGE_SIZE,
    paginated: isDemoMode
      ? filteredDemo.slice(page * PAGE_SIZE, (page+1)*PAGE_SIZE)
      : (history.data?.items ?? []),
    total: isDemoMode ? filteredDemo.length : history.data?.total ?? 0,
    isLoading: !isDemoMode && history.isLoading,
    isError: !isDemoMode && history.isError,
  }
}
