import { useState } from 'react'
import { Activity, BarChart3, TrendingUp, GitBranch, Filter, Brain, Calendar } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import { useNavigate } from 'react-router-dom'
import EngineHealthCard from '@/components/engine/EngineHealthCard'
import RejectionStats from '@/components/engine/RejectionStats'
import RelativeStrength from '@/components/engine/RelativeStrength'
import DecisionTrace from '@/components/engine/DecisionTrace'
import FilterAnalysis from '@/components/engine/FilterAnalysis'
import { useMLValidation, useMonthlyHistory } from '@/hooks/useEngine'
import { formatCurrency, formatPercent, formatTimeAgo } from '@/lib/utils'
import { pnlColor } from '@/lib/tokens'

const TABS = [
  { id: 'overview',  label: 'Overview',         icon: Activity   },
  { id: 'traces',    label: 'Decision Traces',   icon: GitBranch  },
  { id: 'rejections',label: 'Rejections',        icon: BarChart3  },
  { id: 'rs',        label: 'Relative Strength', icon: TrendingUp },
  { id: 'filters',   label: 'Filter Analysis',   icon: Filter     },
  { id: 'ml',        label: 'ML Validation',     icon: Brain      },
  { id: 'monthly',   label: 'Monthly Reports',   icon: Calendar   },
]

function MLValidationPanel() {
  const { data: validation, isLoading } = useMLValidation()

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-12 w-full rounded-lg border border-border shimmer" />
        ))}
      </div>
    )
  }

  if (!validation || (validation as { error?: string }).error) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center">
        <Brain className="h-8 w-8 text-muted-foreground/20 mx-auto mb-3" />
        <p className="text-sm font-medium text-foreground">No model trained yet</p>
        <p className="text-xs text-muted-foreground mt-1">
          ML activates after 100 closed trades
        </p>
      </div>
    )
  }

  const v = validation as {
    trained_at?:       string | null
    samples?:          number
    win_rate?:         number
    cv_auc?:           number | null
    cv_std?:           number | null
    train_auc?:        number | null
    precision?:        number | null
    recall?:           number | null
    f1?:               number | null
    calibrated?:       boolean
    threshold?:        number
    confusion_matrix?: { true_positive: number; true_negative: number; false_positive: number; false_negative: number } | null
    top_features?:     Array<{ feature: string; importance: number }>
    shap_top_features?:Array<{ feature: string; shap_mean: number }>
  }

  const cm = v.confusion_matrix

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: 'Samples',    value: String(v.samples ?? '—')                                                    },
          { label: 'CV AUC',     value: v.cv_auc ? `${v.cv_auc} ± ${v.cv_std ?? 0}` : '—'                         },
          { label: 'Precision',  value: v.precision ? String(v.precision) : '—'                                     },
          { label: 'Recall',     value: v.recall    ? String(v.recall)    : '—'                                     },
          { label: 'F1 Score',   value: v.f1        ? String(v.f1)        : '—'                                     },
          { label: 'Train AUC',  value: v.train_auc ? String(v.train_auc) : '—'                                     },
          { label: 'Calibrated', value: v.calibrated ? 'Yes' : 'No'                                                 },
          { label: 'Trained',    value: v.trained_at ? formatTimeAgo(v.trained_at) : '—'                            },
        ].map(item => (
          <div key={item.label} className="rounded-lg border border-border bg-card p-4">
            <p className="label-xs">{item.label}</p>
            <p className="text-sm font-mono font-semibold text-foreground mt-1.5">{item.value}</p>
          </div>
        ))}
      </div>

      {cm && (
        <div className="rounded-lg border border-border bg-card p-5">
          <p className="text-sm font-semibold text-foreground mb-4">Confusion Matrix</p>
          <div className="grid grid-cols-2 gap-2 max-w-xs">
            {[
              { label: 'True Positive',  value: cm.true_positive,  color: 'text-[hsl(var(--chart-1))]' },
              { label: 'False Positive', value: cm.false_positive, color: 'text-[hsl(var(--chart-2))]' },
              { label: 'False Negative', value: cm.false_negative, color: 'text-[hsl(var(--chart-2))]' },
              { label: 'True Negative',  value: cm.true_negative,  color: 'text-[hsl(var(--chart-1))]' },
            ].map(item => (
              <div key={item.label} className="rounded-md border border-border bg-background p-3 text-center">
                <p className="label-xs">{item.label}</p>
                <p className={cn('text-lg font-mono font-semibold mt-1', item.color)}>{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {v.top_features && v.top_features.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-5">
          <p className="text-sm font-semibold text-foreground mb-4">Top Features by Importance</p>
          <div className="space-y-2">
            {v.top_features.slice(0, 8).map((f, i) => {
              const max = v.top_features![0]?.importance ?? 1
              const pct = Math.round((f.importance / max) * 100)
              return (
                <div key={f.feature} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-foreground capitalize">{f.feature.replace(/_/g, ' ')}</span>
                    <span className="text-xs font-mono text-muted-foreground">{f.importance}</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className = "h-full rounded-full bg-[hsl(var(--chart-3))]"
                      style     = {{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function MonthlyReportsPanel() {
  const { data: reports, isLoading } = useMonthlyHistory(3)

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-32 w-full rounded-lg border border-border shimmer" />
        ))}
      </div>
    )
  }

  const list = (reports as Array<{
    period_label:  string
    trades:        number
    win_rate:      number
    total_pnl:     number
    total_pnl_pos: boolean
    profit_factor: number
    max_drawdown:  number
    best_regime:   string
    worst_regime:  string
    top_rejection: string
    error?:        string
  }> | undefined) ?? []

  if (list.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center">
        <Calendar className="h-8 w-8 text-muted-foreground/20 mx-auto mb-3" />
        <p className="text-sm font-medium text-foreground">No monthly reports yet</p>
        <p className="text-xs text-muted-foreground mt-1">Reports generate on the 1st of each month</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {list.map((report, i) => {
        if (report.error) return null
        return (
          <div key={i} className="rounded-lg border border-border bg-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <p className="text-sm font-semibold text-foreground">{report.period_label}</p>
              <span className={cn('text-sm font-mono font-semibold', pnlColor(report.total_pnl))}>
                {formatCurrency(report.total_pnl)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4">
              {[
                { label: 'Trades',         value: String(report.trades)                              },
                { label: 'Win Rate',       value: formatPercent(report.win_rate, false)              },
                { label: 'Profit Factor',  value: String(report.profit_factor)                       },
                { label: 'Max Drawdown',   value: formatPercent(report.max_drawdown, false)          },
                { label: 'Best Regime',    value: report.best_regime  || '—'                         },
                { label: 'Worst Regime',   value: report.worst_regime || '—'                         },
                { label: 'Top Rejection',  value: (report.top_rejection || '—').replace(/_/g, ' ')  },
              ].map(item => (
                <div key={item.label} className="bg-card px-4 py-3">
                  <p className="label-xs">{item.label}</p>
                  <p className="text-xs font-medium text-foreground mt-1 capitalize">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function Engine() {
  const { isAdmin } = useAuthStore()
  const navigate    = useNavigate()
  const [tab, setTab] = useState('overview')

  if (!isAdmin) {
    navigate('/', { replace: true })
    return null
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div>
        <h1 className="text-base font-semibold text-foreground">Engine Intelligence</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Signal engine observability, filter analysis, and ML validation
        </p>
      </div>

      <div className="flex items-center gap-px overflow-x-auto scrollbar-none rounded-md border border-border w-fit">
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button
              key       = {t.id}
              onClick   = {() => setTab(t.id)}
              className = {cn(
                'flex items-center gap-1.5 px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors',
                tab === t.id
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground bg-background'
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{t.label}</span>
            </button>
          )
        })}
      </div>

      {tab === 'overview' && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <EngineHealthCard />
          </div>
          <div className="lg:col-span-2">
            <RejectionStats />
          </div>
        </div>
      )}

      {tab === 'traces'     && <DecisionTrace />}
      {tab === 'rejections' && <RejectionStats />}
      {tab === 'rs'         && <RelativeStrength />}
      {tab === 'filters'    && <FilterAnalysis />}
      {tab === 'ml'         && <MLValidationPanel />}
      {tab === 'monthly'    && <MonthlyReportsPanel />}
    </div>
  )
}