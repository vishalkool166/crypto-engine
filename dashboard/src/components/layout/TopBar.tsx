import { useEffect, useRef, useState } from 'react'
import { useTheme } from 'next-themes'
import { Sun, Moon, Wifi, WifiOff } from 'lucide-react'
import { cn, formatPercent } from '@/lib/utils'
import { useWsStore } from '@/stores/wsStore'
import { useUiStore } from '@/stores/uiStore'
import { useDemoStore } from '@/demo/demoStore'
import { mockTicker, mockSummary } from '@/demo/mockData'
import { useScanStatus } from '@/hooks/useHealth'
import { getSessionConfig } from '@/lib/tokens'

const SPEED = 35

function useSession() {
  const [session, setSession] = useState(() => getSession())
  useEffect(() => {
    const id = setInterval(() => setSession(getSession()), 60_000)
    return () => clearInterval(id)
  }, [])
  return session
}

function getSession(): string {
  const h   = new Date().getUTCHours() + new Date().getUTCMinutes() / 60
  const day = new Date().getUTCDay()
  if (day === 0 || day === 6)   return 'Weekend'
  if (h >= 13 && h < 17)        return 'London/NY Overlap'
  if (h >= 17 && h < 21)        return 'New York'
  if (h >= 8  && h < 13)        return 'London'
  return 'Asia'
}

export default function TopBar() {
  const { theme, setTheme }       = useTheme()
  const { isDemoMode }            = useDemoStore()
  const { setCommandPaletteOpen } = useUiStore()
  const session                   = useSession()
  const [, setFreshnessClock]     = useState(Date.now())
  const sessionCfg                = getSessionConfig(session)

  const realWs    = useWsStore()
  const status    = isDemoMode ? 'connected' : realWs.status
  const ticker    = isDemoMode ? mockTicker  : realWs.ticker
  const summary   = isDemoMode ? mockSummary : realWs.summary

  const { countdown } = useScanStatus()

  const isConnected = status === 'connected'
  const isStale = !isDemoMode && isConnected && realWs.lastUpdated !== null && Date.now() - realWs.lastUpdated > 60_000
  const connectionLabel = isStale ? 'Connection active · data is stale' : isConnected && realWs.lastUpdated === null ? 'Connected · awaiting data' : isConnected ? 'Connection active' : `Connection ${status}`
  const isLive      = summary?.mode === 'live'
  const hasTickerItems = ticker.length > 0

  const tickerRef   = useRef<HTMLDivElement>(null)
  const animRef     = useRef<number | null>(null)
  const offsetRef   = useRef(0)
  const lastTimeRef = useRef(0)
  const startedRef  = useRef(false)

  useEffect(() => {
    const timer = window.setInterval(() => setFreshnessClock(Date.now()), 15_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!hasTickerItems || startedRef.current) return
    if (!tickerRef.current) return
    startedRef.current = true

    const step = (ts: number) => {
      if (!lastTimeRef.current) lastTimeRef.current = ts
      const delta = ts - lastTimeRef.current
      lastTimeRef.current = ts

      if (!tickerRef.current) return
      const total = tickerRef.current.scrollWidth / 2
      if (total > 0) {
        offsetRef.current = (offsetRef.current + (SPEED * delta) / 1000) % total
        tickerRef.current.style.transform = `translateX(-${offsetRef.current}px)`
      }
      animRef.current = requestAnimationFrame(step)
    }

    animRef.current = requestAnimationFrame(step)

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
      startedRef.current  = false
      lastTimeRef.current = 0
    }
  }, [hasTickerItems])

  return (
    <header className="shrink-0 border-b border-border bg-background">
      <div className="flex h-14 items-center justify-between px-4 md:px-6 gap-4">

        <div className="flex items-center gap-4 min-w-0 flex-1">
          <button
            onClick   = {() => setCommandPaletteOpen(true)}
            className = {cn(
              'hidden md:flex h-8 w-52 shrink-0 items-center gap-2 rounded-md border border-border',
              'bg-muted/40 px-3 text-xs text-muted-foreground hover:bg-muted transition-colors'
            )}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <span>Search</span>
            <kbd className="ml-auto text-[10px] text-muted-foreground/40 border border-border rounded px-1 py-px">⌘K</kbd>
          </button>

          {ticker.length > 0 && (
            <div className="hidden md:block overflow-hidden flex-1">
              <div
                ref       = {tickerRef}
                className = "flex items-center gap-8 whitespace-nowrap will-change-transform"
                style     = {{ width: 'max-content' }}
              >
                {[...ticker, ...ticker].map((item, i) => (
                  <div key={i} className="flex items-center gap-2 shrink-0">
                    <span className="text-xs font-mono font-medium text-foreground">{item.coin}</span>
                    <span className="text-xs font-mono text-muted-foreground">
                      {item.price >= 1000
                        ? item.price.toLocaleString(undefined, { maximumFractionDigits: 0 })
                        : item.price >= 1
                        ? (item.price ?? 0).toFixed(2)
                        : (item.price ?? 0).toFixed(4)
                      }
                    </span>
                    <span className={cn(
                      'text-xs font-mono',
                      item.change >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
                    )}>
                      {formatPercent(item.change)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden lg:flex items-center gap-2 text-xs">
            <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', sessionCfg.dot)} />
            <span className={cn('font-medium', sessionCfg.text)}>{session}</span>
            <span className="text-muted-foreground/40">·</span>
            <span className="text-muted-foreground">{sessionCfg.quality}</span>
          </div>

          <div className="hidden lg:flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>Scan</span>
            <span className="font-mono font-medium text-foreground">{countdown}</span>
          </div>

          <div className={cn(
            'flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium',
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

          {!isDemoMode && (
            <div className="flex items-center gap-1.5" role="status" aria-live="polite" aria-label={connectionLabel}>
              {isConnected && !isStale
                ? <Wifi className="h-3.5 w-3.5 text-[hsl(var(--chart-1))]" aria-hidden="true" />
                : <WifiOff className={cn('h-3.5 w-3.5', isStale ? 'text-[hsl(var(--chart-4))]' : 'text-muted-foreground')} aria-hidden="true" />
              }
              <span className="sr-only">{connectionLabel}</span>
            </div>
          )}

          {isDemoMode && (
            <Wifi className="h-3.5 w-3.5 text-[hsl(var(--chart-1))]" />
          )}

          <button
            onClick   = {() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className = "flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {ticker.length > 0 && (
        <div className="md:hidden border-t border-border overflow-x-auto scrollbar-none">
          <div className="flex items-center gap-6 px-4 py-2">
            {ticker.map((item, i) => (
              <div key={i} className="flex items-center gap-1.5 shrink-0">
                <span className="text-xs font-mono font-medium text-foreground">{item.coin}</span>
                <span className="text-xs font-mono text-muted-foreground">
                  {item.price >= 1000
                    ? item.price.toLocaleString(undefined, { maximumFractionDigits: 0 })
                    : item.price >= 1
                    ? (item.price ?? 0).toFixed(2)
                    : (item.price ?? 0).toFixed(4)
                  }
                </span>
                <span className={cn(
                  'text-xs font-mono',
                  item.change >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
                )}>
                  {formatPercent(item.change)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </header>
  )
}
