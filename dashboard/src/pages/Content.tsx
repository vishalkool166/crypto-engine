import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, Copy, Check, RefreshCw, Radio, BarChart3, Lock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import { useSignals } from '@/hooks/useSignals'
import api from '@/lib/api'
import { toast } from 'sonner'

interface GeneratedPost {
  id:        string
  text:      string
  type:      'signal' | 'market'
  coin?:     string
  createdAt: number
}

const STORAGE_KEY = 'se_content_history'

function loadHistory(): GeneratedPost[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveHistory(posts: GeneratedPost[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(posts.slice(0, 10)))
  } catch {}
}

export default function Content() {
  const { hasFeature, isAdmin }         = useAuthStore()
  const { live, watching }              = useSignals()
  const [history,      setHistory]      = useState<GeneratedPost[]>(loadHistory)
  const [generating,   setGenerating]   = useState(false)
  const [mode,         setMode]         = useState<'signal' | 'market'>('market')
  const [selectedCoin, setSelectedCoin] = useState<string>('')
  const [copiedId,     setCopiedId]     = useState<string | null>(null)

  const canUse = hasFeature('api_key_access') || isAdmin

  const availableCoins = [
    ...live.map(i => i.coin),
    ...watching.map(i => i.coin),
  ].filter(Boolean)

  useEffect(() => {
    if (availableCoins.length > 0 && !selectedCoin) {
      setSelectedCoin(availableCoins[0])
    }
  }, [availableCoins.length])

  const handleGenerate = async () => {
    if (generating) return
    setGenerating(true)

    try {
      const endpoint = mode === 'signal' && selectedCoin
        ? `/api/content/generate?coin=${selectedCoin}&type=signal`
        : `/api/content/generate?type=market`

      const res  = await api.post(endpoint)
      const text = res.data?.text ?? res.data?.tweet ?? res.data?.content ?? ''

      if (!text) {
        toast.error('No content generated')
        return
      }

      const post: GeneratedPost = {
        id:        crypto.randomUUID(),
        text,
        type:      mode,
        coin:      mode === 'signal' ? selectedCoin : undefined,
        createdAt: Date.now(),
      }

      const updated = [post, ...history].slice(0, 10)
      setHistory(updated)
      saveHistory(updated)
      toast.success('Generated')

    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? 'Generation failed'
      toast.error(msg)
    } finally {
      setGenerating(false)
    }
  }

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
    toast.success('Copied')
  }

  const handleClear = () => {
    setHistory([])
    saveHistory([])
  }

  if (!canUse) {
    return (
      <div className="p-4 md:p-6">
        <div className="mb-6">
          <h1 className="text-base font-semibold text-foreground">Content Generator</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Generate market commentary on demand
          </p>
        </div>
        <div className="rounded-lg border border-border bg-card p-8 text-center space-y-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-muted mx-auto">
            <Lock className="h-5 w-5 text-muted-foreground" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold text-foreground">
              Elite Plan Required
            </p>
            <p className="text-xs text-muted-foreground max-w-xs mx-auto">
              Generate sharp market commentary and signal tweets on demand.
              One click, one call.
            </p>
          </div>
          <a
            href      = "/pricing"
            className = "inline-flex items-center gap-1.5 rounded-md bg-foreground px-4 py-2 text-xs font-semibold text-background hover:bg-foreground/90 transition-colors"
          >
            View Plans
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-2xl">

      <div>
        <h1 className="text-base font-semibold text-foreground">
          Content Generator
        </h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Generate market commentary on demand. One click, one call.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-6 space-y-5">

        <div className="flex items-center gap-px rounded-md border border-border overflow-hidden w-fit">
          <button
            onClick   = {() => setMode('market')}
            className = {cn(
              'flex items-center gap-1.5 px-4 py-2 text-xs font-medium transition-colors',
              mode === 'market'
                ? 'bg-foreground text-background'
                : 'text-muted-foreground hover:text-foreground bg-background'
            )}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            Market Analysis
          </button>
          <button
            onClick   = {() => setMode('signal')}
            className = {cn(
              'flex items-center gap-1.5 px-4 py-2 text-xs font-medium transition-colors',
              mode === 'signal'
                ? 'bg-foreground text-background'
                : 'text-muted-foreground hover:text-foreground bg-background'
            )}
          >
            <Radio className="h-3.5 w-3.5" />
            Signal Tweet
          </button>
        </div>

        {mode === 'signal' && (
          <div className="space-y-2">
            <p className="label-xs">Select coin</p>
            {availableCoins.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {availableCoins.map(coin => (
                  <button
                    key       = {coin}
                    onClick   = {() => setSelectedCoin(coin)}
                    className = {cn(
                      'rounded-md border px-3 py-1.5 text-xs font-mono font-medium transition-colors',
                      selectedCoin === coin
                        ? 'border-foreground/20 bg-foreground/5 text-foreground'
                        : 'border-border bg-background text-muted-foreground hover:text-foreground hover:bg-accent'
                    )}
                  >
                    {coin}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No active signals or watching coins. Run a scan first.
              </p>
            )}
          </div>
        )}

        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">
            {mode === 'market'
              ? 'Generates witty market commentary based on current conditions.'
              : `Generates a sharp tweet about the ${selectedCoin || '—'} setup.`
            }
          </p>
          <p className="text-xs text-muted-foreground/50">
            Tone: sharp · witty · to the point. No fluff.
          </p>
        </div>

        <button
          onClick   = {handleGenerate}
          disabled  = {generating || (mode === 'signal' && !selectedCoin)}
          className = "flex items-center gap-2 rounded-md bg-foreground px-4 py-2.5 text-sm font-medium text-background hover:bg-foreground/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? (
            <>
              <RefreshCw className="h-4 w-4 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Generate
            </>
          )}
        </button>
      </div>

      {history.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-foreground">
              History
              <span className="ml-2 label-xs">{history.length}</span>
            </p>
            <button
              onClick   = {handleClear}
              className = "text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Clear all
            </button>
          </div>

          <div className="space-y-3">
            <AnimatePresence initial={false}>
              {history.map((post, i) => (
                <motion.div
                  key        = {post.id}
                  initial    = {{ opacity: 0, y: -6 }}
                  animate    = {{ opacity: 1, y: 0  }}
                  exit       = {{ opacity: 0, height: 0 }}
                  transition = {{ delay: i === 0 ? 0 : i * 0.03 }}
                  className  = "rounded-lg border border-border bg-card p-5 space-y-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
                        post.type === 'signal'
                          ? 'border-[hsl(var(--chart-3)/0.2)] bg-[hsl(var(--chart-3)/0.08)] text-[hsl(var(--chart-3))]'
                          : 'border-[hsl(var(--chart-5)/0.2)] bg-[hsl(var(--chart-5)/0.08)] text-[hsl(var(--chart-5))]'
                      )}>
                        {post.type === 'signal' ? `${post.coin} Signal` : 'Market'}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {new Date(post.createdAt).toLocaleTimeString([], {
                          hour:   '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'text-xs font-mono',
                        post.text.length > 270
                          ? 'text-[hsl(var(--chart-2))]'
                          : 'text-muted-foreground'
                      )}>
                        {post.text.length}/280
                      </span>
                      <button
                        onClick   = {() => handleCopy(post.id, post.text)}
                        className = "flex h-7 w-7 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {copiedId === post.id
                          ? <Check className="h-3.5 w-3.5 text-[hsl(var(--chart-1))]" />
                          : <Copy  className="h-3.5 w-3.5" />
                        }
                      </button>
                    </div>
                  </div>

                  <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                    {post.text}
                  </p>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {history.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Sparkles className="h-8 w-8 text-muted-foreground/20 mb-3" />
          <p className="text-sm text-muted-foreground">No posts generated yet</p>
          <p className="text-xs text-muted-foreground/50 mt-1">
            Generated posts appear here. History persists until you clear it.
          </p>
        </div>
      )}

    </div>
  )
}