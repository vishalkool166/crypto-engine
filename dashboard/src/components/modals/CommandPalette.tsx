import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  LayoutDashboard, Radio, Activity, BarChart3,
  Users, Coins, Server, ScrollText, Settings,
  User, Tag, Search, ArrowRight, Sparkles, TrendingUp,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'

interface Command {
  id:         string
  label:      string
  description?: string
  icon:       React.ElementType
  action:     () => void
  adminOnly?: boolean
  minTier?:   'free' | 'pro' | 'elite' | 'admin'
  eliteOnly?: boolean
}

interface Props {
  open:    boolean
  onClose: () => void
}

export default function CommandPalette({ open, onClose }: Props) {
  const [query,       setQuery]       = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const navigate                      = useNavigate()
  const { isAdmin, canAccess, hasFeature } = useAuthStore()

  const isElite = hasFeature('api_key_access') || isAdmin

  const go = (path: string) => {
    navigate(path)
    onClose()
    setQuery('')
  }

  const ALL: Command[] = [
    { id: 'home',        label: 'Overview',    description: 'Dashboard overview',       icon: LayoutDashboard, action: () => go('/')            },
    { id: 'signals',     label: 'Signals',     description: 'Signal radar',             icon: Radio,           action: () => go('/signals')     },
    { id: 'trades',      label: 'Trades',      description: 'Live positions',           icon: Activity,        action: () => go('/trades'),      minTier: 'pro'   },
    { id: 'performance', label: 'Performance', description: 'Analytics',                icon: BarChart3,       action: () => go('/performance'), minTier: 'pro'   },
    { id: 'content',     label: 'Content',     description: 'Content generator',        icon: Sparkles,        action: () => go('/content'),     eliteOnly: true  },
    { id: 'india',       label: 'India',       description: 'Indian market ORB signals',    icon: TrendingUp,      action: () => go('/india'),       adminOnly: true  },
    { id: 'users',       label: 'Users',       description: 'User management',          icon: Users,           action: () => go('/users'),       adminOnly: true  },
    { id: 'coins',       label: 'Coins',       description: 'Coin universe',            icon: Coins,           action: () => go('/coins'),       adminOnly: true  },
    { id: 'system',      label: 'System',      description: 'Infrastructure monitor',   icon: Server,          action: () => go('/system'),      adminOnly: true  },
    { id: 'audit',       label: 'Audit',       description: 'Audit log',                icon: ScrollText,      action: () => go('/audit'),       adminOnly: true  },
    { id: 'pricing',     label: 'Pricing',     description: 'Plans and pricing',        icon: Tag,             action: () => go('/pricing')     },
    { id: 'profile',     label: 'Profile',     description: 'Account details',          icon: User,            action: () => go('/profile')     },
    { id: 'settings',    label: 'Settings',    description: 'Preferences and security', icon: Settings,        action: () => go('/settings')    },
  ]

  const visible = ALL.filter(cmd => {
    if (cmd.adminOnly) return isAdmin
    if (cmd.eliteOnly) return isElite
    if (cmd.minTier)   return canAccess(cmd.minTier)
    return true
  })

  const filtered = query.trim()
    ? visible.filter(cmd =>
        cmd.label.toLowerCase().includes(query.toLowerCase()) ||
        cmd.description?.toLowerCase().includes(query.toLowerCase())
      )
    : visible

  useEffect(() => { setActiveIndex(0) }, [query])

  useEffect(() => {
    if (!open) { setQuery(''); setActiveIndex(0) }
  }, [open])

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (!open) return
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex(i => Math.min(i + 1, filtered.length - 1))
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex(i => Math.max(i - 1, 0))
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        filtered[activeIndex]?.action()
      }
    }
    window.addEventListener('keydown', down)
    return () => window.removeEventListener('keydown', down)
  }, [open, filtered, activeIndex])

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial    = {{ opacity: 0 }}
            animate    = {{ opacity: 1 }}
            exit       = {{ opacity: 0 }}
            transition = {{ duration: 0.15 }}
            className  = "fixed inset-0 z-[100] bg-background/80 backdrop-blur-sm"
            onClick    = {onClose}
          />
          <div className="fixed inset-0 z-[101] flex items-start justify-center pt-[18vh] px-4">
            <motion.div
              initial    = {{ opacity: 0, scale: 0.97, y: -8 }}
              animate    = {{ opacity: 1, scale: 1,    y: 0  }}
              exit       = {{ opacity: 0, scale: 0.97, y: -8 }}
              transition = {{ duration: 0.15 }}
              className  = "w-full max-w-md"
            >
              <div className="overflow-hidden rounded-lg border border-border bg-card shadow-2xl">
                <div className="flex items-center gap-3 border-b border-border px-4 py-3">
                  <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <input
                    autoFocus
                    value       = {query}
                    onChange    = {e => setQuery(e.target.value)}
                    placeholder = "Search pages and actions..."
                    className   = "flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
                  />
                  <kbd className="text-[10px] text-muted-foreground/40 border border-border rounded px-1.5 py-0.5">
                    ESC
                  </kbd>
                </div>

                <div className="max-h-72 overflow-y-auto p-1.5">
                  {filtered.length === 0 ? (
                    <div className="flex items-center justify-center py-8">
                      <p className="text-sm text-muted-foreground">No results</p>
                    </div>
                  ) : (
                    filtered.map((cmd, i) => {
                      const Icon = cmd.icon
                      return (
                        <button
                          key           = {cmd.id}
                          onClick       = {cmd.action}
                          onMouseEnter  = {() => setActiveIndex(i)}
                          className     = {cn(
                            'flex w-full items-center gap-3 rounded-md px-3 py-2.5',
                            'text-left transition-colors',
                            i === activeIndex
                              ? 'bg-accent text-foreground'
                              : 'text-foreground hover:bg-accent/50'
                          )}
                        >
                          <div className={cn(
                            'flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border',
                            i === activeIndex ? 'bg-background' : 'bg-muted'
                          )}>
                            <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium">{cmd.label}</p>
                            {cmd.description && (
                              <p className="text-xs text-muted-foreground truncate">
                                {cmd.description}
                              </p>
                            )}
                          </div>
                          {i === activeIndex && (
                            <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          )}
                        </button>
                      )
                    })
                  )}
                </div>

                <div className="border-t border-border px-4 py-2">
                  <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <kbd className="border border-border rounded px-1">↑↓</kbd>
                      Navigate
                    </span>
                    <span className="flex items-center gap-1">
                      <kbd className="border border-border rounded px-1">↵</kbd>
                      Select
                    </span>
                    <span className="flex items-center gap-1">
                      <kbd className="border border-border rounded px-1">ESC</kbd>
                      Close
                    </span>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  )
}
