import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Plus, Search, X, RefreshCw,
  CheckCircle, AlertCircle, ToggleLeft, ToggleRight, Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatTimeAgo, formatPercent, formatPrice } from '@/lib/utils'
import { useCoins, useToggleCoin, useRemoveCoin, useAddCoin } from '@/hooks/useAdmin'
import { coinsApi } from '@/lib/endpoints'
import { useDemoStore } from '@/demo/demoStore'
import EmptyState from '@/components/ui/EmptyState'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import { getStateConfig } from '@/lib/tokens'
import { Coins } from 'lucide-react'
import type { CoinConfig } from '@/types'

export default function CoinsPage() {
  const { isDemoMode }             = useDemoStore()
  const { data: coins, isLoading } = useCoins()
  const toggleMutation             = useToggleCoin()
  const removeMutation             = useRemoveCoin()
  const addMutation                = useAddCoin()

  const [search,     setSearch]     = useState('')
  const [addOpen,    setAddOpen]    = useState(false)
  const [newCoin,    setNewCoin]    = useState('')
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState<{
    valid:   boolean
    reason?: string
    coin?:   string
  } | null>(null)

  if (isLoading) return <PageSkeleton />

  const all      = (coins ?? []) as CoinConfig[]
  const filtered = all.filter(c =>
    search ? c.coin.toLowerCase().includes(search.toLowerCase()) : true
  )
  const enabled  = all.filter(c => c.enabled).length

  const handleValidate = async () => {
    if (!newCoin.trim()) return
    if (isDemoMode) {
      setValidation({ valid: true, coin: newCoin.trim().toUpperCase() })
      return
    }
    setValidating(true)
    setValidation(null)
    try {
      const res = await coinsApi.validate(newCoin.trim().toUpperCase())
      setValidation(res.data)
    } catch {
      setValidation({ valid: false, reason: 'Validation failed' })
    } finally {
      setValidating(false)
    }
  }

  const handleAdd = () => {
    if (!validation?.valid) return
    addMutation.mutate(newCoin.trim().toUpperCase(), {
      onSuccess: () => {
        setAddOpen(false)
        setNewCoin('')
        setValidation(null)
      },
    })
  }

  const handleClose = () => {
    setAddOpen(false)
    setNewCoin('')
    setValidation(null)
  }

  return (
    <div className="p-4 md:p-6 space-y-6">

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-foreground">Coin Universe</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {enabled} active · {all.length - enabled} disabled · {all.length} total
            {isDemoMode && ' · Demo data'}
          </p>
        </div>
        <button
          onClick   = {() => setAddOpen(true)}
          className = "flex items-center gap-2 rounded-md bg-foreground px-3 py-1.5 text-xs font-medium text-background hover:bg-foreground/90 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Coin
        </button>
      </div>

      <div className="relative max-w-xs">
        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          value       = {search}
          onChange    = {e => setSearch(e.target.value)}
          placeholder = "Search coins..."
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

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <table className="w-full">
          <thead className="border-b border-border">
            <tr>
              {['Coin', 'Status', 'State', 'Price', 'Change', 'Source', 'Added', 'Actions'].map(h => (
                <th key={h} className="table-header-cell">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  <EmptyState
                    icon        = {Coins}
                    title       = "No coins found"
                    description = "Add coins to start monitoring"
                    compact
                  />
                </td>
              </tr>
            ) : (
              filtered.map((coin, i) => {
                const stateCfg = getStateConfig(coin.state ?? 'idle')
                return (
                  <motion.tr
                    key        = {coin.coin}
                    initial    = {{ opacity: 0 }}
                    animate    = {{ opacity: 1 }}
                    transition = {{ delay: i * 0.02 }}
                    className  = "table-row"
                  >
                    <td className="table-cell">
                      <span className="font-mono font-semibold text-foreground">{coin.coin}</span>
                    </td>
                    <td className="table-cell">
                      <div className="flex items-center gap-1.5">
                        <span className={cn(
                          'h-1.5 w-1.5 rounded-full',
                          coin.enabled ? 'bg-[hsl(var(--chart-1))]' : 'bg-muted-foreground'
                        )} />
                        <span className={cn(
                          'text-xs font-medium',
                          coin.enabled ? 'text-[hsl(var(--chart-1))]' : 'text-muted-foreground'
                        )}>
                          {coin.enabled ? 'Active' : 'Disabled'}
                        </span>
                      </div>
                    </td>
                    <td className="table-cell">
                      <div className="flex items-center gap-1.5">
                        <span className={cn('h-1.5 w-1.5 rounded-full', stateCfg.dot)} />
                        <span className={cn('text-xs', stateCfg.text)}>{stateCfg.label}</span>
                      </div>
                    </td>
                    <td className="table-cell font-mono text-xs text-foreground">
                      {coin.price > 0 ? formatPrice(coin.price) : '—'}
                    </td>
                    <td className="table-cell">
                      {coin.change !== undefined ? (
                        <span className={cn(
                          'font-mono text-xs',
                          coin.change >= 0 ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
                        )}>
                          {formatPercent(coin.change)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </td>
                    <td className="table-cell text-xs text-muted-foreground capitalize">{coin.source}</td>
                    <td className="table-cell text-xs text-muted-foreground">{formatTimeAgo(coin.added_at)}</td>
                    <td className="table-cell">
                      <div className="flex items-center gap-1">
                        <button
                          onClick   = {() => toggleMutation.mutate({ coin: coin.coin, enabled: !coin.enabled })}
                          disabled  = {toggleMutation.isPending}
                          className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors disabled:opacity-50"
                          title     = {coin.enabled ? 'Disable' : 'Enable'}
                        >
                          {coin.enabled
                            ? <ToggleRight className="h-4 w-4 text-[hsl(var(--chart-1))]" />
                            : <ToggleLeft  className="h-4 w-4" />
                          }
                        </button>
                        <button
                          onClick   = {() => {
                            if (confirm(`Remove ${coin.coin} from universe?`)) {
                              removeMutation.mutate(coin.coin)
                            }
                          }}
                          disabled  = {removeMutation.isPending}
                          className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-[hsl(var(--chart-2)/0.1)] hover:text-[hsl(var(--chart-2))] transition-colors disabled:opacity-50"
                          title     = "Remove"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      <AnimatePresence>
        {addOpen && (
          <>
            <motion.div
              initial    = {{ opacity: 0 }}
              animate    = {{ opacity: 1 }}
              exit       = {{ opacity: 0 }}
              transition = {{ duration: 0.15 }}
              className  = "fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
              onClick    = {handleClose}
            />
            <motion.div
              initial    = {{ opacity: 0, scale: 0.97, y: -8 }}
              animate    = {{ opacity: 1, scale: 1,    y: 0  }}
              exit       = {{ opacity: 0, scale: 0.97, y: -8 }}
              transition = {{ duration: 0.15 }}
              className  = "fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 px-4"
            >
              <div className="overflow-hidden rounded-lg border border-border bg-card shadow-2xl">
                <div className="flex items-center justify-between border-b border-border px-5 py-4">
                  <p className="text-sm font-semibold text-foreground">
                    Add Coin {isDemoMode && '(Demo)'}
                  </p>
                  <button
                    onClick   = {handleClose}
                    className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="p-5 space-y-4">
                  <div className="flex gap-2">
                    <input
                      value       = {newCoin}
                      onChange    = {e => {
                        setNewCoin(e.target.value.toUpperCase())
                        setValidation(null)
                      }}
                      onKeyDown   = {e => e.key === 'Enter' && handleValidate()}
                      placeholder = "BTC"
                      className   = "flex-1 h-9 rounded-md border border-border bg-background px-3 text-sm font-mono text-foreground placeholder:text-muted-foreground outline-none focus:border-foreground/40 transition-colors"
                    />
                    <button
                      onClick   = {handleValidate}
                      disabled  = {!newCoin.trim() || validating}
                      className = "flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-2 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
                    >
                      {validating ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : 'Validate'}
                    </button>
                  </div>

                  <AnimatePresence>
                    {validation && (
                      <motion.div
                        initial    = {{ opacity: 0, y: -4 }}
                        animate    = {{ opacity: 1, y: 0  }}
                        exit       = {{ opacity: 0 }}
                        className  = {cn(
                          'flex items-center gap-2 rounded-md border px-3 py-2.5',
                          validation.valid
                            ? 'border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.06)]'
                            : 'border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)]'
                        )}
                      >
                        {validation.valid
                          ? <CheckCircle className="h-4 w-4 shrink-0 text-[hsl(var(--chart-1))]" />
                          : <AlertCircle className="h-4 w-4 shrink-0 text-[hsl(var(--chart-2))]" />
                        }
                        <p className={cn(
                          'text-xs',
                          validation.valid ? 'text-[hsl(var(--chart-1))]' : 'text-[hsl(var(--chart-2))]'
                        )}>
                          {validation.valid
                            ? isDemoMode
                              ? `${validation.coin} — demo validation passed`
                              : `${validation.coin}/USDT found on Binance Futures`
                            : validation.reason
                          }
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <p className="text-xs text-muted-foreground">
                    {isDemoMode
                      ? 'Demo mode — no real backfill will run.'
                      : 'Adding a coin triggers a historical data backfill. This may take a few minutes.'
                    }
                  </p>
                </div>

                <div className="flex items-center gap-2 border-t border-border px-5 py-4">
                  <button
                    onClick   = {handleClose}
                    className = "flex-1 rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick   = {handleAdd}
                    disabled  = {!validation?.valid || addMutation.isPending}
                    className = "flex-1 rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
                  >
                    {addMutation.isPending ? (
                      <span className="flex items-center justify-center gap-2">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        Adding...
                      </span>
                    ) : isDemoMode ? 'Add (Demo)' : 'Add + Backfill'}
                  </button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

    </div>
  )
}