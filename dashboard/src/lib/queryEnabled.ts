import { useDemoStore } from '@/demo/demoStore'

export function useEnabled(condition = true): boolean {
  const { isDemoMode } = useDemoStore()
  return !isDemoMode && condition
}