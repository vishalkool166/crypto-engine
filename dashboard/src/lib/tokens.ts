import {
  TrendingUp, TrendingDown, Minus,
  Zap, Flame, Clock,
} from 'lucide-react'

// ─── Grade ───────────────────────────────────────────────
export const gradeConfig = {
  'A+': {
    label:  'A+',
    color:  'hsl(var(--chart-1))',
    text:   'text-[hsl(var(--chart-1))]',
    bg:     'bg-[hsl(var(--chart-1)/0.08)]',
    border: 'border-[hsl(var(--chart-1)/0.2)]',
  },
  'A': {
    label:  'A',
    color:  'hsl(var(--chart-3))',
    text:   'text-[hsl(var(--chart-3))]',
    bg:     'bg-[hsl(var(--chart-3)/0.08)]',
    border: 'border-[hsl(var(--chart-3)/0.2)]',
  },
  'B': {
    label:  'B',
    color:  'hsl(var(--chart-4))',
    text:   'text-[hsl(var(--chart-4))]',
    bg:     'bg-[hsl(var(--chart-4)/0.08)]',
    border: 'border-[hsl(var(--chart-4)/0.2)]',
  },
  'C': {
    label:  'C',
    color:  'hsl(var(--muted-foreground))',
    text:   'text-muted-foreground',
    bg:     'bg-muted',
    border: 'border-border',
  },
  'F': {
    label:  'F',
    color:  'hsl(var(--muted-foreground))',
    text:   'text-muted-foreground',
    bg:     'bg-muted',
    border: 'border-border',
  },
  '--': {
    label:  '—',
    color:  'hsl(var(--muted-foreground))',
    text:   'text-muted-foreground',
    bg:     'bg-muted',
    border: 'border-border',
  },
} as const

// ─── Direction ───────────────────────────────────────────
export const directionConfig = {
  LONG: {
    label:  'Long',
    text:   'text-[hsl(var(--chart-1))]',
    bg:     'bg-[hsl(var(--chart-1)/0.08)]',
    border: 'border-[hsl(var(--chart-1)/0.15)]',
    icon:   TrendingUp,
  },
  SHORT: {
    label:  'Short',
    text:   'text-[hsl(var(--chart-2))]',
    bg:     'bg-[hsl(var(--chart-2)/0.08)]',
    border: 'border-[hsl(var(--chart-2)/0.15)]',
    icon:   TrendingDown,
  },
} as const

// ─── Coin State ───────────────────────────────────────────
export const stateConfig = {
  watching: {
    label: 'Watching',
    text:  'text-[hsl(var(--chart-4))]',
    dot:   'bg-[hsl(var(--chart-4))]',
    icon:  Zap,
  },
  in_trade: {
    label: 'In Trade',
    text:  'text-[hsl(var(--chart-5))]',
    dot:   'bg-[hsl(var(--chart-5))]',
    icon:  Flame,
  },
  cooldown: {
    label: 'Cooldown',
    text:  'text-muted-foreground',
    dot:   'bg-muted-foreground',
    icon:  Clock,
  },
  idle: {
    label: 'Idle',
    text:  'text-muted-foreground',
    dot:   'bg-muted-foreground/40',
    icon:  Minus,
  },
} as const

// ─── Health ───────────────────────────────────────────────
export const healthConfig = {
  HEALTHY: {
    label: 'Healthy',
    text:  'text-[hsl(var(--chart-1))]',
    dot:   'bg-[hsl(var(--chart-1))]',
  },
  WARNING: {
    label: 'Warning',
    text:  'text-[hsl(var(--chart-4))]',
    dot:   'bg-[hsl(var(--chart-4))]',
  },
  INVALIDATED: {
    label: 'Invalidated',
    text:  'text-[hsl(var(--chart-2))]',
    dot:   'bg-[hsl(var(--chart-2))]',
  },
} as const

// ─── Outcome ──────────────────────────────────────────────
export const outcomeConfig = {
  win: {
    label:  'Win',
    text:   'text-[hsl(var(--chart-1))]',
    bg:     'bg-[hsl(var(--chart-1)/0.08)]',
    border: 'border-[hsl(var(--chart-1)/0.2)]',
  },
  loss: {
    label:  'Loss',
    text:   'text-[hsl(var(--chart-2))]',
    bg:     'bg-[hsl(var(--chart-2)/0.08)]',
    border: 'border-[hsl(var(--chart-2)/0.2)]',
  },
  pending: {
    label:  'Pending',
    text:   'text-[hsl(var(--chart-4))]',
    bg:     'bg-[hsl(var(--chart-4)/0.08)]',
    border: 'border-[hsl(var(--chart-4)/0.2)]',
  },
  timeout: {
    label:  'Timeout',
    text:   'text-muted-foreground',
    bg:     'bg-muted',
    border: 'border-border',
  },
  cancelled: {
    label:  'Cancelled',
    text:   'text-muted-foreground',
    bg:     'bg-muted',
    border: 'border-border',
  },
  expired: {
    label:  'Expired',
    text:   'text-muted-foreground',
    bg:     'bg-muted',
    border: 'border-border',
  },
} as const

// ─── Close Reason ─────────────────────────────────────────
export const closeReasonConfig: Record<string, {
  label: string
  text:  string
  bg:    string
}> = {
  tp1_hit:             { label: 'TP1',        text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]' },
  tp2_hit:             { label: 'TP2',        text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]' },
  tp1_be_stop:         { label: 'BE Stop',    text: 'text-[hsl(var(--chart-3))]', bg: 'bg-[hsl(var(--chart-3)/0.08)]' },
  sl_hit:              { label: 'SL Hit',     text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]' },
  manual_close:        { label: 'Manual',     text: 'text-[hsl(var(--chart-3))]', bg: 'bg-[hsl(var(--chart-3)/0.08)]' },
  time_stop_profit:    { label: 'Time +',     text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]' },
  time_stop_breakeven: { label: 'Time =',     text: 'text-muted-foreground',       bg: 'bg-muted'                       },
  time_stop_loss:      { label: 'Time -',     text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]' },
  time_stop_after_tp1: { label: 'TP1 + Time', text: 'text-[hsl(var(--chart-1))]', bg: 'bg-[hsl(var(--chart-1)/0.08)]' },
  exchange_closed:     { label: 'Exchange',   text: 'text-[hsl(var(--chart-4))]', bg: 'bg-[hsl(var(--chart-4)/0.08)]' },
  liquidated:          { label: 'Liquidated', text: 'text-[hsl(var(--chart-2))]', bg: 'bg-[hsl(var(--chart-2)/0.08)]' },
}

// ─── Tier ─────────────────────────────────────────────────
export const tierConfig = {
  free:  { label: 'Basic',  text: 'text-muted-foreground',       bg: 'bg-muted'                       },
  pro:   { label: 'Pro',    text: 'text-[hsl(var(--chart-3))]',  bg: 'bg-[hsl(var(--chart-3)/0.08)]' },
  elite: { label: 'Elite',  text: 'text-[hsl(var(--chart-5))]',  bg: 'bg-[hsl(var(--chart-5)/0.08)]' },
  admin: { label: 'Admin',  text: 'text-[hsl(var(--chart-1))]',  bg: 'bg-[hsl(var(--chart-1)/0.08)]' },
} as const

// ─── Session ──────────────────────────────────────────────
export const sessionConfig: Record<string, {
  text:    string
  dot:     string
  quality: string
}> = {
  'London/NY Overlap': {
    text:    'text-[hsl(var(--chart-1))]',
    dot:     'bg-[hsl(var(--chart-1))] animate-pulse-dot',
    quality: 'Best',
  },
  'New York': {
    text:    'text-[hsl(var(--chart-3))]',
    dot:     'bg-[hsl(var(--chart-3))]',
    quality: 'Good',
  },
  'London': {
    text:    'text-[hsl(var(--chart-3))]',
    dot:     'bg-[hsl(var(--chart-3))]',
    quality: 'Good',
  },
  'Asia': {
    text:    'text-muted-foreground',
    dot:     'bg-muted-foreground',
    quality: 'Low',
  },
  'Off Hours': {
    text:    'text-muted-foreground',
    dot:     'bg-muted-foreground/40',
    quality: 'Low',
  },
  'Weekend': {
    text:    'text-muted-foreground',
    dot:     'bg-muted-foreground/40',
    quality: 'Low',
  },
}

// ─── Helper functions ─────────────────────────────────────
export function getGradeConfig(grade: string) {
  return gradeConfig[grade as keyof typeof gradeConfig] ?? gradeConfig['--']
}

export function getDirectionConfig(direction: string) {
  return directionConfig[direction as keyof typeof directionConfig] ?? null
}

export function getStateConfig(state: string) {
  return stateConfig[state as keyof typeof stateConfig] ?? stateConfig.idle
}

export function getHealthConfig(state: string) {
  return healthConfig[state as keyof typeof healthConfig] ?? healthConfig.HEALTHY
}

export function getOutcomeConfig(outcome: string) {
  return outcomeConfig[outcome as keyof typeof outcomeConfig] ?? outcomeConfig.pending
}

export function getCloseReasonConfig(reason: string | null) {
  if (!reason) return null
  return closeReasonConfig[reason] ?? {
    label: reason,
    text:  'text-muted-foreground',
    bg:    'bg-muted',
  }
}

export function getTierConfig(tier: string) {
  return tierConfig[tier as keyof typeof tierConfig] ?? tierConfig.free
}

export function getSessionConfig(session: string) {
  return sessionConfig[session] ?? sessionConfig['Off Hours']
}

export function pnlColor(value: number): string {
  if (value > 0) return 'text-[hsl(var(--chart-1))]'
  if (value < 0) return 'text-[hsl(var(--chart-2))]'
  return 'text-muted-foreground'
}

export function scoreToColor(score: number): string {
  if (score >= 80) return 'text-[hsl(var(--chart-1))]'
  if (score >= 65) return 'text-[hsl(var(--chart-3))]'
  if (score >= 50) return 'text-[hsl(var(--chart-4))]'
  return 'text-muted-foreground'
}

export function scoreToBarColor(score: number): string {
  if (score >= 80) return 'bg-[hsl(var(--chart-1))]'
  if (score >= 65) return 'bg-[hsl(var(--chart-3))]'
  if (score >= 50) return 'bg-[hsl(var(--chart-4))]'
  return 'bg-muted-foreground/40'
}