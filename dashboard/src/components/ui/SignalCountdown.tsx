import { useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSignalAccess } from '@/hooks/useSignalAccess'

interface Props {
  timestamp:  string | number | null | undefined
  className?: string
}

function formatCountdown(ms: number): string {
  if (ms <= 0) return '0m'
  const totalSecs = Math.floor(ms / 1000)
  const h         = Math.floor(totalSecs / 3600)
  const m         = Math.floor((totalSecs % 3600) / 60)
  const s         = totalSecs % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export default function SignalCountdown({ timestamp, className }: Props) {
  const { msUntilVisible } = useSignalAccess()
  const [ms, setMs]        = useState(() => msUntilVisible(timestamp))

  useEffect(() => {
    setMs(msUntilVisible(timestamp))
    const id = setInterval(() => {
      const remaining = msUntilVisible(timestamp)
      setMs(remaining)
      if (remaining <= 0) clearInterval(id)
    }, 1000)
    return () => clearInterval(id)
  }, [timestamp])

  if (ms <= 0) return null

  return (
    <div className={cn('flex flex-col items-start gap-1.5', className)}>
      <div className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/50 px-2.5 py-1.5">
        <Lock className="h-3 w-3 text-muted-foreground shrink-0" />
        <span className="text-xs font-mono font-medium text-foreground">
          Available in {formatCountdown(ms)}
        </span>
      </div>
      <a
        href      = "/pricing"
        className = "text-xs font-medium text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2"
      >
        Upgrade to reveal now
      </a>
    </div>
  )
}