import { useEffect, useState } from 'react'
import Pagination from '@/components/ui/Pagination'
import { motion } from 'framer-motion'
import { Search, X, RefreshCw, Download } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDateTime, formatTimeAgo } from '@/lib/utils'
import { useAuditLog } from '@/hooks/useAdmin'
import { useDemoStore } from '@/demo/demoStore'
import EmptyState from '@/components/ui/EmptyState'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import { ScrollText } from 'lucide-react'
import type { AuditEntry } from '@/types'

const ACTION_COLORS: Record<string, { text: string; bg: string }> = {
  dashboard_login:          { text: 'text-[hsl(var(--chart-3))]', bg: 'bg-[hsl(var(--chart-3)/0.08)]' },
  oauth_login:              { text: 'text-[hsl(var(--chart-3))]', bg: 'bg-[hsl(var(--chart-3)/0.08)]' },
  mode_toggle:              { text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]' },
  docker_purge:             { text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]' },
  coin_add:                 { text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]' },
  coin_delete:              { text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]' },
  coin_toggle:              { text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]' },
  admin_tier_update:        { text: 'text-[hsl(var(--chart-5))]', bg: 'bg-[hsl(var(--chart-5)/0.08)]' },
  admin_deactivate_user:    { text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]' },
  admin_reactivate_user:    { text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]' },
  password_reset:           { text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]' },
  recovery_codes_generated: { text: 'text-[hsl(var(--chart-5))]', bg: 'bg-[hsl(var(--chart-5)/0.08)]' },
}

const ACTION_GROUPS = [
  { label: 'All',     value: 'all'     },
  { label: 'Auth',    value: 'auth'    },
  { label: 'Trading', value: 'trading' },
  { label: 'Admin',   value: 'admin'   },
  { label: 'System',  value: 'system'  },
]

const ACTION_GROUP_MAP: Record<string, string[]> = {
  auth:    ['dashboard_login', 'oauth_login', 'password_reset', 'recovery_codes_generated'],
  trading: ['mode_toggle'],
  admin:   ['admin_tier_update', 'admin_deactivate_user', 'admin_reactivate_user', 'admin_revoke_session', 'admin_revoke_all_sessions'],
  system:  ['docker_purge', 'coin_add', 'coin_delete', 'coin_toggle'],
}

const LIMIT = 50

const MOCK_AUDIT: AuditEntry[] = [
  { id: 1, timestamp: new Date(Date.now() - 2  * 60000).toISOString(),  action: 'oauth_login',       source: 'google',    detail: 'user:demo@example.com tier:pro new:false',  ip: '192.168.1.1',  success: true  },
  { id: 2, timestamp: new Date(Date.now() - 15 * 60000).toISOString(),  action: 'admin_tier_update', source: 'admin',     detail: 'user:42 tier:free→pro',                     ip: '10.0.0.1',     success: true  },
  { id: 3, timestamp: new Date(Date.now() - 32 * 60000).toISOString(),  action: 'coin_add',          source: 'api',       detail: 'BTC added',                                 ip: '10.0.0.1',     success: true  },
  { id: 4, timestamp: new Date(Date.now() - 48 * 60000).toISOString(),  action: 'mode_toggle',       source: 'dashboard', detail: 'mode:paper',                                ip: '10.0.0.1',     success: true  },
  { id: 5, timestamp: new Date(Date.now() - 62 * 60000).toISOString(),  action: 'oauth_login',       source: 'google',    detail: 'user:user2@example.com tier:free new:true',  ip: '172.16.0.5',   success: true  },
  { id: 6, timestamp: new Date(Date.now() - 90 * 60000).toISOString(),  action: 'coin_toggle',       source: 'api',       detail: 'ETH enabled:false',                         ip: '10.0.0.1',     success: true  },
  { id: 7, timestamp: new Date(Date.now() - 120 * 60000).toISOString(), action: 'docker_purge',      source: 'dashboard', detail: 'freed:142MB',                               ip: '10.0.0.1',     success: true  },
  { id: 8, timestamp: new Date(Date.now() - 180 * 60000).toISOString(), action: 'oauth_login',       source: 'google',    detail: 'user:user3@example.com tier:elite new:false',ip: '203.0.113.42', success: false },
]

function exportCsv(logs: AuditEntry[]) {
  const headers = ['ID', 'Timestamp', 'Action', 'Source', 'Detail', 'IP', 'Success']
  const rows    = logs.map(l => [
    l.id,
    l.timestamp ?? '',
    l.action,
    l.source,
    (l.detail ?? '').replace(/,/g, ';'),
    l.ip ?? '',
    l.success ? 'true' : 'false',
  ])
  // CSV injection defence: audit details may contain arbitrary external strings.
  const escapeCsv = (v: string | number | boolean) => {
    const raw = String(v)
    const safe = /^[=+@\-\t\r]/.test(raw.trimStart()) ? `'${raw}` : raw
    return `"${safe.replace(/"/g, '""')}"`
  }
  const csv     = [headers, ...rows].map(r => r.map(escapeCsv).join(',')).join('\n')
  const blob    = new Blob([csv], { type: 'text/csv' })
  const url     = URL.createObjectURL(blob)
  const a       = document.createElement('a')
  a.href        = url
  a.download    = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function Audit() {
  const { isDemoMode }                             = useDemoStore()
  const [search,       setSearch]                  = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300)
    return () => window.clearTimeout(timer)
  }, [search])
  const [statusFilter, setStatusFilter]            = useState<'all' | 'success' | 'failed'>('all')
  const [actionGroup,  setActionGroup]             = useState('all')
  const [page,         setPage]                    = useState(0)

  const realAudit = useAuditLog(LIMIT, page * LIMIT, {
    search: debouncedSearch,
    actions: actionGroup === 'all' ? undefined : ACTION_GROUP_MAP[actionGroup]?.join(','),
    success: statusFilter === 'all' ? undefined : statusFilter === 'success',
  })
  const {
    data,
    isLoading,
    refetch,
    isFetching,
  } = isDemoMode
    ? { data: { logs: MOCK_AUDIT, total: MOCK_AUDIT.length }, isLoading: false, refetch: () => {}, isFetching: false }
    : realAudit

  const logs:  AuditEntry[] = data?.logs  ?? []
  const total: number       = data?.total ?? 0

  const filtered = logs.filter(entry => {
    if (!isDemoMode) return true // filters already applied across all rows on the server
    if (statusFilter === 'success' && !entry.success) return false
    if (statusFilter === 'failed'  &&  entry.success) return false
    if (actionGroup !== 'all') {
      const group = ACTION_GROUP_MAP[actionGroup] ?? []
      if (!group.includes(entry.action)) return false
    }
    if (search) {
      const q = search.toLowerCase()
      return (
        entry.action.toLowerCase().includes(q) ||
        (entry.detail ?? '').toLowerCase().includes(q) ||
        (entry.source ?? '').toLowerCase().includes(q) ||
        (entry.ip     ?? '').toLowerCase().includes(q)
      )
    }
    return true
  })

  if (isLoading) return <PageSkeleton />

  return (
    <div className="p-4 md:p-6 space-y-6">

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-foreground">Audit Log</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {isDemoMode ? 'Demo — sample audit events' : `${total} total events · filters cover all matching events`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick   = {() => exportCsv(filtered)}
            disabled  = {filtered.length === 0}
            className = "flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            Export visible page
          </button>
          {!isDemoMode && (
            <button
              onClick   = {() => refetch()}
              disabled  = {isFetching}
              className = "flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin')} />
              Refresh
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value       = {search}
            onChange    = {e => { setSearch(e.target.value); setPage(0) }}
            placeholder = "Search actions, details, IP..."
            className   = "h-9 w-full rounded-md border border-border bg-background pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:border-foreground/40 transition-colors"
          />
          {search && (
            <button
              onClick   = {() => setSearch('')}
              className = "absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
          {ACTION_GROUPS.map(g => (
            <button
              key       = {g.value}
              onClick   = {() => { setActionGroup(g.value); setPage(0) }}
              className = {cn(
                'px-3 py-1.5 text-xs font-medium transition-colors',
                actionGroup === g.value
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground bg-background'
              )}
            >
              {g.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
          {(['all', 'success', 'failed'] as const).map(f => (
            <button
              key       = {f}
              onClick   = {() => { setStatusFilter(f); setPage(0) }}
              className = {cn(
                'px-3 py-1.5 text-xs font-medium capitalize transition-colors',
                statusFilter === f
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground bg-background'
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        {filtered.length === 0 ? (
          <EmptyState
            icon        = {ScrollText}
            title       = "No audit events found"
            description = "Try adjusting your search or filters"
            compact
          />
        ) : (
          <div className="divide-y divide-border">
            {filtered.map((entry, i) => {
              const style = ACTION_COLORS[entry.action] ?? {
                text: 'text-muted-foreground',
                bg:   'bg-muted',
              }

              return (
                <motion.div
                  key        = {entry.id}
                  initial    = {{ opacity: 0 }}
                  animate    = {{ opacity: 1 }}
                  transition = {{ delay: i * 0.01 }}
                  className  = "flex items-start gap-4 px-6 py-4 hover:bg-muted/20 transition-colors"
                >
                  <div className="mt-0.5 shrink-0">
                    <span className={cn(
                      'h-1.5 w-1.5 rounded-full inline-block mt-1.5',
                      entry.success
                        ? 'bg-[hsl(var(--chart-1))]'
                        : 'bg-[hsl(var(--chart-2))]'
                    )} />
                  </div>

                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={cn(
                        'inline-flex items-center rounded border px-1.5 py-px text-xs font-mono font-medium',
                        style.text,
                        style.bg,
                        'border-current/20'
                      )}>
                        {entry.action}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        via {entry.source}
                      </span>
                      {entry.ip && (
                        <span className="text-xs font-mono text-muted-foreground">
                          {entry.ip}
                        </span>
                      )}
                    </div>
                    {entry.detail && (
                      <p className="text-xs text-muted-foreground truncate">
                        {entry.detail}
                      </p>
                    )}
                  </div>

                  <div className="shrink-0 text-right">
                    <p className="text-xs text-muted-foreground">
                      {formatTimeAgo(entry.timestamp)}
                    </p>
                    <p className="text-xs text-muted-foreground/50 mt-0.5">
                      {formatDateTime(entry.timestamp)}
                    </p>
                  </div>
                </motion.div>
              )
            })}
          </div>
        )}
      </div>

      {!isDemoMode && <Pagination page={page} pageSize={LIMIT} total={total} onChange={setPage} />}

    </div>
  )
}