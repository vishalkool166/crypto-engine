import { cn } from '@/lib/utils'
import { Lock } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import type { Tier, TierFeatures } from '@/types'

interface TierGateProps {
  feature?:       keyof TierFeatures
  requiredTier?:  Tier
  children:       React.ReactNode
  fallback?:      React.ReactNode
  blur?:          boolean
  className?:     string
}

export default function TierGate({
  feature,
  requiredTier,
  children,
  fallback,
  blur      = false,
  className,
}: TierGateProps) {
  const { hasFeature, canAccess } = useAuthStore()

  const allowed =
    (feature      ? hasFeature(feature)           : true) &&
    (requiredTier ? canAccess(requiredTier)        : true)

  if (allowed) return <>{children}</>
  if (fallback)  return <>{fallback}</>
  if (blur) {
    return (
      <div className={cn('relative', className)}>
        <div className="pointer-events-none select-none opacity-30 blur-sm">
          {children}
        </div>
      </div>
    )
  }
  return null
}

interface LockedCellProps {
  requiredTier: Tier
  width?:       string
}

export function LockedCell({ requiredTier, width = 'w-16' }: LockedCellProps) {
  const label = requiredTier === 'pro' ? 'Pro' : requiredTier === 'elite' ? 'Elite' : 'Admin'
  return (
    <div className="flex items-center gap-1.5">
      <div className={cn('h-4 rounded bg-muted', width)} />
      <span className="inline-flex items-center gap-0.5 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
        <Lock className="h-2.5 w-2.5" />
        {label}
      </span>
    </div>
  )
}

interface LockedSectionProps {
  requiredTier:  Tier
  title:         string
  description?:  string
  className?:    string
  rows?:         number
}

export function LockedSection({
  requiredTier,
  title,
  description,
  className,
  rows = 3,
}: LockedSectionProps) {
  const tierLabel = requiredTier === 'pro'
    ? 'Pro'
    : requiredTier === 'elite'
    ? 'Elite'
    : 'Admin'

  const tierPrice = requiredTier === 'pro'
    ? '$29/mo'
    : requiredTier === 'elite'
    ? '$79/mo'
    : ''

  return (
    <div className={cn('relative rounded-lg border border-border overflow-hidden', className)}>
      <div className="space-y-2 p-4 pointer-events-none select-none">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="h-4 rounded bg-muted shimmer" style={{ width: `${60 + i * 10}%` }} />
            <div className="h-4 w-16 rounded bg-muted shimmer" />
          </div>
        ))}
      </div>

      <div className="absolute inset-0 flex flex-col items-center justify-center bg-card/80 backdrop-blur-[2px] p-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-card mb-3">
          <Lock className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
        <p className="text-sm font-semibold text-foreground text-center">{title}</p>
        {description && (
          <p className="text-xs text-muted-foreground text-center mt-1 max-w-xs">
            {description}
          </p>
        )}
        <a
          href      = "/pricing"
          className = {cn(
            'mt-4 inline-flex items-center gap-1.5 rounded-md px-4 py-2',
            'text-xs font-semibold transition-colors',
            'bg-foreground text-background hover:bg-foreground/90'
          )}
        >
          Upgrade to {tierLabel}
          {tierPrice && (
            <span className="opacity-60">{tierPrice}</span>
          )}
        </a>
      </div>
    </div>
  )
}

interface DelayedSignalProps {
  availableIn: number
  coin:        string
  grade:       string
  direction:   string
  score:       number
}

export function DelayedSignal({
  availableIn,
  coin,
  grade,
  direction,
  score,
}: DelayedSignalProps) {
  const hours   = Math.floor(availableIn / 60)
  const minutes = availableIn % 60
  const label   = hours > 0
    ? `${hours}h ${minutes}m`
    : `${minutes}m`

  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-border">
      <div className="flex items-center gap-4">
        <span className="inline-flex items-center justify-center rounded border border-border bg-muted font-mono text-xs font-semibold text-muted-foreground px-2 py-0.5">
          {grade}
        </span>
        <span className="font-mono text-sm font-medium text-muted-foreground">
          {coin}USDT
        </span>
        <span className="text-xs text-muted-foreground">{direction}</span>
        <span className="text-xs font-mono text-muted-foreground">{score}</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <p className="text-xs text-muted-foreground">Available in</p>
          <p className="text-sm font-mono font-semibold text-foreground">{label}</p>
        </div>
        <a
          href      = "/pricing"
          className = "rounded-md bg-foreground px-3 py-1.5 text-xs font-semibold text-background hover:bg-foreground/90 transition-colors"
        >
          Upgrade
        </a>
      </div>
    </div>
  )
}