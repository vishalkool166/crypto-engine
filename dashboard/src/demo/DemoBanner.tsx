import { useNavigate } from 'react-router-dom'
import { Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { useDemoStore } from '@/demo/demoStore'
import { getTierConfig } from '@/lib/tokens'

export default function DemoBanner() {
  const { demoTier }    = useDemoStore()
  const navigate        = useNavigate()
  const [dismissed, setDismissed] = useState(false)
  const tierCfg         = getTierConfig(demoTier)

  if (dismissed) return null

  return (
    <div className={cn(
      'relative z-50 flex items-center justify-between gap-3',
      'border-b border-border bg-card px-4 py-2.5',
    )}>
      <div className="flex items-center gap-2.5 min-w-0">
        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-muted">
          <Sparkles className="h-3 w-3 text-muted-foreground" />
        </div>
        <p className="text-xs text-muted-foreground truncate">
          You are viewing a demo on{' '}
          <span className={cn('font-semibold', tierCfg.text)}>
            {tierCfg.label} tier
          </span>
          {' '}— data is simulated
        </p>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick   = {() => navigate('/login')}
          className = {cn(
            'rounded-md bg-foreground px-3 py-1.5',
            'text-xs font-semibold text-background',
            'hover:bg-foreground/90 transition-colors'
          )}
        >
          Get Real Signals
        </button>
        <button
          onClick   = {() => setDismissed(true)}
          className = "flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}