import { useEffect, useRef } from 'react'
import { useDemoStore } from '@/demo/demoStore'
import api from '@/lib/api'

const SESSION_KEY = 'se_demo_session'

function getSessionId(): string {
  let sid = sessionStorage.getItem(SESSION_KEY)
  if (!sid) {
    sid = `demo_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    sessionStorage.setItem(SESSION_KEY, sid)
  }
  return sid
}

export function useDemoTracking() {
  const { isDemoMode, demoTier } = useDemoStore()
  const startTime                = useRef(Date.now())
  const sessionId                = useRef(getSessionId())
  const visitFired               = useRef(false)
  const prevTier                 = useRef(demoTier)

  useEffect(() => {
    if (!isDemoMode || visitFired.current) return
    visitFired.current = true

    api.post('/api/demo/visit', {
      session_id: sessionId.current,
      tier:       demoTier,
      referrer:   document.referrer || '',
    }).catch(() => {})
  }, [isDemoMode])

  useEffect(() => {
    if (!isDemoMode) return
    if (demoTier === prevTier.current) return
    prevTier.current = demoTier

    api.post('/api/demo/event', {
      session_id: sessionId.current,
      event:      'tier_switch',
      tier:       demoTier,
    }).catch(() => {})
  }, [demoTier, isDemoMode])

  useEffect(() => {
    if (!isDemoMode) return

    const handleExit = () => {
      const duration = Math.floor((Date.now() - startTime.current) / 1000)
      navigator.sendBeacon(
        '/api/demo/event',
        JSON.stringify({
          session_id:    sessionId.current,
          event:         'exit',
          duration_secs: duration,
        })
      )
    }

    window.addEventListener('beforeunload', handleExit)
    return () => window.removeEventListener('beforeunload', handleExit)
  }, [isDemoMode])

  const trackCta = () => {
    if (!isDemoMode) return
    api.post('/api/demo/event', {
      session_id: sessionId.current,
      event:      'cta_click',
    }).catch(() => {})
  }

  return { trackCta, sessionId: sessionId.current }
}