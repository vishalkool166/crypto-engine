import { useEffect, useState } from 'react'
import { useTheme } from 'next-themes'
import { Sun, Moon, Wifi, WifiOff, Search, ChevronRight } from 'lucide-react'
import { cn, formatPercent } from '@/lib/utils'
import { useWsStore } from '@/stores/wsStore'
import { useUiStore } from '@/stores/uiStore'
import { useDemoStore } from '@/demo/demoStore'
import { mockTicker, mockSummary } from '@/demo/mockData'
import { useScanStatus } from '@/hooks/useHealth'
import { getSessionConfig } from '@/lib/tokens'

function getSession(): string {
  const h = new Date().getUTCHours() + new Date().getUTCMinutes() / 60
  const day = new Date().getUTCDay()
  if (day === 0 || day === 6) return 'Weekend'
  if (h >= 13 && h < 17) return 'London / New York'
  if (h >= 17 && h < 21) return 'New York'
  if (h >= 8 && h < 13) return 'London'
  return 'Asia'
}

function useSession() {
  const [session, setSession] = useState(getSession)
  useEffect(() => {
    const id = window.setInterval(() => setSession(getSession()), 60_000)
    return () => window.clearInterval(id)
  }, [])
  return session
}

export default function TopBar() {
  const { theme, setTheme } = useTheme()
  const { isDemoMode } = useDemoStore()
  const { setCommandPaletteOpen } = useUiStore()
  const session = useSession()
  const sessionCfg = getSessionConfig(session)
  const realWs = useWsStore()
  const status = isDemoMode ? 'connected' : realWs.status
  const ticker = isDemoMode ? mockTicker : realWs.ticker
  const summary = isDemoMode ? mockSummary : realWs.summary
  const { countdown } = useScanStatus()
  const isConnected = status === 'connected'
  const isLive = summary?.mode === 'live'

  return <header className="app-topbar shrink-0 border-b border-border bg-background/95 backdrop-blur">
    <div className="flex min-h-[62px] items-center justify-between gap-4 px-4 md:px-6">
      <div className="min-w-0">
        <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">{isDemoMode ? 'Interactive demo' : 'Signal Engine workspace'}</p>
      </div>

      <div className="hidden min-w-0 flex-1 items-center justify-center gap-6 xl:flex">
        <button onClick={() => setCommandPaletteOpen(true)} className="flex h-8 w-52 shrink-0 items-center gap-2 rounded-md border border-border bg-muted/30 px-3 text-xs text-muted-foreground transition-colors hover:bg-muted/60" aria-label="Search pages and actions">
          <Search className="h-3.5 w-3.5" /><span>Search workspace</span><kbd className="ml-auto rounded border border-border px-1 py-px text-[9px]">⌘K</kbd>
        </button>
        {ticker.length > 0 && <div className="flex min-w-0 items-center gap-5 overflow-x-auto scrollbar-none" aria-label="Market ticker">
          {ticker.slice(0, 5).map(item => <div key={item.coin} className="flex shrink-0 items-center gap-1.5 text-[11px]">
            <span className="font-mono font-semibold">{item.coin}</span>
            <span className="font-mono text-muted-foreground">{item.price >= 1000 ? item.price.toLocaleString(undefined, { maximumFractionDigits: 0 }) : item.price >= 1 ? item.price.toFixed(2) : item.price.toFixed(4)}</span>
            <span className={cn('font-mono', item.change >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')}>{formatPercent(item.change)}</span>
          </div>)}
        </div>}
      </div>

      <div className="flex shrink-0 items-center gap-2 md:gap-3">
        <button onClick={() => setCommandPaletteOpen(true)} aria-label="Search pages and actions" className="icon-button h-8 w-8 xl:hidden"><Search className="h-4 w-4" /></button>
        <div className="hidden items-center gap-2 text-[11px] lg:flex">
          <span className={cn('h-1.5 w-1.5 rounded-full', sessionCfg.dot)} />
          <span className={cn('font-medium', sessionCfg.text)}>{session}</span>
          <ChevronRight className="h-3 w-3 text-muted-foreground/50" />
          <span className="text-muted-foreground">Scan {countdown}</span>
        </div>
        <span className={cn('status-pill', isLive ? 'status-live' : 'status-paper')}><span />{isLive ? 'Live' : 'Paper'}</span>
        {!isDemoMode && <span className="connection-indicator" aria-label={isConnected ? 'Market data connected' : 'Market data disconnected'} title={isConnected ? 'Market data connected' : 'Market data disconnected'}>
          {isConnected ? <Wifi className="h-3.5 w-3.5 text-[hsl(var(--chart-1))]" /> : <WifiOff className="h-3.5 w-3.5 text-muted-foreground" />}
        </span>}
        <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label={theme === 'dark' ? 'Use light theme' : 'Use dark theme'} className="icon-button h-8 w-8">
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </div>

    {ticker.length > 0 && <div className="flex items-center gap-5 overflow-x-auto border-t border-border/70 px-4 py-2 scrollbar-none md:hidden">
      {ticker.map(item => <div key={item.coin} className="flex shrink-0 items-center gap-1.5 text-[10px]">
        <span className="font-mono font-semibold">{item.coin}</span><span className="font-mono text-muted-foreground">{item.price >= 1000 ? item.price.toLocaleString(undefined, { maximumFractionDigits: 0 }) : item.price >= 1 ? item.price.toFixed(2) : item.price.toFixed(4)}</span><span className={cn('font-mono', item.change >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]')}>{formatPercent(item.change)}</span>
      </div>)}
    </div>}
  </header>
}
