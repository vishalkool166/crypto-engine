import { useCallback } from 'react'
import { useDemoStore } from '@/demo/demoStore'
import { useAuthStore } from '@/stores/authStore'

const DELAY_MS = 480 * 60 * 1000

function getFirstTimestamp(timestamp: string | number | null | undefined): number | null {
  if (!timestamp) return null
  if (typeof timestamp === 'number') return timestamp * 1000
  try {
    const dt = new Date(
      timestamp.includes('Z') || timestamp.includes('+')
        ? timestamp
        : timestamp + 'Z'
    )
    return isNaN(dt.getTime()) ? null : dt.getTime()
  } catch {
    return null
  }
}

export function useSignalAccess() {
  const { isDemoMode, demoTier } = useDemoStore()
  const { tier, isAdmin }        = useAuthStore()

  const effectiveTier = isDemoMode ? demoTier : tier

  const isFree = !isAdmin && effectiveTier === 'free'

  const canSeeSignal = useCallback((timestamp: string | number | null | undefined): boolean => {
    if (!isFree) return true
    const ts = getFirstTimestamp(timestamp)
    if (!ts) return false
    return Date.now() - ts >= DELAY_MS
  }, [isFree])

  const msUntilVisible = useCallback((timestamp: string | number | null | undefined): number => {
    if (!isFree) return 0
    const ts = getFirstTimestamp(timestamp)
    if (!ts) return DELAY_MS
    return Math.max(0, DELAY_MS - (Date.now() - ts))
  }, [isFree])

  return {
    isFree,
    isAdmin,
    effectiveTier,
    canSeeSignal,
    msUntilVisible,
  }
}
