import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDemoStore } from '@/demo/demoStore'
import { useAuthStore } from '@/stores/authStore'
import { useDemoTracking } from '@/demo/useDemoTracking'

function DemoInit() {
  const { isDemoMode, demoTier } = useDemoStore()
  useDemoTracking()
  return null
}

export default function Demo() {
  const { setDemoMode, setDemoTier } = useDemoStore()
  const { setUser, setLoading }      = useAuthStore()
  const navigate                     = useNavigate()

  useEffect(() => {
    setDemoMode(true)
    setDemoTier('free')
    setLoading(false)
    setUser({
      sub:      'demo-free',
      email:    'demo-free@signalengine.app',
      tier:     'free',
      is_admin: false,
      type:     'demo',
    })
    navigate('/demo/home', { replace: true })
  }, [])

  return null
}

export { DemoInit }