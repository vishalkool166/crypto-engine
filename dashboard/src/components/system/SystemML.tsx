import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { formatTimeAgo } from '@/lib/utils'
import { scoreToColor } from '@/lib/tokens'
import CollapsibleSection from '@/components/ui/CollapsibleSection'
import ScoreBar from '@/components/ui/ScoreBar'

interface MLStatusData {
  ml_enabled:    boolean
  closed_trades: number
  required:      number
  message:       string
  cv_auc?:       number
  win_rate?:     number
  trained_at?:   string | null
  top_features?: Array<{ feature: string; importance: number }>
}

interface MLProgress {
  closed:   number
  required: number
  pct:      number
  message:  string
}

interface Props {
  mlStatus:   MLStatusData | null | undefined
  mlProgress: MLProgress
  mlEnabled:  boolean
}

function StatBox({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="rounded-md border border-border bg-background p-3">
      <p className="label-xs">{label}</p>
      <p className={cn('text-sm font-mono font-semibold text-foreground mt-1.5', valueClass)}>
        {value}
      </p>
    </div>
  )
}

export default function SystemML({ mlStatus, mlProgress, mlEnabled }: Props) {
  return (
    <CollapsibleSection
      title = "ML Model"
      badge = {
        <span className={cn(
          'inline-flex items-center rounded-md border px-2 py-px text-xs font-medium',
          mlEnabled
            ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.08)] text-[hsl(var(--chart-1))]'
            : 'border-[hsl(var(--chart-4)/0.2)] bg-[hsl(var(--chart-4)/0.08)] text-[hsl(var(--chart-4))]'
        )}>
          {mlEnabled ? 'Active' : 'Collecting'}
        </span>
      }
    >
      <div className="p-6 space-y-5">
        {!mlEnabled && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-mono">
                {mlProgress.closed} / {mlProgress.required} trades
              </span>
              <span className="text-xs font-medium text-[hsl(var(--chart-4))]">
                {mlProgress.pct}%
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <motion.div
                initial    = {{ width: 0 }}
                animate    = {{ width: `${mlProgress.pct}%` }}
                transition = {{ duration: 0.8, ease: 'easeOut' }}
                className  = "h-full rounded-full bg-[hsl(var(--chart-4))]"
              />
            </div>
            <p className="text-xs text-muted-foreground">{mlProgress.message}</p>
          </div>
        )}

        {mlStatus && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatBox
              label = "Samples"
              value = {mlStatus.closed_trades ? String(mlStatus.closed_trades) : '—'}
            />
            <StatBox
              label      = "CV AUC"
              value      = {mlStatus.cv_auc ? String(mlStatus.cv_auc) : '—'}
              valueClass = {
                (mlStatus.cv_auc ?? 0) >= 0.7
                  ? 'text-[hsl(var(--chart-1))]'
                  : (mlStatus.cv_auc ?? 0) >= 0.6
                  ? 'text-[hsl(var(--chart-4))]'
                  : 'text-[hsl(var(--chart-2))]'
              }
            />
            <StatBox
              label = "Win Rate"
              value = {mlStatus.win_rate ? `${mlStatus.win_rate}%` : '—'}
            />
            <StatBox
              label = "Trained"
              value = {mlStatus.trained_at ? formatTimeAgo(mlStatus.trained_at) : '—'}
            />
          </div>
        )}

        {mlStatus?.top_features && mlStatus.top_features.length > 0 && (
          <div className="space-y-2">
            <p className="label-xs">Top Features</p>
            <div className="space-y-2">
              {mlStatus.top_features.slice(0, 5).map((f: { feature: string; importance: number }) => {
                const max = mlStatus.top_features![0]?.importance ?? 1
                const pct = Math.round((f.importance / max) * 100)
                return (
                  <ScoreBar
                    key       = {f.feature}
                    score     = {pct}
                    label     = {f.feature.replace(/_/g, ' ')}
                    size      = "sm"
                    className = "capitalize"
                  />
                )
              })}
            </div>
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}