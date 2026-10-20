import { NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Radio, Activity, BarChart3,
  Users, Coins, Server, ScrollText, Settings,
  User, Tag, ChevronLeft, ChevronRight, LogOut,
  TrendingUp, Sparkles, Cpu,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import { useUiStore } from '@/stores/uiStore'
import { useDemoStore } from '@/demo/demoStore'
import { authApi } from '@/lib/endpoints'
import { toast } from 'sonner'
import type { Tier } from '@/types'

interface NavItem {
  label:     string
  path:      string
  icon:      React.ElementType
  adminOnly?: boolean
  minTier?:  Tier
}

const NAV: NavItem[] = [
  { label: 'Overview',    path: '/',            icon: LayoutDashboard                  },
  { label: 'Signals',     path: '/signals',     icon: Radio                            },
  { label: 'Trades',      path: '/trades',      icon: Activity,   minTier: 'pro'       },
  { label: 'Performance', path: '/performance', icon: BarChart3,  minTier: 'pro'       },
  { label: 'Content',     path: '/content',     icon: Sparkles,   minTier: 'elite'     },
  { label: 'Engine',      path: '/engine',      icon: Cpu,        adminOnly: true      },
  { label: 'India',       path: '/india',       icon: TrendingUp, adminOnly: true      },
  { label: 'Users',       path: '/users',       icon: Users,      adminOnly: true      },
  { label: 'Coins',       path: '/coins',       icon: Coins,      adminOnly: true      },
  { label: 'System',      path: '/system',      icon: Server,     adminOnly: true      },
  { label: 'Audit',       path: '/audit',       icon: ScrollText, adminOnly: true      },
]

const BOTTOM: NavItem[] = [
  { label: 'Pricing',  path: '/pricing',  icon: Tag      },
  { label: 'Profile',  path: '/profile',  icon: User     },
  { label: 'Settings', path: '/settings', icon: Settings },
]

const DEMO_TIERS: { label: string; value: Tier }[] = [
  { label: 'Free',  value: 'free'  },
  { label: 'Pro',   value: 'pro'   },
  { label: 'Elite', value: 'elite' },
]

const DEMO_BOTTOM: NavItem[] = [
  { label: 'Pricing',  path: '/demo/pricing',  icon: Tag      },
  { label: 'Profile',  path: '/demo/profile',  icon: User     },
  { label: 'Settings', path: '/demo/settings', icon: Settings },
]

export default function Sidebar() {
  const { isAdmin, canAccess, user, logout } = useAuthStore()
  const { sidebarCollapsed, toggleSidebar }              = useUiStore()
  const { isDemoMode, demoTier, setDemoTier }            = useDemoStore()
  const navigate                                         = useNavigate()

  const navItems = NAV.filter(item => {
    if (item.adminOnly) return isAdmin && !isDemoMode
    if (item.minTier)   return canAccess(item.minTier)
    return true
  }).map(item => isDemoMode
    ? { ...item, path: item.path === '/' ? '/demo/home' : `/demo${item.path}` }
    : item
  )

  const bottomItems = isDemoMode ? DEMO_BOTTOM : BOTTOM

  const handleLogout = async () => {
    if (isDemoMode) { navigate('/login', { replace: true }); return }
    try {
      await authApi.logout()
    } catch {
      // Clear the local session even when the backend logout endpoint is unavailable.
    }
    logout()
    navigate('/login', { replace: true })
    toast.success('Signed out')
  }

  const displayEmail = isDemoMode ? `demo-${demoTier}@signalengine.app` : user?.email ?? ''
  const displayTier  = isDemoMode ? demoTier : user?.tier ?? 'free'

  return (
    <>
      <motion.aside
        animate    = {{ width: sidebarCollapsed ? 56 : 220 }}
        transition = {{ duration: 0.2, ease: 'easeInOut' }}
        className  = "relative flex h-screen flex-col border-r border-border bg-sidebar overflow-hidden"
      >
        <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-3 shrink-0">
          <AnimatePresence mode="wait">
            {!sidebarCollapsed && (
              <motion.div
                initial    = {{ opacity: 0, x: -8 }}
                animate    = {{ opacity: 1, x: 0  }}
                exit       = {{ opacity: 0, x: -8 }}
                transition = {{ duration: 0.15 }}
                className  = "flex items-center gap-2.5 overflow-hidden"
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-foreground">
                  <TrendingUp className="h-3.5 w-3.5 text-background" />
                </div>
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-sm font-semibold text-sidebar-foreground truncate">Signal Engine</span>
                  {isDemoMode && (
                    <span className="inline-flex items-center rounded-full bg-[hsl(var(--chart-4)/0.15)] px-1.5 py-px text-[10px] font-medium text-[hsl(var(--chart-4))] shrink-0">
                      Demo
                    </span>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {sidebarCollapsed && (
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-foreground mx-auto">
              <TrendingUp className="h-3.5 w-3.5 text-background" />
            </div>
          )}

          {!sidebarCollapsed && (
            <button
              onClick   = {toggleSidebar}
              aria-label = "Collapse sidebar"
              className = "flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-sidebar-foreground/40 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors"
            >
              <ChevronLeft className="h-3 w-3" />
            </button>
          )}
        </div>

        <nav className="flex flex-1 flex-col gap-px overflow-y-auto p-2 scrollbar-none">
          {navItems.map((item, index) => {
            const previousAdmin = index > 0 && navItems[index - 1].adminOnly
            const sectionStart = index === 0 || (!previousAdmin && item.adminOnly)
            return (
              <div key={item.path}>
                {sectionStart && !sidebarCollapsed && (
                  <p className="px-3 pt-4 pb-2 text-[10px] tracking-[0.16em] uppercase font-semibold text-sidebar-foreground/45">
                    {item.adminOnly ? 'Administration' : 'Workspace'}
                  </p>
                )}
                {sectionStart && sidebarCollapsed && index > 0 && <div className="my-2 border-t border-sidebar-border" />}
                <SidebarLink item={item} collapsed={sidebarCollapsed} />
              </div>
            )
          })}
        </nav>

        <div className="border-t border-sidebar-border p-2 space-y-px shrink-0">
          {isDemoMode && !sidebarCollapsed && (
            <div className="px-2 py-2 mb-1">
              <p className="text-[10px] text-sidebar-foreground/40 mb-1.5 uppercase tracking-wide">Demo Tier</p>
              <div className="flex items-center gap-px rounded-md border border-sidebar-border overflow-hidden">
                {DEMO_TIERS.map(t => (
                  <button
                    key       = {t.value}
                    onClick   = {() => setDemoTier(t.value)}
                    className = {cn(
                      'flex-1 py-1 text-[10px] font-medium transition-colors',
                      demoTier === t.value
                        ? 'bg-foreground text-background'
                        : 'text-sidebar-foreground/50 hover:text-sidebar-foreground bg-transparent'
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {bottomItems.map(item => (
            <SidebarLink key={item.path} item={item} collapsed={sidebarCollapsed} />
          ))}

          <button
            onClick   = {handleLogout}
            aria-label = {sidebarCollapsed ? (isDemoMode ? 'Exit demo' : 'Sign out') : undefined}
            className = {cn(
              'flex h-9 w-full items-center gap-3 rounded-md px-2.5',
              'text-sm text-sidebar-foreground/50 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-colors',
              sidebarCollapsed && 'justify-center px-0'
            )}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            <AnimatePresence mode="wait">
              {!sidebarCollapsed && (
                <motion.span
                  initial    = {{ opacity: 0 }}
                  animate    = {{ opacity: 1 }}
                  exit       = {{ opacity: 0 }}
                  transition = {{ duration: 0.1 }}
                  className  = "truncate text-sm"
                >
                  {isDemoMode ? 'Exit Demo' : 'Sign out'}
                </motion.span>
              )}
            </AnimatePresence>
          </button>

          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.div
                initial    = {{ opacity: 0 }}
                animate    = {{ opacity: 1 }}
                exit       = {{ opacity: 0 }}
                transition = {{ duration: 0.15 }}
                className  = "mt-1 border-t border-sidebar-border pt-2 px-1"
              >
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sidebar-accent text-xs font-semibold text-sidebar-foreground">
                    {displayEmail.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-sidebar-foreground leading-none">{displayEmail}</p>
                    <p className="text-[10px] text-sidebar-foreground/40 mt-0.5 capitalize">
                      {displayTier}{isDemoMode && ' · demo'}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.aside>

      {sidebarCollapsed && (
        <button
          onClick   = {toggleSidebar}
          aria-label = "Expand sidebar"
          className = "fixed left-[44px] top-4 z-50 flex h-6 w-6 items-center justify-center rounded-md border border-border bg-background text-muted-foreground hover:bg-accent hover:text-foreground transition-colors shadow-sm"
        >
          <ChevronRight className="h-3 w-3" />
        </button>
      )}
    </>
  )
}

function SidebarLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const Icon = item.icon
  return (
    <NavLink
      to        = {item.path}
      end       = {item.path === '/' || item.path === '/demo/home'}
      aria-label = {item.label}
      title      = {collapsed ? item.label : undefined}
      className = {({ isActive }) => cn(
        'flex h-9 w-full items-center gap-3 rounded-md px-2.5 text-sm transition-colors',
        isActive
          ? 'bg-sidebar-accent text-sidebar-foreground font-medium'
          : 'text-sidebar-foreground/60 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
        collapsed && 'justify-center px-0'
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <AnimatePresence mode="wait">
        {!collapsed && (
          <motion.span
            initial    = {{ opacity: 0 }}
            animate    = {{ opacity: 1 }}
            exit       = {{ opacity: 0 }}
            transition = {{ duration: 0.1 }}
            className  = "truncate"
          >
            {item.label}
          </motion.span>
        )}
      </AnimatePresence>
    </NavLink>
  )
}
