import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, X, ChevronRight, UserCheck, UserX, Monitor, Smartphone, Clock, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  formatTimeAgo, formatDateTime, truncate,
} from '@/lib/utils'
import {
  useUsers, useUserDetail, useUpdateTier,
  useDeactivateUser, useReactivateUser,
  useRevokeSession, useRevokeAllSessions,
} from '@/hooks/useAdmin'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/lib/endpoints'
import EmptyState from '@/components/ui/EmptyState'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import { getTierConfig } from '@/lib/tokens'
import { Users } from 'lucide-react'
import type { AdminUser, Tier, UserSession } from '@/types'

const TIERS: Tier[] = ['free', 'pro', 'elite', 'admin']

const TIER_OPTIONS = [
  { value: 'all',   label: 'All'   },
  { value: 'free',  label: 'Basic' },
  { value: 'pro',   label: 'Pro'   },
  { value: 'elite', label: 'Elite' },
  { value: 'admin', label: 'Admin' },
  { value: 'guest', label: 'Guest' },
]

const LIMIT = 20

interface DemoVisit {
  id:            number
  visited_at:    string | null
  device:        string | null
  browser:       string | null
  tier_explored: string | null
  cta_clicked:   boolean
  duration_secs: number | null
  referrer:      string | null
}

interface DemoStats {
  total:             number
  last_24h:          number
  last_7d:           number
  last_30d:          number
  cta_clicks:        number
  conversion_rate:   number
  mobile_count:      number
  desktop_count:     number
  avg_duration_secs: number
  tier_breakdown:    Record<string, number>
  recent:            DemoVisit[]
}

function useDemoStats() {
  return useQuery({
    queryKey:        ['demo-stats'],
    queryFn:         () => adminApi.pricing().then(() => {
      return fetch('/api/admin/demo/stats', { credentials: 'include' })
        .then(r => r.json()) as Promise<DemoStats>
    }),
    refetchInterval: 60_000,
    staleTime:       30_000,
  })
}

function useDemoStatsQuery() {
  return useQuery<DemoStats>({
    queryKey:        ['demo-stats'],
    queryFn:         async () => {
      const res = await fetch('/api/admin/demo/stats', { credentials: 'include' })
      if (!res.ok) throw new Error('Failed to fetch demo stats')
      return res.json()
    },
    refetchInterval: 60_000,
    staleTime:       30_000,
  })
}

export default function UsersPage() {
  const [search,       setSearch]       = useState('')
  const [tierFilter,   setTierFilter]   = useState('all')
  const [page,         setPage]         = useState(0)
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null)

  const isGuestTab = tierFilter === 'guest'

  const { data, isLoading }  = useUsers({
    limit:  LIMIT,
    offset: page * LIMIT,
    tier:   isGuestTab ? undefined : tierFilter,
  })
  const { data: userDetail } = useUserDetail(selectedUser?.id ?? null)
  const { data: demoStats, isLoading: demoLoading } = useDemoStatsQuery()

  const updateTier    = useUpdateTier()
  const deactivate    = useDeactivateUser()
  const reactivate    = useReactivateUser()
  const revokeSession = useRevokeSession()
  const revokeAll     = useRevokeAllSessions()

  if (isLoading && !isGuestTab) return <PageSkeleton />

  const users: AdminUser[] = data?.users ?? []
  const total              = data?.total ?? 0

  const filtered = users.filter(u =>
    search
      ? u.email.toLowerCase().includes(search.toLowerCase()) ||
        (u.name ?? '').toLowerCase().includes(search.toLowerCase())
      : true
  )

  return (
    <div className="flex h-full">
      <div className={cn(
        'flex flex-1 flex-col overflow-hidden transition-all duration-300',
        selectedUser ? 'lg:mr-96' : ''
      )}>
        <div className="p-4 md:p-6 space-y-4 overflow-y-auto h-full">

          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-base font-semibold text-foreground">Users</h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                {isGuestTab
                  ? `${demoStats?.total ?? 0} demo visitors`
                  : `${total} total`
                }
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {!isGuestTab && (
              <div className="relative flex-1 max-w-xs">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  value       = {search}
                  onChange    = {e => setSearch(e.target.value)}
                  placeholder = "Search by email or name..."
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
            )}
            <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
              {TIER_OPTIONS.map(opt => (
                <button
                  key       = {opt.value}
                  onClick   = {() => { setTierFilter(opt.value); setPage(0); setSelectedUser(null) }}
                  className = {cn(
                    'px-3 py-1.5 text-xs font-medium transition-colors',
                    tierFilter === opt.value
                      ? 'bg-foreground text-background'
                      : 'text-muted-foreground hover:text-foreground bg-background'
                  )}
                >
                  {opt.label}
                  {opt.value === 'guest' && demoStats?.total ? (
                    <span className="ml-1.5 inline-flex items-center justify-center rounded-full bg-muted-foreground/20 text-[10px] px-1.5 py-px">
                      {demoStats.total}
                    </span>
                  ) : null}
                </button>
              ))}
            </div>
          </div>

          {isGuestTab ? (
            <GuestTab
              stats     = {demoStats ?? null}
              isLoading = {demoLoading}
            />
          ) : (
            <>
              <div className="rounded-lg border border-border bg-card overflow-hidden">
                <table className="w-full">
                  <thead className="border-b border-border">
                    <tr>
                      {['User', 'Tier', 'Status', 'Subscription', 'Last Seen', ''].map(h => (
                        <th key={h} className="table-header-cell">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filtered.length === 0 ? (
                      <tr>
                        <td colSpan={6}>
                          <EmptyState
                            icon        = {Users}
                            title       = "No users found"
                            description = "Try adjusting filters"
                            compact
                          />
                        </td>
                      </tr>
                    ) : (
                      filtered.map((user, i) => {
                        const tierCfg = getTierConfig(user.tier)
                        const sub     = (user as AdminUser & {
                          subscription?: {
                            status:               string
                            cancel_at_period_end: boolean
                            current_period_end:   string | null
                          }
                        }).subscription

                        return (
                          <motion.tr
                            key        = {user.id}
                            initial    = {{ opacity: 0 }}
                            animate    = {{ opacity: 1 }}
                            transition = {{ delay: i * 0.02 }}
                            onClick    = {() => setSelectedUser(
                              selectedUser?.id === user.id ? null : user
                            )}
                            className  = {cn(
                              'table-row cursor-pointer',
                              selectedUser?.id === user.id && 'bg-muted/20'
                            )}
                          >
                            <td className="table-cell">
                              <div className="flex items-center gap-3">
                                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground">
                                  {user.email.charAt(0).toUpperCase()}
                                </div>
                                <div className="min-w-0">
                                  <p className="text-sm font-medium text-foreground truncate max-w-[160px]">
                                    {user.name ?? truncate(user.email, 22)}
                                  </p>
                                  <p className="text-xs text-muted-foreground truncate max-w-[160px]">
                                    {user.email}
                                  </p>
                                </div>
                              </div>
                            </td>
                            <td className="table-cell">
                              <span className={cn('text-xs font-medium', tierCfg.text)}>
                                {tierCfg.label}
                              </span>
                            </td>
                            <td className="table-cell">
                              <div className="flex items-center gap-1.5">
                                <span className={cn(
                                  'h-1.5 w-1.5 rounded-full',
                                  user.is_active
                                    ? 'bg-[hsl(var(--chart-1))]'
                                    : 'bg-muted-foreground'
                                )} />
                                <span className={cn(
                                  'text-xs',
                                  user.is_active
                                    ? 'text-[hsl(var(--chart-1))]'
                                    : 'text-muted-foreground'
                                )}>
                                  {user.is_active ? 'Active' : 'Inactive'}
                                </span>
                              </div>
                            </td>
                            <td className="table-cell">
                              {sub ? (
                                <div>
                                  <span className={cn(
                                    'text-xs font-medium capitalize',
                                    sub.status === 'active'
                                      ? 'text-[hsl(var(--chart-1))]'
                                      : 'text-muted-foreground'
                                  )}>
                                    {sub.status}
                                  </span>
                                  {sub.cancel_at_period_end && (
                                    <p className="text-xs text-[hsl(var(--chart-4))] mt-0.5">
                                      Cancels {formatTimeAgo(sub.current_period_end)}
                                    </p>
                                  )}
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground">—</span>
                              )}
                            </td>
                            <td className="table-cell text-xs text-muted-foreground">
                              {formatTimeAgo(user.last_seen)}
                            </td>
                            <td className="table-cell">
                              <ChevronRight className={cn(
                                'h-4 w-4 text-muted-foreground transition-transform',
                                selectedUser?.id === user.id && 'rotate-90'
                              )} />
                            </td>
                          </motion.tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {total > LIMIT && (
                <div className="flex items-center justify-between">
                  <p className="text-xs text-muted-foreground">
                    Showing {page * LIMIT + 1}–{Math.min((page + 1) * LIMIT, total)} of {total}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick   = {() => setPage(p => Math.max(0, p - 1))}
                      disabled  = {page === 0}
                      className = "rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <button
                      onClick   = {() => setPage(p => p + 1)}
                      disabled  = {(page + 1) * LIMIT >= total}
                      className = "rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

        </div>
      </div>

      <AnimatePresence>
        {selectedUser && !isGuestTab && (
          <motion.div
            initial    = {{ x: '100%', opacity: 0 }}
            animate    = {{ x: 0, opacity: 1 }}
            exit       = {{ x: '100%', opacity: 0 }}
            transition = {{ duration: 0.25, ease: 'easeInOut' }}
            className  = "fixed right-0 top-0 h-full w-96 border-l border-border bg-card overflow-y-auto z-40"
          >
            <UserPanel
              user            = {selectedUser}
              detail          = {userDetail ?? null}
              onClose         = {() => setSelectedUser(null)}
              onUpdateTier    = {tier => updateTier.mutate({ id: selectedUser.id, tier })}
              onDeactivate    = {() => deactivate.mutate(selectedUser.id)}
              onReactivate    = {() => reactivate.mutate(selectedUser.id)}
              onRevokeSession = {sid => revokeSession.mutate(sid)}
              onRevokeAll     = {() => revokeAll.mutate(selectedUser.id)}
              updating        = {updateTier.isPending}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function GuestTab({
  stats,
  isLoading,
}: {
  stats:     DemoStats | null
  isLoading: boolean
}) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-lg border border-border bg-card p-5">
              <div className="h-3 w-20 rounded shimmer mb-3" />
              <div className="h-7 w-16 rounded shimmer" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!stats) {
    return (
      <EmptyState
        icon        = {Users}
        title       = "No demo visits yet"
        description = "Visits appear here when users explore the demo"
        compact
      />
    )
  }

  const tierColors: Record<string, string> = {
    free:  'text-muted-foreground',
    pro:   'text-[hsl(var(--chart-3))]',
    elite: 'text-[hsl(var(--chart-5))]',
  }

  const avgMins = Math.floor(stats.avg_duration_secs / 60)
  const avgSecs = stats.avg_duration_secs % 60

  return (
    <div className="space-y-6">

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label = "Total Visitors"
          value = {String(stats.total)}
          sub   = {`${stats.last_24h} today`}
        />
        <StatCard
          label = "This Week"
          value = {String(stats.last_7d)}
          sub   = {`${stats.last_30d} this month`}
        />
        <StatCard
          label    = "CTA Clicks"
          value    = {String(stats.cta_clicks)}
          sub      = {`${stats.conversion_rate}% conversion`}
          positive = {stats.conversion_rate > 5}
        />
        <StatCard
          label = "Avg Session"
          value = {avgMins > 0 ? `${avgMins}m ${avgSecs}s` : `${avgSecs}s`}
          sub   = {`${stats.mobile_count} mobile · ${stats.desktop_count} desktop`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="border-b border-border px-6 py-4">
            <p className="text-sm font-semibold text-foreground">Tier Exploration</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Which tier visitors explored most
            </p>
          </div>
          <div className="p-6 space-y-3">
            {Object.entries(stats.tier_breakdown).length === 0 ? (
              <p className="text-xs text-muted-foreground">No data yet</p>
            ) : (
              Object.entries(stats.tier_breakdown)
                .sort(([, a], [, b]) => b - a)
                .map(([tier, count]) => {
                  const pct = stats.total > 0
                    ? Math.round((count / stats.total) * 100)
                    : 0
                  return (
                    <div key={tier} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className={cn(
                          'text-xs font-medium capitalize',
                          tierColors[tier] ?? 'text-foreground'
                        )}>
                          {tier === 'free' ? 'Basic' : tier.charAt(0).toUpperCase() + tier.slice(1)}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-foreground">{count}</span>
                          <span className="text-xs text-muted-foreground w-8 text-right">{pct}%</span>
                        </div>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                        <motion.div
                          initial    = {{ width: 0 }}
                          animate    = {{ width: `${pct}%` }}
                          transition = {{ duration: 0.5, ease: 'easeOut' }}
                          className  = {cn(
                            'h-full rounded-full',
                            tier === 'elite' ? 'bg-[hsl(var(--chart-5))]' :
                            tier === 'pro'   ? 'bg-[hsl(var(--chart-3))]' :
                            'bg-muted-foreground/40'
                          )}
                        />
                      </div>
                    </div>
                  )
                })
            )}
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="border-b border-border px-6 py-4">
            <p className="text-sm font-semibold text-foreground">Conversion Funnel</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              From visit to signup intent
            </p>
          </div>
          <div className="p-6 space-y-4">
            <FunnelRow
              label   = "Total Visits"
              value   = {stats.total}
              total   = {stats.total}
              color   = "bg-[hsl(var(--chart-3))]"
            />
            <FunnelRow
              label   = "Explored Pro/Elite"
              value   = {(stats.tier_breakdown['pro'] ?? 0) + (stats.tier_breakdown['elite'] ?? 0)}
              total   = {stats.total}
              color   = "bg-[hsl(var(--chart-3))]"
            />
            <FunnelRow
              label   = "Clicked Get Real Signals"
              value   = {stats.cta_clicks}
              total   = {stats.total}
              color   = "bg-[hsl(var(--chart-1))]"
            />
            <div className="rounded-md border border-border bg-muted/30 p-3 mt-2">
              <p className="text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">
                  {stats.conversion_rate}%
                </span>
                {' '}of visitors clicked the signup CTA
              </p>
            </div>
          </div>
        </div>

      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="border-b border-border px-6 py-4">
          <p className="text-sm font-semibold text-foreground">Recent Visitors</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Last 20 demo sessions
          </p>
        </div>
        {stats.recent.length === 0 ? (
          <EmptyState
            title   = "No visits yet"
            compact
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px]">
              <thead className="border-b border-border">
                <tr>
                  {['Time', 'Device', 'Browser', 'Tier Explored', 'Duration', 'CTA'].map(h => (
                    <th key={h} className="table-header-cell">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {stats.recent.map((visit, i) => {
                  const mins = visit.duration_secs
                    ? Math.floor(visit.duration_secs / 60)
                    : null
                  const secs = visit.duration_secs
                    ? visit.duration_secs % 60
                    : null
                  const tier = visit.tier_explored ?? 'free'

                  return (
                    <motion.tr
                      key        = {visit.id}
                      initial    = {{ opacity: 0 }}
                      animate    = {{ opacity: 1 }}
                      transition = {{ delay: i * 0.02 }}
                      className  = "table-row"
                    >
                      <td className="table-cell text-xs text-muted-foreground">
                        {formatTimeAgo(visit.visited_at)}
                      </td>
                      <td className="table-cell">
                        <div className="flex items-center gap-1.5">
                          {visit.device === 'mobile'
                            ? <Smartphone className="h-3.5 w-3.5 text-muted-foreground" />
                            : <Monitor    className="h-3.5 w-3.5 text-muted-foreground" />
                          }
                          <span className="text-xs text-muted-foreground capitalize">
                            {visit.device ?? '—'}
                          </span>
                        </div>
                      </td>
                      <td className="table-cell text-xs text-muted-foreground capitalize">
                        {visit.browser ?? '—'}
                      </td>
                      <td className="table-cell">
                        <span className={cn(
                          'text-xs font-medium capitalize',
                          tierColors[tier] ?? 'text-foreground'
                        )}>
                          {tier === 'free' ? 'Basic' : tier.charAt(0).toUpperCase() + tier.slice(1)}
                        </span>
                      </td>
                      <td className="table-cell text-xs font-mono text-muted-foreground">
                        {mins !== null && secs !== null
                          ? mins > 0 ? `${mins}m ${secs}s` : `${secs}s`
                          : '—'
                        }
                      </td>
                      <td className="table-cell">
                        {visit.cta_clicked ? (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-[hsl(var(--chart-1))]">
                            <TrendingUp className="h-3 w-3" />
                            Yes
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                    </motion.tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  )
}

function StatCard({
  label,
  value,
  sub,
  positive,
}: {
  label:     string
  value:     string
  sub?:      string
  positive?: boolean
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <p className="label-xs">{label}</p>
      <p className="value-md text-foreground mt-2">{value}</p>
      {sub && (
        <p className={cn(
          'text-xs mt-1',
          positive === true  && 'text-[hsl(var(--chart-1))]',
          positive === false && 'text-[hsl(var(--chart-2))]',
          positive === undefined && 'text-muted-foreground',
        )}>
          {sub}
        </p>
      )}
    </div>
  )
}

function FunnelRow({
  label,
  value,
  total,
  color,
}: {
  label: string
  value: number
  total: number
  color: string
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-semibold text-foreground">{value}</span>
          <span className="text-xs text-muted-foreground w-8 text-right">{pct}%</span>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <motion.div
          initial    = {{ width: 0 }}
          animate    = {{ width: `${pct}%` }}
          transition = {{ duration: 0.5, ease: 'easeOut' }}
          className  = {cn('h-full rounded-full', color)}
        />
      </div>
    </div>
  )
}

function UserPanel({
  user,
  detail,
  onClose,
  onUpdateTier,
  onDeactivate,
  onReactivate,
  onRevokeSession,
  onRevokeAll,
  updating,
}: {
  user:            AdminUser
  detail:          { user: AdminUser; sessions: UserSession[] } | null
  onClose:         () => void
  onUpdateTier:    (tier: string) => void
  onDeactivate:    () => void
  onReactivate:    () => void
  onRevokeSession: (sid: string) => void
  onRevokeAll:     () => void
  updating:        boolean
}) {
  const sessions    = detail?.sessions ?? []
  const currentUser = detail?.user ?? user
  const tierCfg     = getTierConfig(currentUser.tier)

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-border px-5 py-4 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-xs font-semibold text-foreground">
            {user.email.charAt(0).toUpperCase()}
          </div>
          <span className="text-sm font-semibold text-foreground truncate max-w-[200px]">
            {user.name ?? user.email}
          </span>
        </div>
        <button
          onClick   = {onClose}
          className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-5">

        <PanelSection title="Profile">
          <PanelRow label="Email"      value={currentUser.email}                        mono />
          <PanelRow label="Provider"   value={currentUser.provider}                          />
          <PanelRow label="Onboarded"  value={currentUser.onboarded ? 'Yes' : 'No'}         />
          <PanelRow label="Joined"     value={formatDateTime(currentUser.created_at)}        />
          <PanelRow label="Last Login" value={formatTimeAgo(currentUser.last_login)}         />
          <PanelRow label="Last Seen"  value={formatTimeAgo(currentUser.last_seen)}          />
          <PanelRow
            label = "Status"
            value = {
              <div className="flex items-center gap-1.5">
                <span className={cn(
                  'h-1.5 w-1.5 rounded-full',
                  currentUser.is_active
                    ? 'bg-[hsl(var(--chart-1))]'
                    : 'bg-muted-foreground'
                )} />
                <span className={cn(
                  'text-xs font-medium',
                  currentUser.is_active
                    ? 'text-[hsl(var(--chart-1))]'
                    : 'text-muted-foreground'
                )}>
                  {currentUser.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
            }
          />
          {currentUser.is_admin && (
            <PanelRow
              label = "Role"
              value = {
                <span className="text-xs font-medium text-[hsl(var(--chart-1))]">
                  Admin
                </span>
              }
            />
          )}
        </PanelSection>

        <PanelSection title="Tier Management">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-muted-foreground">Current</span>
            <span className={cn('text-xs font-semibold', tierCfg.text)}>
              {tierCfg.label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {TIERS.map(t => {
              const tc = getTierConfig(t)
              return (
                <button
                  key       = {t}
                  onClick   = {() => onUpdateTier(t)}
                  disabled  = {updating || currentUser.tier === t}
                  className = {cn(
                    'rounded-md border px-2.5 py-2 text-xs font-medium transition-colors',
                    'disabled:opacity-50 disabled:cursor-not-allowed',
                    currentUser.tier === t
                      ? `${tc.bg} ${tc.text} border-current/20`
                      : 'border-border bg-background text-foreground hover:bg-accent'
                  )}
                >
                  {tc.label}
                </button>
              )
            })}
          </div>
        </PanelSection>

        <PanelSection title={`Sessions (${sessions.length})`}>
          {sessions.length === 0 ? (
            <p className="text-xs text-muted-foreground">No active sessions</p>
          ) : (
            <div className="space-y-2">
              {sessions.map(s => (
                <div
                  key       = {s.id}
                  className = "flex items-center justify-between rounded-md bg-muted/50 px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-foreground">
                      {s.device ?? 'Unknown'} · {s.browser ?? 'Unknown'}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {s.ip ?? '—'} · {formatTimeAgo(s.last_active)}
                    </p>
                  </div>
                  <button
                    onClick   = {() => onRevokeSession(s.session_id)}
                    className = "ml-3 shrink-0 text-xs text-[hsl(var(--chart-2))] hover:text-[hsl(var(--chart-2)/0.8)] transition-colors"
                  >
                    Revoke
                  </button>
                </div>
              ))}
              {sessions.length > 1 && (
                <button
                  onClick   = {onRevokeAll}
                  className = "w-full rounded-md border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-3 py-2 text-xs font-medium text-[hsl(var(--chart-2))] hover:bg-[hsl(var(--chart-2)/0.12)] transition-colors"
                >
                  Revoke All Sessions
                </button>
              )}
            </div>
          )}
        </PanelSection>

        <PanelSection title="Account Control">
          {currentUser.is_active ? (
            <button
              onClick   = {onDeactivate}
              className = "flex w-full items-center justify-center gap-2 rounded-md border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-3 py-2.5 text-xs font-medium text-[hsl(var(--chart-2))] hover:bg-[hsl(var(--chart-2)/0.12)] transition-colors"
            >
              <UserX className="h-3.5 w-3.5" />
              Deactivate Account
            </button>
          ) : (
            <button
              onClick   = {onReactivate}
              className = "flex w-full items-center justify-center gap-2 rounded-md border border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.06)] px-3 py-2.5 text-xs font-medium text-[hsl(var(--chart-1))] hover:bg-[hsl(var(--chart-1)/0.12)] transition-colors"
            >
              <UserCheck className="h-3.5 w-3.5" />
              Reactivate Account
            </button>
          )}
        </PanelSection>

      </div>
    </div>
  )
}

function PanelSection({
  title,
  children,
}: {
  title:    string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-4 space-y-2">
      <p className="label-xs mb-3">{title}</p>
      {children}
    </div>
  )
}

function PanelRow({
  label,
  value,
  mono = false,
}: {
  label:  string
  value:  React.ReactNode
  mono?:  boolean
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-0.5">
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      {typeof value === 'string' ? (
        <span className={cn(
          'text-xs text-foreground text-right truncate',
          mono && 'font-mono'
        )}>
          {value}
        </span>
      ) : value}
    </div>
  )
}