import { useEffect, ReactNode } from 'react'
import { useDemoStore } from '@/demo/demoStore'
import { useAuthStore } from '@/stores/authStore'
import type { Tier } from '@/types'

const DEMO_EMAILS: Record<Tier, string> = {
  free:  'demo-free@signalengine.app',
  pro:   'demo-pro@signalengine.app',
  elite: 'demo-elite@signalengine.app',
  admin: 'demo-elite@signalengine.app',
}

export default function DemoAuthProvider({ children }: { children: ReactNode }) {
  const { demoTier, setDemoMode } = useDemoStore()
  const { setUser, setLoading }   = useAuthStore()

  useEffect(() => {
    setDemoMode(true)
    setLoading(false)
    setUser({
      sub:      `demo-${demoTier}`,
      email:    DEMO_EMAILS[demoTier],
      tier:     demoTier,
      is_admin: false,
      type:     'demo',
    })
  }, [demoTier])

  useEffect(() => {
    return () => {
      setDemoMode(false)
      setUser(null)
    }
  }, [])

  return <>{children}</>
}