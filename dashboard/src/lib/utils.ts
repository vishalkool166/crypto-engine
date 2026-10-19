import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow } from 'date-fns'
import numeral from 'numeral'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

function normalizeDate(value: string): string {
  return value.includes('Z') || value.includes('+') ? value : value + 'Z'
}

export function formatCurrency(
  value:    number | null | undefined,
  decimals: number = 2
): string {
  if (value === null || value === undefined) return '—'
  const abs  = Math.abs(value)
  const sign = value >= 0 ? '+$' : '-$'
  return sign + numeral(abs).format(`0,0.${'0'.repeat(decimals)}`)
}

export function formatCurrencyCompact(
  value: number | null | undefined
): string {
  if (value === null || value === undefined) return '—'
  const abs  = Math.abs(value)
  const sign = value >= 0 ? '+$' : '-$'
  if (abs >= 1_000_000) return sign + numeral(abs).format('0.00a').toUpperCase()
  if (abs >= 1_000)     return sign + numeral(abs).format('0,0.00')
  return sign + numeral(abs).format('0.00')
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (value >= 10_000) return '$' + numeral(value).format('0,0.00')
  if (value >= 1_000)  return '$' + numeral(value).format('0,0.00')
  if (value >= 1)      return '$' + numeral(value).format('0,0.0000')
  return '$' + numeral(value).format('0,0.00000000')
}

export function formatPercent(
  value:    number | null | undefined,
  showSign: boolean = true
): string {
  if (value === null || value === undefined) return '—'
  const sign = showSign && value > 0 ? '+' : ''
  return `${sign}${numeral(value).format('0.00')}%`
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return numeral(value).format('0,0')
}

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return numeral(value).format('0.0a').toUpperCase()
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value)}`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  try {
    return format(new Date(normalizeDate(value)), 'dd MMM yyyy')
  } catch {
    return '—'
  }
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  try {
    return format(new Date(normalizeDate(value)), 'dd MMM yyyy, HH:mm')
  } catch {
    return '—'
  }
}

export function formatDateTimeShort(value: string | null | undefined): string {
  if (!value) return '—'
  try {
    return format(new Date(normalizeDate(value)), 'dd MMM, HH:mm')
  } catch {
    return '—'
  }
}

export function formatTimeAgo(value: string | null | undefined): string {
  if (!value) return '—'
  try {
    return formatDistanceToNow(
      new Date(normalizeDate(value)),
      { addSuffix: true }
    )
  } catch {
    return '—'
  }
}

export function formatCountdown(epochMs: number | null | undefined): string {
  if (!epochMs) return '—'
  const diff = epochMs - Date.now()
  if (diff <= 0) return 'Now'
  const mins = Math.floor(diff / 60000)
  const secs = Math.floor((diff % 60000) / 1000)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function formatDuration(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return '—'
  if (hours < 1) {
    const mins = Math.round(hours * 60)
    return `${mins}m`
  }
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

export function formatDurationFromSeconds(seconds: number): string {
  if (seconds < 60)   return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

export function formatFunding(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(4)}%`
}

export function formatMRR(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return '$' + numeral(value).format('0,0')
}

export function isPositive(value: number | null | undefined): boolean {
  if (value === null || value === undefined) return true
  return value >= 0
}

export function tierLabel(tier: string | null | undefined): string {
  switch (tier) {
    case 'free':  return 'Basic'
    case 'pro':   return 'Pro'
    case 'elite': return 'Elite'
    case 'admin': return 'Admin'
    default:      return '—'
  }
}

export function truncate(
  str:    string | null | undefined,
  length: number = 20
): string {
  if (!str) return '—'
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

export function fundingColor(pct: number): string {
  const abs = Math.abs(pct)
  if (abs > 0.08) return 'text-[hsl(var(--chart-2))]'
  if (abs > 0.05) return 'text-[hsl(var(--chart-4))]'
  return 'text-muted-foreground'
}

export function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, value))
}