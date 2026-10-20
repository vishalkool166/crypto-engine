import { create } from 'zustand'
import type { Tier } from '@/types'
import { TIER_FEATURES_MAP } from '@/stores/authStore'

interface DemoState {
  isDemoMode:  boolean
  demoTier:    Tier
  setDemoMode: (v: boolean) => void
  setDemoTier: (tier: Tier) => void
}

export const useDemoStore = create<DemoState>((set) => ({
  isDemoMode: false,
  demoTier:   'free',

  setDemoMode: (v) => {
    set({ isDemoMode: v })
    if (v) {
      const { demoTier } = useDemoStore.getState()
      import('@/stores/authStore').then(({ useAuthStore }) => {
        useAuthStore.getState().setUser({
          sub:      'demo',
          email:    `demo-${demoTier}@signalengine.app`,
          tier:     demoTier,
          is_admin: demoTier === 'admin',
          type:     'demo',
        })
      })
    }
  },

  setDemoTier: (tier) => {
    set({ demoTier: tier })
    import('@/stores/authStore').then(({ useAuthStore }) => {
      useAuthStore.getState().setUser({
        sub:      'demo',
        email:    `demo-${tier}@signalengine.app`,
        tier,
        is_admin: tier === 'admin',
        type:     'demo',
      })
    })
  },
}))