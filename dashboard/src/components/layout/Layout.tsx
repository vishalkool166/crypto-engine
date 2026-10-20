import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Radio, Activity, User,
  MoreHorizontal, X, BarChart3, Users, TrendingUp,
  Coins, Server, ScrollText, Settings, Tag, Cpu,
} from 'lucide-react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import CommandPalette from '@/components/modals/CommandPalette'
import { useUiStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/lib/utils'

const BOTTOM_NAV = [
  { path: '/',        label: 'Overview', icon: LayoutDashboard                    },
  { path: '/signals', label: 'Signals',  icon: Radio                              },
  { path: '/trades',  label: 'Trades',   icon: Activity,  minTier: 'pro' as const },
  { path: '/profile', label: 'Profile',  icon: User                               },
]

const MORE_ITEMS = [
  { path: '/performance', label: 'Performance', icon: BarChart3,  minTier: 'pro' as const  },
  { path: '/engine',      label: 'Engine',      icon: Cpu,        adminOnly: true          },
  { path: '/india',       label: 'India',       icon: TrendingUp, adminOnly: true          },
  { path: '/users',       label: 'Users',       icon: Users,      adminOnly: true          },
  { path: '/coins',       label: 'Coins',       icon: Coins,      adminOnly: true          },
  { path: '/system',      label: 'System',      icon: Server,     adminOnly: true          },
  { path: '/audit',       label: 'Audit',       icon: ScrollText, adminOnly: true          },
  { path: '/pricing',     label: 'Pricing',     icon: Tag                                  },
  { path: '/settings',    label: 'Settings',    icon: Settings                             },
]

export default function Layout() {
  const { commandPaletteOpen, setCommandPaletteOpen } = useUiStore()
  const { isAdmin, canAccess }                         = useAuthStore()
  const [moreOpen, setMoreOpen]                       = useState(false)
  const location                                      = useLocation()
  const navigate                                      = useNavigate()

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCommandPaletteOpen(true)
      }
      if (e.key === 'Escape') {
        setCommandPaletteOpen(false)
        setMoreOpen(false)
      }
    }
    window.addEventListener('keydown', down)
    return () => window.removeEventListener('keydown', down)
  }, [])

  useEffect(() => {
    setMoreOpen(false)
  }, [location.pathname])

  const visibleMore = MORE_ITEMS.filter(item => {
    if (item.adminOnly) return isAdmin
    if (item.minTier)   return canAccess(item.minTier)
    return true
  })

  const isMoreActive = visibleMore.some(item => location.pathname === item.path)

  return (
    <div className="app-shell flex h-dvh w-full overflow-hidden bg-background">
      <div className="hidden md:flex shrink-0">
        <Sidebar />
      </div>

      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <TopBar />
        <main className="app-main flex-1 overflow-y-auto pb-20 md:pb-0">
          <motion.div
            key        = {location.pathname}
            initial    = {{ opacity: 0, y: 6 }}
            animate    = {{ opacity: 1, y: 0 }}
            transition = {{ duration: 0.2, ease: 'easeOut' }}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>

      <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden border-t border-border bg-background/95 backdrop-blur-sm">
        <div className="flex items-center justify-around px-2 py-1 pb-safe">
          {BOTTOM_NAV.map(item => {
            if (item.minTier && !canAccess(item.minTier)) return null
            const Icon     = item.icon
            const isActive = item.path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(item.path)

            return (
              <button
                key       = {item.path}
                onClick   = {() => navigate(item.path)}
                className = {cn(
                  'flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg min-w-[56px] transition-colors',
                  isActive ? 'text-foreground' : 'text-muted-foreground'
                )}
              >
                <Icon className="h-5 w-5" />
                <span className={cn('text-[10px] font-medium', isActive ? 'text-foreground' : 'text-muted-foreground')}>
                  {item.label}
                </span>
                {isActive && (
                  <motion.div
                    layoutId   = "bottomIndicator"
                    className  = "absolute bottom-1 h-0.5 w-4 rounded-full bg-foreground"
                    transition = {{ type: 'spring', stiffness: 400, damping: 30 }}
                  />
                )}
              </button>
            )
          })}

          <button
            onClick   = {() => setMoreOpen(true)}
            className = {cn(
              'flex flex-col items-center gap-0.5 px-3 py-2 rounded-lg min-w-[56px] transition-colors',
              isMoreActive ? 'text-foreground' : 'text-muted-foreground'
            )}
          >
            <MoreHorizontal className="h-5 w-5" />
            <span className="text-[10px] font-medium">More</span>
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {moreOpen && (
          <>
            <motion.div
              initial    = {{ opacity: 0 }}
              animate    = {{ opacity: 1 }}
              exit       = {{ opacity: 0 }}
              transition = {{ duration: 0.15 }}
              className  = "fixed inset-0 z-50 bg-background/60 backdrop-blur-sm md:hidden"
              onClick    = {() => setMoreOpen(false)}
            />
            <motion.div
              initial    = {{ y: '100%' }}
              animate    = {{ y: 0 }}
              exit       = {{ y: '100%' }}
              transition = {{ type: 'spring', stiffness: 400, damping: 40 }}
              className  = "fixed bottom-0 left-0 right-0 z-50 md:hidden rounded-t-xl border-t border-border bg-card"
            >
              <div className="flex justify-center pt-3 pb-1">
                <div className="h-1 w-10 rounded-full bg-muted-foreground/20" />
              </div>
              <div className="flex items-center justify-between px-4 py-2 border-b border-border">
                <p className="text-sm font-semibold text-foreground">More</p>
                <button
                  onClick   = {() => setMoreOpen(false)}
                  className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="grid grid-cols-4 gap-1 p-3 pb-safe">
                {visibleMore.map(item => {
                  const Icon     = item.icon
                  const isActive = location.pathname === item.path
                  return (
                    <button
                      key       = {item.path}
                      onClick   = {() => navigate(item.path)}
                      className = {cn(
                        'flex flex-col items-center gap-1.5 rounded-xl p-3 transition-colors',
                        isActive
                          ? 'bg-accent text-foreground'
                          : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
                      )}
                    >
                      <Icon className="h-5 w-5" />
                      <span className="text-[10px] font-medium text-center leading-tight">{item.label}</span>
                    </button>
                  )
                })}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <CommandPalette
        open    = {commandPaletteOpen}
        onClose = {() => setCommandPaletteOpen(false)}
      />
    </div>
  )
}


