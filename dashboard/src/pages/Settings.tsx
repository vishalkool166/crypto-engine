import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, Key, Monitor, RefreshCw, Copy, Check, X } from 'lucide-react'
import { useTheme } from 'next-themes'
import { meApi } from '@/lib/endpoints'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { PageSkeleton } from '@/components/ui/LoadingSkeleton'
import { formatTimeAgo } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import type { UserSession, ApiKey } from '@/types'

export default function Settings() {
  const { theme, setTheme }         = useTheme()
  const { hasFeature, isAdmin }     = useAuthStore()
  const { isDemoMode }              = useDemoStore()
  const queryClient                 = useQueryClient()
  const [copied,     setCopied]     = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [createdKey, setCreatedKey] = useState<string | null>(null)

  const { data: meData, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn:  () => meApi.get().then(r => r.data),
    enabled:  !isDemoMode,
  })

  const revokeSession = useMutation({
    mutationFn: (sid: string) => meApi.revokeSession(sid),
    onSuccess:  () => {
      toast.success('Session revoked')
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
    onError: () => toast.error('Failed to revoke session'),
  })

  const revokeAll = useMutation({
    mutationFn: () => meApi.revokeAllSessions(),
    onSuccess:  () => {
      toast.success('All other sessions revoked')
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
    onError: () => toast.error('Failed to revoke sessions'),
  })

  const createKey = useMutation({
    mutationFn: (name: string) => meApi.createApiKey(name),
    onSuccess:  (data) => {
      setCreatedKey(data.data.key)
      setNewKeyName('')
      queryClient.invalidateQueries({ queryKey: ['me'] })
      toast.success('API key created')
    },
    onError: () => toast.error('Failed to create key'),
  })

  const deleteKey = useMutation({
    mutationFn: (id: number) => meApi.deleteApiKey(id),
    onSuccess:  () => {
      toast.success('Key revoked')
      queryClient.invalidateQueries({ queryKey: ['me'] })
    },
    onError: () => toast.error('Failed to revoke key'),
  })

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    toast.success('Copied to clipboard')
  }

  if (isLoading && !isDemoMode) return <PageSkeleton />

  const sessions: UserSession[] = meData?.sessions  ?? []
  const apiKeys:  ApiKey[]      = meData?.api_keys  ?? []
  const canUseApiKeys           = hasFeature('api_key_access') || isAdmin

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-2xl">

      <div>
        <h1 className="text-base font-semibold text-foreground">Settings</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {isDemoMode ? 'Demo — preferences preview' : 'Preferences and security'}
        </p>
      </div>

      <Card title="Appearance" icon={Monitor}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Theme</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Choose your color scheme
            </p>
          </div>
          <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
            {(['light', 'dark'] as const).map(t => (
              <button
                key       = {t}
                onClick   = {() => setTheme(t)}
                className = {cn(
                  'px-4 py-1.5 text-xs font-medium capitalize transition-colors',
                  theme === t
                    ? 'bg-foreground text-background'
                    : 'text-muted-foreground hover:text-foreground bg-background'
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <Card title="Authentication" icon={Shield}>
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-md border border-border bg-background px-4 py-3">
            <div>
              <p className="text-sm font-medium text-foreground">
                {isDemoMode ? 'Demo Account' : 'Google OAuth'}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {isDemoMode
                  ? 'demo@signalengine.app'
                  : (meData?.email ?? '—')
                }
              </p>
            </div>
            <span className={cn(
              'text-xs font-medium',
              isDemoMode
                ? 'text-[hsl(var(--chart-4))]'
                : 'text-[hsl(var(--chart-1))]'
            )}>
              {isDemoMode ? 'Demo' : 'Connected'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {isDemoMode
              ? 'Sign up with Google to get a real account and access live signals.'
              : 'Authentication is managed via Google. Your account is secured by your Google credentials.'
            }
          </p>
          {isDemoMode && (
            <a
              href      = "/login"
              className = "inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-2 text-xs font-medium text-background hover:bg-foreground/90 transition-colors"
            >
              Sign Up with Google
            </a>
          )}
        </div>
      </Card>

      {!isDemoMode && (
        <Card title="Active Sessions" icon={Monitor}>
          <div className="space-y-3">
            {sessions.length === 0 ? (
              <p className="text-xs text-muted-foreground">No active sessions</p>
            ) : (
              <>
                <div className="space-y-2">
                  {sessions.map(s => (
                    <div
                      key       = {s.id}
                      className = "flex items-center justify-between rounded-md border border-border bg-background px-4 py-3"
                    >
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-foreground">
                          {s.device ?? 'Unknown'} · {s.browser ?? 'Unknown'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {s.ip ?? '—'} · Last active {formatTimeAgo(s.last_active)}
                        </p>
                      </div>
                      <button
                        onClick   = {() => revokeSession.mutate(s.session_id)}
                        disabled  = {revokeSession.isPending}
                        className = "ml-4 shrink-0 text-xs text-[hsl(var(--chart-2))] hover:text-[hsl(var(--chart-2)/0.8)] transition-colors disabled:opacity-50"
                      >
                        Revoke
                      </button>
                    </div>
                  ))}
                </div>
                {sessions.length > 1 && (
                  <button
                    onClick   = {() => revokeAll.mutate()}
                    disabled  = {revokeAll.isPending}
                    className = "w-full rounded-md border border-[hsl(var(--chart-2)/0.2)] bg-[hsl(var(--chart-2)/0.06)] px-4 py-2.5 text-xs font-medium text-[hsl(var(--chart-2))] hover:bg-[hsl(var(--chart-2)/0.12)] transition-colors disabled:opacity-50"
                  >
                    {revokeAll.isPending ? (
                      <span className="flex items-center justify-center gap-2">
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        Revoking...
                      </span>
                    ) : 'Revoke All Other Sessions'}
                  </button>
                )}
              </>
            )}
          </div>
        </Card>
      )}

      <Card title="API Keys" icon={Key}>
        {!canUseApiKeys ? (
          <div className="rounded-md border border-border bg-muted/30 p-5 text-center space-y-2">
            <p className="text-sm font-medium text-foreground">
              API keys require Elite plan
            </p>
            <p className="text-xs text-muted-foreground">
              Upgrade to generate keys for programmatic access
            </p>
            <a
              href      = {isDemoMode ? '/demo/pricing' : '/pricing'}
              className = "inline-flex items-center gap-1 text-xs font-medium text-foreground hover:text-muted-foreground transition-colors"
            >
              View Plans
            </a>
          </div>
        ) : isDemoMode ? (
          <div className="space-y-4">
            <div className="rounded-md border border-border bg-background px-4 py-3">
              <p className="text-xs font-medium text-foreground">
                demo_key_preview
              </p>
              <p className="text-xs font-mono text-muted-foreground mt-0.5">
                se_demo...
                <span className="ml-2 not-italic font-sans">
                  Demo key — not real
                </span>
              </p>
            </div>
            <p className="text-xs text-muted-foreground">
              Sign up to generate real API keys for programmatic access.
            </p>
            <a
              href      = "/login"
              className = "inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-2 text-xs font-medium text-background hover:bg-foreground/90 transition-colors"
            >
              Get Real Access
            </a>
          </div>
        ) : (
          <div className="space-y-4">
            <AnimatePresence>
              {createdKey && (
                <motion.div
                  initial    = {{ opacity: 0, y: -4 }}
                  animate    = {{ opacity: 1, y: 0  }}
                  exit       = {{ opacity: 0 }}
                  className  = "rounded-md border border-[hsl(var(--chart-1)/0.2)] bg-[hsl(var(--chart-1)/0.06)] p-4 space-y-2"
                >
                  <p className="text-xs font-medium text-[hsl(var(--chart-1))]">
                    Key created — copy it now, it will not be shown again
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 rounded-md bg-background border border-border px-3 py-2 text-xs font-mono text-foreground truncate">
                      {createdKey}
                    </code>
                    <button
                      onClick   = {() => handleCopy(createdKey)}
                      className = "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {copied
                        ? <Check className="h-3.5 w-3.5 text-[hsl(var(--chart-1))]" />
                        : <Copy  className="h-3.5 w-3.5" />
                      }
                    </button>
                    <button
                      onClick   = {() => setCreatedKey(null)}
                      className = "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {apiKeys.length > 0 && (
              <div className="space-y-2">
                {apiKeys.map(key => (
                  <div
                    key       = {key.id}
                    className = "flex items-center justify-between rounded-md border border-border bg-background px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground">
                        {key.name}
                      </p>
                      <p className="text-xs font-mono text-muted-foreground mt-0.5">
                        {key.prefix}...
                        {key.last_used && (
                          <span className="ml-2 not-italic font-sans">
                            Used {formatTimeAgo(key.last_used)}
                          </span>
                        )}
                      </p>
                    </div>
                    <button
                      onClick   = {() => deleteKey.mutate(key.id)}
                      disabled  = {deleteKey.isPending}
                      className = "ml-4 shrink-0 text-xs text-[hsl(var(--chart-2))] hover:text-[hsl(var(--chart-2)/0.8)] transition-colors disabled:opacity-50"
                    >
                      Revoke
                    </button>
                  </div>
                ))}
              </div>
            )}

            {apiKeys.length < 3 && (
              <div className="flex items-center gap-2">
                <input
                  value       = {newKeyName}
                  onChange    = {e => setNewKeyName(e.target.value)}
                  onKeyDown   = {e => {
                    if (e.key === 'Enter' && newKeyName.trim()) {
                      createKey.mutate(newKeyName.trim())
                    }
                  }}
                  placeholder = "Key name (e.g. Production)"
                  className   = "flex-1 h-9 rounded-md border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:border-foreground/40 transition-colors"
                />
                <button
                  onClick   = {() => newKeyName.trim() && createKey.mutate(newKeyName.trim())}
                  disabled  = {!newKeyName.trim() || createKey.isPending}
                  className = "flex items-center gap-1.5 rounded-md bg-foreground px-3 py-2 text-xs font-medium text-background hover:bg-foreground/90 transition-colors disabled:opacity-50"
                >
                  {createKey.isPending
                    ? <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    : 'Create'
                  }
                </button>
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Maximum 3 active keys. Keys start with{' '}
              <code className="font-mono">se_</code>
            </p>
          </div>
        )}
      </Card>

    </div>
  )
}

function Card({
  title,
  icon: Icon,
  children,
}: {
  title:    string
  icon:     React.ElementType
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center gap-2.5 border-b border-border px-6 py-4">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm font-semibold text-foreground">{title}</p>
      </div>
      <div className="p-6">{children}</div>
    </div>
  )
}