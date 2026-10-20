import { useEffect, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useDemoStore } from '@/demo/demoStore'
import { authApi } from '@/lib/api'

export default function AuthGuard({ children }: { children: ReactNode }) {
  const { isAuthenticated, setUser, setLoading, isLoading } = useAuthStore()
  const { isDemoMode } = useDemoStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (isDemoMode) {
      setLoading(false)
      return
    }

    const verify = async () => {
      setLoading(true)
      try {
        const res = await authApi.get('/auth/session')
        if (res.data.authenticated && res.data.user) {
          setUser({
            sub:      res.data.user.id,
            email:    res.data.user.email,
            tier:     res.data.user.tier as never,
            is_admin: res.data.user.is_admin,
            type:     'oauth',
          })
        } else {
          setUser(null)
          navigate('/welcome', { replace: true })
        }
      } catch {
        setUser(null)
        navigate('/welcome', { replace: true })
      } finally {
        setLoading(false)
      }
    }
    verify()
  }, [isDemoMode])

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-foreground" />
          <p className="text-xs text-muted-foreground">Verifying session</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) return null

  return <>{children}</>
}
