import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { User, Mail, Calendar, Clock, Shield, Crown, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDateTime, formatTimeAgo } from '@/lib/utils'
import { meApi } from '@/lib/endpoints'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import { getTierConfig } from '@/lib/tokens'
import type { Tier } from '@/types'

const TIERS: Tier[] = ['free', 'pro', 'elite']

const TIER_FEATURES: Record<string, Array<{ label: string; value: string; available: boolean }>> = {
  free: [
    { label: 'Signal delay',      value: '30 minutes',  available: false },
    { label: 'Signals per day',   value: '3',            available: true  },
    { label: 'Entry / SL / TP',   value: 'Not included', available: false },
    { label: 'Performance',       value: 'Not included', available: false },
    { label: 'Coins monitored',   value: '5',            available: true  },
  ],
  pro: [
    { label: 'Signal delay',      value: 'Live',         available: true  },
    { label: 'Signals per day',   value: 'Unlimited',    available: true  },
    { label: 'Entry / SL / TP',   value: 'Included',     available: true  },
    { label: 'Performance',       value: 'Full access',  available: true  },
    { label: 'Coins monitored',   value: 'All coins',    available: true  },
  ],
  elite: [
    { label: 'Signal delay',      value: 'Live',         available: true  },
    { label: 'Signals per day',   value: 'Unlimited',    available: true  },
    { label: 'Entry / SL / TP',   value: 'Included',     available: true  },
    { label: 'Confluence factors',value: 'Included',     available: true  },
    { label: 'ML probability',    value: 'Included',     available: true  },
    { label: 'API key access',    value: 'Up to 3 keys', available: true  },
    { label: 'AI assistant',      value: 'Included',     available: true  },
  ],
  admin: [
    { label: 'Signal delay',      value: 'Live',         available: true  },
    { label: 'Full system access',value: 'All features', available: true  },
    { label: 'User management',   value: 'Full control', available: true  },
    { label: 'API key access',    value: 'Unlimited',    available: true  },
    { label: 'AI assistant',      value: 'Included',     available: true  },
  ],
}

export default function Profile() {
  const { user, tier, isAdmin } = useAuthStore()
  const { isDemoMode, demoTier, setDemoTier } = useDemoStore()

  const { data: meData, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn:  () => meApi.get().then(r => r.data),
    enabled:  !isDemoMode,
  })

  if (isLoading && !isDemoMode) return <PageSkeleton />

  const activeTier = isDemoMode ? demoTier : tier
  const tierCfg    = getTierConfig(activeTier)
  const features   = TIER_FEATURES[activeTier] ?? TIER_FEATURES.free

  const displayEmail = isDemoMode
    ? `demo-${demoTier}@signalengine.app`
    : user?.email ?? '—'

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-2xl">

      <div>
        <h1 className="text-base font-semibold text-foreground">Profile</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {isDemoMode ? 'Demo account — switch tiers to explore' : 'Account details and subscription'}
        </p>
      </div>

      <motion.div
        initial    = {{ opacity: 0, y: 6 }}
        animate    = {{ opacity: 1, y: 0 }}
        className  = "rounded-lg border border-border bg-card overflow-hidden"
      >
        <div className="flex items-center gap-2.5 border-b border-border px-6 py-4">
          <User className="h-4 w-4 text-muted-foreground" />
          <p className="text-sm font-semibold text-foreground">Identity</p>
        </div>
        <div className="p-6 space-y-5">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-muted text-lg font-semibold text-foreground">
              {displayEmail.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-base font-semibold text-foreground truncate">
                {isDemoMode ? `Demo — ${tierCfg.label} Tier` : (meData?.name ?? user?.email)}
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={cn('text-xs font-medium', tierCfg.text)}>
                  {tierCfg.label}
                </span>
                {isAdmin && !isDemoMode && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-[hsl(var(--chart-1))]">
                    <Shield className="h-3 w-3" />
                    Admin
                  </span>
                )}
                {isDemoMode && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
                    Demo Mode
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-1">
            <InfoRow icon={Mail}     label="Email"     value={displayEmail}                                          mono />
            <InfoRow icon={Shield}   label="Provider"  value={isDemoMode ? 'Demo' : (meData?.provider ?? 'Google')}      />
            {!isDemoMode && (
              <>
                <InfoRow icon={Calendar} label="Joined"    value={formatDateTime(meData?.created_at)}  />
                <InfoRow icon={Clock}    label="Last seen" value={formatTimeAgo(meData?.last_seen)}     />
                <InfoRow icon={Clock}    label="Last login" value={formatTimeAgo(meData?.last_login)}   />
              </>
            )}
          </div>
        </div>
      </motion.div>

      {isDemoMode && (
        <motion.div
          initial    = {{ opacity: 0, y: 6 }}
          animate    = {{ opacity: 1, y: 0 }}
          transition = {{ delay: 0.05 }}
          className  = "rounded-lg border border-border bg-card overflow-hidden"
        >
          <div className="flex items-center gap-2.5 border-b border-border px-6 py-4">
            <Crown className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-semibold text-foreground">Try Different Tiers</p>
          </div>
          <div className="p-6 space-y-4">
            <p className="text-xs text-muted-foreground">
              Switch tiers to see how the dashboard changes. Each tier unlocks different features.
            </p>
            <div className="grid grid-cols-3 gap-2">
              {TIERS.map(t => {
                const tc       = getTierConfig(t)
                const isActive = demoTier === t
                return (
                  <button
                    key       = {t}
                    onClick   = {() => setDemoTier(t)}
                    className = {cn(
                      'rounded-lg border p-4 text-left transition-all space-y-1',
                      isActive
                        ? 'border-foreground/20 bg-foreground/5'
                        : 'border-border bg-background hover:bg-accent'
                    )}
                  >
                    <p className={cn('text-sm font-semibold', tc.text)}>
                      {tc.label}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t === 'free'  && 'Delayed signals'}
                      {t === 'pro'   && 'Live signals + levels'}
                      {t === 'elite' && 'Full access + AI'}
                    </p>
                    {isActive && (
                      <p className="text-xs font-medium text-foreground mt-1">
                        Active
                      </p>
                    )}
                  </button>
                )
              })}
            </div>
            <div className="rounded-md border border-border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground leading-relaxed">
                You are exploring as <span className={cn('font-semibold', tierCfg.text)}>{tierCfg.label}</span>.
                Navigate to any page to see what this tier can access.
                Locked sections show upgrade prompts.
              </p>
            </div>
          </div>
        </motion.div>
      )}

      <motion.div
        initial    = {{ opacity: 0, y: 6 }}
        animate    = {{ opacity: 1, y: 0 }}
        transition = {{ delay: 0.05 }}
        className  = "rounded-lg border border-border bg-card overflow-hidden"
      >
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-2.5">
            <Crown className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm font-semibold text-foreground">Subscription</p>
          </div>
          <span className={cn(
            'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
            tierCfg.bg, tierCfg.text, 'border-current/20'
          )}>
            {tierCfg.label}
          </span>
        </div>
        <div className="p-6 space-y-5">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-foreground">
              {tierCfg.label} Plan
            </p>
            {!isDemoMode && activeTier !== 'admin' && activeTier !== 'elite' && (
              <a
                href      = "/pricing"
                className = "flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/90 transition-colors"
              >
                Upgrade
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
            {isDemoMode && (
              <a
                href      = "/login"
                className = "flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/90 transition-colors"
              >
                Get Real Access
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>

          <div className="space-y-2">
            <p className="label-xs">Your Plan Includes</p>
            <div className="space-y-2">
              {features.map(f => (
                <div key={f.label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      'h-1.5 w-1.5 rounded-full shrink-0',
                      f.available
                        ? 'bg-[hsl(var(--chart-1))]'
                        : 'bg-muted-foreground/30'
                    )} />
                    <span className={cn(
                      'text-xs',
                      f.available ? 'text-foreground' : 'text-muted-foreground'
                    )}>
                      {f.label}
                    </span>
                  </div>
                  <span className={cn(
                    'text-xs font-medium',
                    f.available ? 'text-foreground' : 'text-muted-foreground/50'
                  )}>
                    {f.value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {!isDemoMode && (
            <div className="rounded-md border border-[hsl(var(--chart-4)/0.2)] bg-[hsl(var(--chart-4)/0.06)] px-4 py-3">
              <p className="text-xs font-medium text-[hsl(var(--chart-4))]">
                Stripe integration coming soon
              </p>
              <p className="text-xs text-[hsl(var(--chart-4)/0.7)] mt-0.5">
                Contact admin to upgrade your plan manually.
              </p>
            </div>
          )}

          {isDemoMode && (
            <div className="rounded-md border border-border bg-muted/30 px-4 py-3">
              <p className="text-xs text-muted-foreground leading-relaxed">
                This is a demo. Sign up with Google to get a real account and access live signals.
              </p>
            </div>
          )}
        </div>
      </motion.div>

    </div>
  )
}

function InfoRow({
  icon: Icon,
  label,
  value,
  mono = false,
}: {
  icon:  React.ElementType
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted">
        <Icon className="h-3 w-3 text-muted-foreground" />
      </div>
      <div className="flex flex-1 items-center justify-between min-w-0">
        <span className="text-xs text-muted-foreground shrink-0">{label}</span>
        <span className={cn(
          'text-xs text-foreground text-right truncate ml-3',
          mono && 'font-mono'
        )}>
          {value}
        </span>
      </div>
    </div>
  )
}
