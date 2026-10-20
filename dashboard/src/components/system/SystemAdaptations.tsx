import { useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Check, X, RotateCcw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatTimeAgo } from '@/lib/utils'
import CollapsibleSection from '@/components/ui/CollapsibleSection'
import TotpModal from '@/components/modals/TotpModal'
import {
  useAdaptationHistory, usePendingRecommendations,
  useActiveCheckpoints, useVersionHistory,
  useApproveRecommendation, useRejectRecommendation,
  useManualRollback, useCurrentParameters,
} from '@/hooks/useAdaptations'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'

const CONFIDENCE_STYLES: Record<string, { text: string; bg: string; border: string }> = {
  high:     { text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]', border: 'border-[hsl(var(--chart-1)/0.2)]' },
  medium:   { text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]', border: 'border-[hsl(var(--chart-4)/0.2)]' },
  low:      { text: 'text-muted-foreground',       bg: 'bg-muted',                       border: 'border-border'                    },
  very_low: { text: 'text-muted-foreground',       bg: 'bg-muted',                       border: 'border-border'                    },
}

const KEY_PARAMS = [
  { key: 'sweep_min_score',       label: 'Sweep Min Score'     },
  { key: 'zone_min_score',        label: 'Zone Min Score'      },
  { key: 'grade_a_threshold',     label: 'Grade A Threshold'   },
  { key: 'grade_aplus_threshold', label: 'Grade A+ Threshold'  },
  { key: 'sweep_max_age_hours',   label: 'Sweep Max Age (hrs)' },
  { key: 'base_risk_pct',         label: 'Base Risk %'         },
  { key: 'max_open_trades',       label: 'Max Open Trades'     },
  { key: 'max_leverage',          label: 'Max Leverage'        },
]

interface Recommendation {
  id:                   number
  parameter:            string
  current_value:        number
  recommended_value:    number
  direction:            string
  expected_improvement: number | null
  data_basis:           number | null
  confidence:           string | null
  reasoning:            string | null
  status:               string
  created_at:           string | null
}

interface AdaptationLog {
  id:             number
  parameter:      string
  old_value:      number
  new_value:      number
  direction:      string
  reasoning:      string | null
  data_basis:     number | null
  version_before: string | null
  version_after:  string | null
  applied_at:     string | null
  rolled_back:    boolean
}

interface VersionRecord {
  version:        string
  created_at:     string | null
  change_reason:  string | null
  changed_by:     string | null
  trade_count_at: number
  is_current:     boolean
  parameters:     Record<string, unknown>
}

export default function SystemAdaptations() {
  const { isDemoMode }                        = useDemoStore()
  const [rollbackOpen,  setRollbackOpen]      = useState(false)
  const [rollbackParam, setRollbackParam]     = useState<string | null>(null)

  const { data: adaptHistory  } = useAdaptationHistory(20)
  const { data: pendingRecs   } = usePendingRecommendations()
  const { data: versions      } = useVersionHistory(10)
  const { data: currentParams } = useCurrentParameters()

  const approve  = useApproveRecommendation()
  const reject   = useRejectRecommendation()
  const rollback = useManualRollback()

  const pendingList  = (pendingRecs  as Recommendation[]  | undefined) ?? []
  const historyList  = (adaptHistory as AdaptationLog[]   | undefined) ?? []
  const versionList  = (versions     as VersionRecord[]   | undefined) ?? []
  const params       = (currentParams as Record<string, unknown> | undefined) ?? {}
  const currentVersion = versionList.find(v => v.is_current)

  return (
    <div className="space-y-4">
      <CollapsibleSection
        title = "Current Parameters"
        badge = {
          currentVersion ? (
            <span className="text-xs font-mono text-muted-foreground">
              v{currentVersion.version}
            </span>
          ) : undefined
        }
      >
        <div className="p-6">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {KEY_PARAMS.map(p => (
              <div
                key       = {p.key}
                className = "flex items-center justify-between rounded-md border border-border bg-background px-3 py-2.5"
              >
                <span className="text-xs text-muted-foreground">{p.label}</span>
                <span className="text-xs font-mono font-semibold text-foreground">
                  {params[p.key] !== undefined ? String(params[p.key]) : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title = "Pending Recommendations"
        count = {pendingList.length}
      >
        <div className="p-4 space-y-3">
          {pendingList.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">
              No pending recommendations
            </p>
          ) : (
            pendingList.map((rec: Recommendation) => {
              const conf    = CONFIDENCE_STYLES[rec.confidence ?? 'low'] ?? CONFIDENCE_STYLES.low
              const isInc   = rec.direction === 'increase'
              const DirIcon = isInc ? TrendingUp : TrendingDown
              return (
                <div key={rec.id} className="rounded-lg border border-border bg-background p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-mono font-semibold text-foreground">
                          {rec.parameter}
                        </span>
                        <span className={cn(
                          'inline-flex items-center rounded border px-1.5 py-px text-xs font-medium',
                          conf.text, conf.bg, conf.border
                        )}>
                          {rec.confidence ?? 'low'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="font-mono text-muted-foreground">{rec.current_value}</span>
                        <DirIcon className={cn('h-3 w-3', isInc ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')} />
                        <span className="font-mono font-semibold text-foreground">{rec.recommended_value}</span>
                        {rec.expected_improvement !== null && rec.expected_improvement !== undefined && (
                          <span className="text-[hsl(var(--chart-1))]">
                            +{(rec.expected_improvement ?? 0).toFixed(1)}% WR
                          </span>
                        )}
                      </div>
                      {rec.reasoning && (
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {rec.reasoning.slice(0, 120)}{rec.reasoning.length > 120 ? '...' : ''}
                        </p>
                      )}
                    </div>
                    {!isDemoMode && (
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick   = {() => reject.mutate({ id: rec.id })}
                          disabled  = {reject.isPending}
                          className = "flex h-8 w-8 items-center justify-center rounded-md border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] text-[hsl(var(--chart-2))] hover:bg-[hsl(var(--chart-2)/0.12)] transition-colors disabled:opacity-50"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick   = {() => approve.mutate(rec.id)}
                          disabled  = {approve.isPending}
                          className = "flex h-8 w-8 items-center justify-center rounded-md border border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.06)] text-[hsl(var(--chart-1))] hover:bg-[hsl(var(--chart-1)/0.12)] transition-colors disabled:opacity-50"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Version History" count={versionList.length}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[400px]">
            <thead className="border-b border-border">
              <tr>
                {['Version', 'Changed', 'Reason', 'Trades', ''].map(h => (
                  <th key={h} className="table-header-cell">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {versionList.length === 0 ? (
                <tr>
                  <td colSpan={5} className="table-cell text-center text-muted-foreground">
                    No version history
                  </td>
                </tr>
              ) : (
                versionList.map((v: VersionRecord) => (
                  <tr key={v.version} className={cn('table-row', v.is_current && 'bg-muted/20')}>
                    <td className="table-cell">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-foreground">{v.version}</span>
                        {v.is_current && (
                          <span className="inline-flex items-center rounded-full bg-[hsl(var(--chart-1)/0.1)] text-[hsl(var(--chart-1))] text-xs font-medium px-1.5 py-px">
                            current
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="table-cell text-xs text-muted-foreground">{formatTimeAgo(v.created_at)}</td>
                    <td className="table-cell text-xs text-muted-foreground max-w-[200px] truncate">{v.change_reason ?? '—'}</td>
                    <td className="table-cell font-mono text-xs text-muted-foreground">{v.trade_count_at}</td>
                    <td className="table-cell">
                      {!v.is_current && !isDemoMode && (
                        <button
                          onClick   = {() => { setRollbackParam(v.version); setRollbackOpen(true) }}
                          className = "text-xs text-muted-foreground hover:text-foreground transition-colors"
                        >
                          Restore
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title="Adaptation Log" count={historyList.length}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px]">
            <thead className="border-b border-border">
              <tr>
                {['Parameter', 'Change', 'Data Basis', 'Applied', 'Status'].map(h => (
                  <th key={h} className="table-header-cell">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {historyList.length === 0 ? (
                <tr>
                  <td colSpan={5} className="table-cell text-center text-muted-foreground">
                    No adaptation history
                  </td>
                </tr>
              ) : (
                historyList.map((log: AdaptationLog) => {
                  const isInc   = log.direction === 'increase'
                  const DirIcon = isInc ? TrendingUp : TrendingDown
                  return (
                    <tr key={log.id} className="table-row">
                      <td className="table-cell font-mono text-xs font-semibold text-foreground">{log.parameter}</td>
                      <td className="table-cell">
                        <div className="flex items-center gap-1.5 text-xs">
                          <span className="font-mono text-muted-foreground">{log.old_value}</span>
                          <DirIcon className={cn('h-3 w-3 shrink-0', isInc ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')} />
                          <span className="font-mono font-semibold text-foreground">{log.new_value}</span>
                        </div>
                      </td>
                      <td className="table-cell font-mono text-xs text-muted-foreground">{log.data_basis ?? '—'}</td>
                      <td className="table-cell text-xs text-muted-foreground">{formatTimeAgo(log.applied_at)}</td>
                      <td className="table-cell">
                        {log.rolled_back ? (
                          <span className="inline-flex items-center gap-1 text-xs text-[hsl(var(--chart-4))]">
                            <RotateCcw className="h-3 w-3" />
                            Rolled back
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-[hsl(var(--chart-1))]">
                            <Check className="h-3 w-3" />
                            Applied
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </CollapsibleSection>

      <TotpModal
        open        = {rollbackOpen}
        title       = "Confirm Rollback"
        description = {rollbackParam ? `Rollback to version: ${rollbackParam}` : ''}
        destructive
        loading     = {rollback.isPending}
        onClose     = {() => { setRollbackOpen(false); setRollbackParam(null) }}
        onConfirm   = {async () => {
          if (!rollbackParam) return
          await rollback.mutateAsync(rollbackParam)
          setRollbackOpen(false)
          setRollbackParam(null)
        }}
      />
    </div>
  )
}
