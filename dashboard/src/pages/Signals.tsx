import { useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSignals } from '@/hooks/useSignals'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { useSignalAccess } from '@/hooks/useSignalAccess'
import { signalsApi } from '@/lib/endpoints'
import SignalRow from '@/components/signals/SignalRow'
import CoinDetailPanel from '@/components/signals/CoinDetailPanel'
import SignalHistoryTable from '@/components/performance/SignalHistoryTable'
import CollapsibleSection from '@/components/ui/CollapsibleSection'
import FilterBar from '@/components/ui/FilterBar'
import SignalCountdown from '@/components/ui/SignalCountdown'
import { toast } from 'sonner'
import type { RadarItem } from '@/types'

const STATE_FILTERS = [
  { label: 'All',      value: 'all'      },
  { label: 'Watching', value: 'watching' },
  { label: 'Idle',     value: 'idle'     },
]

function SignalSection({
  title,
  count,
  items,
  badge,
  subtitle,
  selectedCoin,
  onSelect,
  defaultOpen = false,
}: {
  title:        string
  count:        number
  items:        RadarItem[]
  badge?:       React.ReactNode
  subtitle?:    string
  selectedCoin: string | null
  onSelect:     (coin: string) => void
  defaultOpen?: boolean
}) {
  const { isFree, canSeeSignal } = useSignalAccess()

  if (items.length === 0) return null

  return (
    <CollapsibleSection
      title       = {title}
      count       = {count}
      defaultOpen = {defaultOpen}
      badge       = {badge}
    >
      {subtitle && (
        <div className="px-6 py-2 border-b border-border">
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
      )}
      <div className="divide-y divide-border">
        {items.map((item, i) => {
          const visible = !isFree || canSeeSignal(item.timestamp)
          return (
            <div key={item.coin}>
              {visible ? (
                <>
                  <SignalRow
                    item     = {item}
                    index    = {i}
                    selected = {selectedCoin === item.coin}
                    onSelect = {() => onSelect(selectedCoin === item.coin ? '' : item.coin)}
                  />
                  <CoinDetailPanel
                    coin      = {item.coin}
                    expanded  = {selectedCoin === item.coin}
                    timestamp = {item.timestamp}
                  />
                </>
              ) : (
                <LockedSignalRow item={item} />
              )}
            </div>
          )
        })}
      </div>
    </CollapsibleSection>
  )
}

function LockedSignalRow({ item }: { item: RadarItem }) {
  return (
    <div className="flex items-center justify-between px-6 py-3.5">
      <div className="flex items-center gap-4 min-w-0">
        <span className="font-mono font-semibold text-foreground text-sm w-14 shrink-0">
          {item.coin}
        </span>
        <SignalCountdown timestamp={item.timestamp} />
      </div>
    </div>
  )
}

export default function Signals() {
  const { isDemoMode }                  = useDemoStore()
  const { isAdmin }                     = useAuthStore()
  const { isFree, canSeeSignal }        = useSignalAccess()
  const [scanning,      setScanning]    = useState(false)
  const [selectedCoin,  setSelectedCoin]= useState<string | null>(null)
  const [stateFilter,   setStateFilter] = useState('all')

  const {
    live, watching, idle, all,
    isLoading, refetch, totalWatching,
  } = useSignals()


  const handleScan = async () => {
    if (isDemoMode) { toast.success('Scan triggered (demo)'); return }
    setScanning(true)
    try {
      await signalsApi.scan()
      await refetch()
      toast.success('Scan complete')
    } catch {
      toast.error('Scan failed')
    } finally {
      setScanning(false)
    }
  }

  const handleSelect = (coin: string) => {
    setSelectedCoin(coin || null)
  }

  const filteredAll = stateFilter === 'all'
    ? all
    : stateFilter === 'watching'
    ? watching
    : idle

  const liveSignalBadge = live.length > 0 ? (
    <span className="inline-flex items-center justify-center rounded-full bg-[hsl(var(--chart-1)/0.1)] text-[hsl(var(--chart-1))] text-xs font-medium px-2 py-px">
      {live.length}
    </span>
  ) : undefined

  const watchingBadge = watching.length > 0 ? (
    <span className="inline-flex items-center justify-center rounded-full bg-[hsl(var(--chart-4)/0.1)] text-[hsl(var(--chart-4))] text-xs font-medium px-2 py-px">
      {watching.length}
    </span>
  ) : undefined

  return (
    <div className="p-4 md:p-6 space-y-6">

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-foreground">Signal Intelligence</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {all.length} coins monitored
            {totalWatching > 0 && ` · ${totalWatching} watching`}
          </p>
        </div>
        {(isAdmin || isDemoMode) && (
          <button
            onClick   = {handleScan}
            disabled  = {scanning}
            className = "flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', scanning && 'animate-spin')} />
            Scan Now
          </button>
        )}
      </div>

      <SignalSection
        title        = "Live Signals"
        count        = {live.length}
        items        = {live}
        badge        = {liveSignalBadge}
        selectedCoin = {selectedCoin}
        onSelect     = {handleSelect}
        defaultOpen
      />

      <SignalSection
        title        = "Watching"
        count        = {watching.length}
        items        = {watching}
        badge        = {watchingBadge}
        subtitle     = "Trend confirmed · waiting for entry"
        selectedCoin = {selectedCoin}
        onSelect     = {handleSelect}
        defaultOpen  = {live.length === 0}
      />

      <CollapsibleSection
        title       = "All Coins"
        count       = {all.length}
        defaultOpen = {live.length === 0 && watching.length === 0}
        action      = {
          <FilterBar
            filters   = {STATE_FILTERS}
            active    = {stateFilter}
            onFilter  = {setStateFilter}
            className = "hidden sm:flex"
          />
        }
      >
        <div className="px-6 py-3 border-b border-border sm:hidden">
          <FilterBar
            filters  = {STATE_FILTERS}
            active   = {stateFilter}
            onFilter = {setStateFilter}
          />
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-foreground" />
          </div>
        ) : filteredAll.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center px-6">
            <p className="text-sm font-medium text-foreground">No coins found</p>
            <p className="text-xs text-muted-foreground mt-1">Run a scan to populate signal data</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {filteredAll.map((item, i) => {
              const visible = !isFree || canSeeSignal(item.timestamp)
              return (
                <div key={item.coin}>
                  {visible ? (
                    <>
                      <SignalRow
                        item     = {item}
                        index    = {i}
                        selected = {selectedCoin === item.coin}
                        onSelect = {() => handleSelect(selectedCoin === item.coin ? '' : item.coin)}
                      />
                      <CoinDetailPanel
                        coin      = {item.coin}
                        expanded  = {selectedCoin === item.coin}
                        timestamp = {item.timestamp}
                      />
                    </>
                  ) : (
                    <LockedSignalRow item={item} />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </CollapsibleSection>

      <SignalHistoryTable />

    </div>
  )
}