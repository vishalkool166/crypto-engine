import { NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard, Radio, Activity, BarChart3, Users, Coins, Server,
  ScrollText, Settings, User, Tag, ChevronRight, LogOut,
  TrendingUp, Cpu, PanelLeftClose,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import { useUiStore } from '@/stores/uiStore'
import { useDemoStore } from '@/demo/demoStore'
import { authApi } from '@/lib/endpoints'
import { toast } from 'sonner'
import type { Tier } from '@/types'

interface NavItem { label: string; path: string; icon: React.ElementType; adminOnly?: boolean; minTier?: Tier }

const WORKSPACE: NavItem[] = [
  { label: 'Overview', path: '/', icon: LayoutDashboard },
  { label: 'Signals', path: '/signals', icon: Radio },
  { label: 'Trades', path: '/trades', icon: Activity, minTier: 'pro' },
  { label: 'Performance', path: '/performance', icon: BarChart3, minTier: 'pro' },
]
const MARKETS: NavItem[] = [
  { label: 'Coin universe', path: '/coins', icon: Coins, adminOnly: true },
  { label: 'India markets', path: '/india', icon: TrendingUp, adminOnly: true },
]
const OPERATIONS: NavItem[] = [
  { label: 'Engine', path: '/engine', icon: Cpu, adminOnly: true },
  { label: 'System health', path: '/system', icon: Server, adminOnly: true },
  { label: 'Users', path: '/users', icon: Users, adminOnly: true },
  { label: 'Audit log', path: '/audit', icon: ScrollText, adminOnly: true },
]
const ACCOUNT: NavItem[] = [
  { label: 'Plans', path: '/pricing', icon: Tag },
  { label: 'Profile', path: '/profile', icon: User },
  { label: 'Settings', path: '/settings', icon: Settings },
]

export default function Sidebar() {
  const { isAdmin, canAccess, user, logout } = useAuthStore()
  const { sidebarCollapsed, toggleSidebar } = useUiStore()
  const { isDemoMode, demoTier } = useDemoStore()
  const navigate = useNavigate()

  const visible = (items: NavItem[]) => items.filter(item => {
    if (item.adminOnly) return isAdmin && !isDemoMode
    if (item.minTier) return canAccess(item.minTier)
    return true
  })

  const pathFor = (path: string) => isDemoMode
    ? path === '/' ? '/demo/home' : `/demo${path}`
    : path

  const handleLogout = async () => {
    if (isDemoMode) { navigate('/login', { replace: true }); return }
    try { await authApi.logout() } catch { /* Session may already be expired. */ }
    logout()
    navigate('/welcome', { replace: true })
    toast.success('Signed out')
  }

  const groups: { title: string; items: NavItem[] }[] = [
    { title: 'Workspace', items: WORKSPACE },
    { title: 'Markets', items: MARKETS },
    { title: 'Operations', items: OPERATIONS },
  ]
  const email = isDemoMode ? `demo-${demoTier}@signalengine.app` : user?.email ?? ''
  const tier = isDemoMode ? demoTier : user?.tier ?? 'free'

  return (
    <motion.aside
      animate={{ width: sidebarCollapsed ? 72 : 248 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className="app-sidebar relative flex h-dvh shrink-0 flex-col overflow-hidden border-r border-border bg-sidebar"
    >
      <div className={cn('flex h-[68px] shrink-0 items-center border-b border-sidebar-border px-4', sidebarCollapsed ? 'justify-center' : 'justify-between')}>
        <button onClick={() => navigate(isDemoMode ? '/demo/home' : '/')} className="flex min-w-0 items-center gap-3 text-left" aria-label="Signal Engine home">
          <span className="brand-mark"><TrendingUp className="h-[17px] w-[17px]" /></span>
          {!sidebarCollapsed && <span className="min-w-0">
            <span className="block truncate text-[13px] font-semibold tracking-[-0.02em] text-sidebar-foreground">Signal Engine</span>
            <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-[0.13em] text-muted-foreground">{isDemoMode ? 'Interactive demo' : isAdmin ? 'Operations' : 'Workspace'}</span>
          </span>}
        </button>
        {!sidebarCollapsed && <button onClick={toggleSidebar} aria-label="Collapse navigation" className="icon-button h-8 w-8"><PanelLeftClose className="h-4 w-4" /></button>}
      </div>

      <nav aria-label="Primary navigation" className="flex-1 space-y-6 overflow-y-auto px-3 py-5 scrollbar-none">
        {groups.map(group => {
          const items = visible(group.items)
          if (!items.length) return null
          return <section key={group.title} className="space-y-1.5">
            {!sidebarCollapsed && <h2 className="nav-section-label px-3">{group.title}</h2>}
            {items.map(item => <NavItemLink key={item.path} item={item} path={pathFor(item.path)} collapsed={sidebarCollapsed} />)}
          </section>
        })}
      </nav>

      <div className="shrink-0 border-t border-sidebar-border p-3">
        <div className="space-y-1">
          {ACCOUNT.map(item => <NavItemLink key={item.path} item={item} path={pathFor(item.path)} collapsed={sidebarCollapsed} />)}
        </div>
        <div className={cn('mt-3 flex items-center border-t border-sidebar-border pt-3', sidebarCollapsed ? 'justify-center' : 'gap-3 px-1')}>
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sidebar-accent text-xs font-semibold text-sidebar-foreground">{email.charAt(0).toUpperCase() || 'S'}</div>
          {!sidebarCollapsed && <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-sidebar-foreground">{email || 'Signal Engine'}</p>
            <p className="mt-0.5 text-[10px] capitalize text-muted-foreground">{tier}{isDemoMode ? ' · demo' : ''}</p>
          </div>}
          <button onClick={handleLogout} aria-label={isDemoMode ? 'Exit demo' : 'Sign out'} title={isDemoMode ? 'Exit demo' : 'Sign out'} className="icon-button h-8 w-8 shrink-0"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>

      {sidebarCollapsed && <button onClick={toggleSidebar} aria-label="Expand navigation" className="absolute left-[58px] top-[18px] z-20 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-sm hover:text-foreground"><ChevronRight className="h-3.5 w-3.5" /></button>}
    </motion.aside>
  )
}

function NavItemLink({ item, path, collapsed }: { item: NavItem; path: string; collapsed: boolean }) {
  const Icon = item.icon
  return <NavLink to={path} end={path === '/' || path === '/demo/home'} title={collapsed ? item.label : undefined}
    className={({ isActive }) => cn('nav-item group', isActive && 'nav-item-active', collapsed && 'justify-center px-0')}>
    <Icon className="h-[17px] w-[17px] shrink-0" />
    {!collapsed && <span className="truncate">{item.label}</span>}
    {item.minTier && !collapsed && <span className="ml-auto rounded border border-border/70 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-muted-foreground">Pro</span>}
  </NavLink>
}
