import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, Search, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatTimeAgo } from '@/lib/utils'
import { useEngineTraces, useTracesByCoin } from '@/hooks/useEngine'
import EmptyState from '@/components/ui/EmptyState'
import { Activity } from 'lucide-react'
import type { DecisionTrace as DecisionTraceType, TraceStep } from '@/types'

const STEP_COLORS: Record<string, string> = {
  PASS:    'text-[hsl(var(--chart-1))]',
  FAIL:    'text-[hsl(var(--chart-2))]',
  SCORE:   'text-[hsl(var(--chart-3))]',
  STOPPED: 'text-[hsl(var(--chart-2))]',
}

const STEP_BG: Record<string, string> = {
  PASS:    'bg-[hsl(var(--chart-1)/0.08)] border-[hsl(var(--chart-1)/0.2)]',
  FAIL:    'bg-[hsl(var(--chart-2)/0.08)] border-[hsl(var(--chart-2)/0.2)]',
  SCORE:   'bg-[hsl(var(--chart-3)/0.08)] border-[hsl(var(--chart-3)/0.2)]',
  STOPPED: 'bg-[hsl(var(--chart-2)/0.08)] border-[hsl(var(--chart-2)/0.2)]',
}

function StepRow({ step }: { step: TraceStep }) {
  const color = STEP_COLORS[step.result] ?? 'text-muted-foreground'
  const bg    = STEP_BG[step.result]    ?? 'bg-muted border-border'

  return (
    <div className={cn('flex items-start gap-3 rounded-md border px-3 py-2', bg)}>
      <div className="flex items-center gap-2 min-w-0 flex-1">
        <span className="text-xs font-mono text-foreground w-28 shrink-0">
          {step.name.replace(/_/g, ' ')}
        </span>
        <span className={cn('text-xs font-semibold shrink-0', color)}>
          {step.result}
        </span>
        {step.score !== 0 && (
          <span className="text-xs font-mono text-muted-foreground shrink-0">
            {step.score > 0 ? '+' : ''}{(step.score ?? 0).toFixed(2)}
          </span>
        )}
        {step.reason && (
          <span className="text-xs text-muted-foreground truncate">
            {step.reason}
          </span>
        )}
      </div>
    </div>
  )
}

function TraceCard({ trace, defaultOpen = false }: { trace: DecisionTraceType; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)

  const isTraded   = trace.final_decision === 'TRADE'
  const stoppedAt  = trace.stopped_at

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <button
        onClick   = {() => setOpen(o => !o)}
        className = "flex w-full items-center justify-between px-5 py-3.5 hover:bg-muted/20 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className={cn(
            'h-2 w-2 rounded-full shrink-0',
            isTraded ? 'bg-[hsl(var(--chart-1))]' : 'bg-[hsl(var(--chart-2))]'
          )} />
          <span className="font-mono font-semibold text-foreground text-sm">{trace.coin}</span>
          <span className="text-xs text-muted-foreground">{trace.direction}</span>
          {stoppedAt && (
            <span className="hidden sm:inline-flex items-center rounded border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-1.5 py-px text-xs text-[hsl(var(--chart-2))]">
              stopped: {stoppedAt.replace(/_/g, ' ')}
            </span>
          )}
          {isTraded && (
            <span className="hidden sm:inline-flex items-center rounded border border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.06)] px-1.5 py-px text-xs text-[hsl(var(--chart-1))]">
              Grade {trace.final_grade} · {(trace.final_score ?? 0).toFixed(1)}%
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-xs text-muted-foreground">
            {formatTimeAgo(trace.datetime)}
          </span>
          <ChevronDown className={cn(
            'h-4 w-4 text-muted-foreground transition-transform duration-200',
            open && 'rotate-180'
          )} />
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial    = {{ height: 0, opacity: 0 }}
            animate    = {{ height: 'auto', opacity: 1 }}
            exit       = {{ height: 0, opacity: 0 }}
            transition = {{ duration: 0.2 }}
            className  = "overflow-hidden border-t border-border"
          >
            <div className="p-4 space-y-2">
              <div className="flex items-center gap-4 mb-3 flex-wrap">
                <div className="text-xs text-muted-foreground">
                  Session: <span className="text-foreground">{trace.session || '—'}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  Regime: <span className="text-foreground">{trace.regime || '—'}</span>
                </div>
                {trace.final_score > 0 && (
                  <div className="text-xs text-muted-foreground">
                    Score: <span className="font-mono text-foreground">{(trace.final_score ?? 0).toFixed(1)}%</span>
                  </div>
                )}
              </div>
              {trace.steps.map((step, i) => (
                <StepRow key={i} step={step} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function DecisionTrace() {
  const [search, setSearch]     = useState('')
  const [coinFilter, setCoinFilter] = useState<string | null>(null)

  const { data: allTraces, isLoading } = useEngineTraces(100)
  const { data: coinTraces }           = useTracesByCoin(coinFilter)

  const traces = coinFilter
    ? (coinTraces?.traces ?? [])
    : (allTraces?.traces ?? [])

  const filtered = search
    ? traces.filter(t =>
        t.coin.toLowerCase().includes(search.toLowerCase()) ||
        t.direction.toLowerCase().includes(search.toLowerCase()) ||
        (t.stopped_at ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : traces

  const summary = allTraces?.summary ?? {}
  const topRejections = Object.entries(summary as Record<string, { count: number; pct: number }>)
    .sort(([, a], [, b]) => b.count - a.count)
    .slice(0, 5)

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 w-full rounded-lg border border-border shimmer" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value       = {search}
            onChange    = {e => setSearch(e.target.value)}
            placeholder = "Search coin, direction, reason..."
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
        {coinFilter && (
          <button
            onClick   = {() => setCoinFilter(null)}
            className = "flex items-center gap-1.5 rounded-md border border-border bg-muted px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors"
          >
            {coinFilter}
            <X className="h-3 w-3" />
          </button>
        )}
        <span className="text-xs text-muted-foreground ml-auto">
          {filtered.length} traces
        </span>
      </div>

      {topRejections.length > 0 && !coinFilter && !search && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="label-xs mb-3">Recent Rejection Summary</p>
          <div className="flex flex-wrap gap-2">
            {topRejections.map(([reason, data]) => (
              <span
                key       = {reason}
                className = "inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1 text-xs"
              >
                <span className="text-muted-foreground capitalize">{reason.replace(/_/g, ' ')}</span>
                <span className="font-mono font-semibold text-foreground">{data.pct}%</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {filtered.length === 0 ? (
        <EmptyState
          icon        = {Activity}
          title       = "No traces found"
          description = "Traces appear after each scan cycle"
          compact
        />
      ) : (
        <div className="space-y-2">
          {filtered.slice(0, 50).map((trace, i) => (
            <TraceCard
              key         = {`${trace.coin}-${trace.timestamp}`}
              trace       = {trace}
              defaultOpen = {i === 0 && filtered.length === 1}
            />
          ))}
        </div>
      )}
    </div>
  )
}
