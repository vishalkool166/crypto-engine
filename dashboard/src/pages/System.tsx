import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSystemStatus, useModeStatus } from '@/hooks/useHealth'
import { useToggleMode, useDockerPurge, useSyncOutcomes } from '@/hooks/useAdmin'
import { useAuthStore } from '@/stores/authStore'
import { useQueryClient } from '@tanstack/react-query'
import TotpModal from '@/components/modals/TotpModal'
import SystemInfra from '@/components/system/SystemInfra'
import SystemML from '@/components/system/SystemML'
import SystemAdaptations from '@/components/system/SystemAdaptations'
import CollapsibleSection from '@/components/ui/CollapsibleSection'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import { toast } from 'sonner'

const TABS = [
  { id: 'infra',       label: 'Infrastructure' },
  { id: 'ml',          label: 'ML Model'        },
  { id: 'adaptations', label: 'Adaptations'     },
]

export default function System() {
  const { isAdmin }                       = useAuthStore()
  const queryClient                       = useQueryClient()
  const [tab,           setTab]           = useState('infra')
  const [purgeTotpOpen, setPurgeTotpOpen] = useState(false)
  const [modeTotpOpen,  setModeTotpOpen]  = useState(false)
  const [pendingMode,   setPendingMode]   = useState<'live' | 'paper' | null>(null)

  const {
    system, wsStreams, wsConnected, redisConnected,
    engineOk, mlEnabled, mlProgress, alerts, isLoading,
  } = useSystemStatus()

  const { data: modeStatus } = useModeStatus()
  const toggleMode           = useToggleMode()
  const dockerPurge          = useDockerPurge()
  const syncOutcomes         = useSyncOutcomes()

  if (!isAdmin) {
    return (
      <div className="p-4 md:p-6">
        <p className="text-sm text-muted-foreground">Access restricted.</p>
      </div>
    )
  }

  if (isLoading) return <PageSkeleton />

  const isLive = modeStatus?.mode === 'live'

  return (
    <div className="p-4 md:p-6 space-y-4">

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-foreground">System</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Infrastructure monitor and controls
          </p>
        </div>
        <button
          onClick   = {() => queryClient.invalidateQueries({ queryKey: ['health'] })}
          className = "flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors"
        >
          Refresh
        </button>
      </div>

      {alerts.length > 0 && (
        <div className="rounded-lg border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-4 py-3 space-y-1">
          {alerts.map((a, i) => (
            <p key={i} className="text-xs font-medium text-[hsl(var(--chart-2))]">{a}</p>
          ))}
        </div>
      )}

      <div className="flex items-center gap-px rounded-md border border-border overflow-hidden w-fit">
        {TABS.map(t => (
          <button
            key       = {t.id}
            onClick   = {() => setTab(t.id)}
            className = {cn(
              'px-4 py-2 text-xs font-medium transition-colors',
              tab === t.id
                ? 'bg-foreground text-background'
                : 'text-muted-foreground hover:text-foreground bg-background'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'infra' && (
        <SystemInfra
          system         = {system}
          wsStreams       = {wsStreams}
          wsConnected    = {wsConnected}
          redisConnected = {redisConnected}
          engineOk       = {engineOk}
          mlEnabled      = {mlEnabled}
          mlProgress     = {mlProgress}
        />
      )}

      {tab === 'ml' && (
        <SystemML
          mlStatus   = {null}
          mlProgress = {mlProgress}
          mlEnabled  = {mlEnabled}
        />
      )}

      {tab === 'adaptations' && <SystemAdaptations />}

      <CollapsibleSection title="Trading Mode" defaultOpen={tab === 'infra'}>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <p className="text-xs text-muted-foreground">
              {isLive
                ? 'Live trading — real funds at risk.'
                : 'Paper trading — simulated with Binance Demo account.'
              }
            </p>
            <div className={cn(
              'flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium',
              isLive
                ? 'border-[hsl(var(--chart-2)/0.3)] bg-[hsl(var(--chart-2)/0.08)] text-[hsl(var(--chart-2))]'
                : 'border-[hsl(var(--chart-3)/0.3)] bg-[hsl(var(--chart-3)/0.08)] text-[hsl(var(--chart-3))]'
            )}>
              <span className={cn(
                'h-1.5 w-1.5 rounded-full',
                isLive ? 'bg-[hsl(var(--chart-2))] animate-pulse-dot' : 'bg-[hsl(var(--chart-3))]'
              )} />
              {isLive ? 'Live' : 'Paper'}
            </div>
          </div>
          {modeStatus && (
            <p className="text-xs text-muted-foreground">
              Active grades:{' '}
              <span className="font-mono font-medium text-foreground">
                {modeStatus.grades.join(', ')}
              </span>
            </p>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick   = {() => { setPendingMode('paper'); setModeTotpOpen(true) }}
              disabled  = {!isLive}
              className = {cn(
                'rounded-md border px-4 py-2 text-sm font-medium transition-colors',
                !isLive
                  ? 'border-[hsl(var(--chart-3)/0.3)] bg-[hsl(var(--chart-3)/0.08)] text-[hsl(var(--chart-3))] cursor-default'
                  : 'border-border bg-background text-foreground hover:bg-accent'
              )}
            >
              Paper Mode
            </button>
            <button
              onClick   = {() => { setPendingMode('live'); setModeTotpOpen(true) }}
              disabled  = {isLive}
              className = {cn(
                'rounded-md border px-4 py-2 text-sm font-medium transition-colors',
                isLive
                  ? 'border-[hsl(var(--chart-2)/0.3)] bg-[hsl(var(--chart-2)/0.08)] text-[hsl(var(--chart-2))] cursor-default'
                  : 'border-border bg-background text-foreground hover:bg-accent'
              )}
            >
              Live Mode
            </button>
            <button
              onClick   = {() => syncOutcomes.mutate()}
              disabled  = {syncOutcomes.isPending}
              className = "rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
            >
              Sync Outcomes
            </button>
          </div>
        </div>
      </CollapsibleSection>

      <div className="rounded-lg border border-[hsl(var(--chart-2)/0.15)] bg-card overflow-hidden">
        <div className="border-b border-[hsl(var(--chart-2)/0.15)] px-6 py-4 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-[hsl(var(--chart-2))]" />
          <p className="text-sm font-semibold text-foreground">Danger Zone</p>
        </div>
        <div className="p-6 flex items-center justify-between flex-wrap gap-4">
          <div>
            <p className="text-sm font-medium text-foreground">Docker System Purge</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Remove unused images, containers, volumes. Frees disk space.
            </p>
          </div>
          <button
            onClick   = {() => setPurgeTotpOpen(true)}
            className = "flex items-center gap-2 rounded-md border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-3 py-2 text-sm font-medium text-[hsl(var(--chart-2))] hover:bg-[hsl(var(--chart-2)/0.12)] transition-colors"
          >
            Purge
          </button>
        </div>
      </div>

      <TotpModal
        open        = {purgeTotpOpen}
        title       = "Confirm Docker Purge"
        description = "This will remove all unused Docker resources"
        destructive
        loading     = {dockerPurge.isPending}
        onClose     = {() => setPurgeTotpOpen(false)}
        onConfirm   = {async (code) => {
          await dockerPurge.mutateAsync(code)
          setPurgeTotpOpen(false)
        }}
      />

      <TotpModal
        open        = {modeTotpOpen}
        title       = {`Switch to ${pendingMode === 'live' ? 'Live' : 'Paper'} Mode`}
        description = {pendingMode === 'live' ? 'Real funds will be used.' : 'Switch to paper trading.'}
        destructive = {pendingMode === 'live'}
        loading     = {toggleMode.isPending}
        onClose     = {() => { setModeTotpOpen(false); setPendingMode(null) }}
        onConfirm   = {async (code) => {
          if (!pendingMode) return
          await toggleMode.mutateAsync({ mode: pendingMode, totp_code: code })
          setModeTotpOpen(false)
          setPendingMode(null)
        }}
      />
    </div>
  )
}