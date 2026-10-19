import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AuthUser, Tier, TierFeatures } from '@/types'

const TIER_FEATURES: Record<Tier, TierFeatures> = {
  free: {
    signal_delay_minutes:   480,
    signals_per_day:        3,
    show_levels:            false,
    show_factors:           false,
    show_thesis:            false,
    show_ml:                false,
    show_positions:         false,
    show_performance:       false,
    show_full_history:      false,
    show_universe:          true,
    show_system:            false,
    api_key_access:         false,
    backtest_access:        false,
    coins_limit:            5,
    show_score:             true,
    show_session_breakdown: false,
    show_phase_breakdown:   false,
    show_mae_mfe:           false,
    content_generator:      false,
    ai_assistant:           false,
  },
  pro: {
    signal_delay_minutes:   0,
    signals_per_day:        999,
    show_levels:            true,
    show_factors:           false,
    show_thesis:            false,
    show_ml:                false,
    show_positions:         true,
    show_performance:       true,
    show_full_history:      true,
    show_universe:          true,
    show_system:            false,
    api_key_access:         false,
    backtest_access:        false,
    coins_limit:            999,
    show_score:             true,
    show_session_breakdown: true,
    show_phase_breakdown:   false,
    show_mae_mfe:           false,
    content_generator:      false,
    ai_assistant:           false,
  },
  elite: {
    signal_delay_minutes:   0,
    signals_per_day:        999,
    show_levels:            true,
    show_factors:           true,
    show_thesis:            true,
    show_ml:                true,
    show_positions:         true,
    show_performance:       true,
    show_full_history:      true,
    show_universe:          true,
    show_system:            false,
    api_key_access:         true,
    backtest_access:        true,
    coins_limit:            999,
    show_score:             true,
    show_session_breakdown: true,
    show_phase_breakdown:   true,
    show_mae_mfe:           true,
    content_generator:      true,
    ai_assistant:           true,
  },
  admin: {
    signal_delay_minutes:   0,
    signals_per_day:        999,
    show_levels:            true,
    show_factors:           true,
    show_thesis:            true,
    show_ml:                true,
    show_positions:         true,
    show_performance:       true,
    show_full_history:      true,
    show_universe:          true,
    show_system:            true,
    api_key_access:         true,
    backtest_access:        true,
    coins_limit:            999,
    show_score:             true,
    show_session_breakdown: true,
    show_phase_breakdown:   true,
    show_mae_mfe:           true,
    content_generator:      true,
    ai_assistant:           true,
  },
}

const TIER_RANK: Record<Tier, number> = {
  free: 0, pro: 1, elite: 2, admin: 3,
}

interface AuthState {
  user:            AuthUser | null
  isAuthenticated: boolean
  isAdmin:         boolean
  tier:            Tier
  features:        TierFeatures
  isLoading:       boolean
  setUser:         (user: AuthUser | null) => void
  setLoading:      (loading: boolean) => void
  logout:          () => void
  hasFeature:      (feature: keyof TierFeatures) => boolean
  canAccess:       (requiredTier: Tier) => boolean
}

const DEFAULT_FEATURES = TIER_FEATURES.free

export const TIER_FEATURES_MAP = TIER_FEATURES

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user:            null,
      isAuthenticated: false,
      isAdmin:         false,
      tier:            'free',
      features:        DEFAULT_FEATURES,
      isLoading:       true,

      setUser: (user) => {
        if (!user) {
          set({
            user:            null,
            isAuthenticated: false,
            isAdmin:         false,
            tier:            'free',
            features:        DEFAULT_FEATURES,
          })
          return
        }
        const tier     = (user.tier ?? 'free') as Tier
        const isAdmin  = user.is_admin === true
        const features = isAdmin
          ? TIER_FEATURES.admin
          : TIER_FEATURES[tier] ?? DEFAULT_FEATURES
        set({
          user,
          isAuthenticated: true,
          isAdmin,
          tier:            isAdmin ? 'admin' : tier,
          features,
        })
      },

      setLoading: (loading) => set({ isLoading: loading }),

      logout: () =>
        set({
          user:            null,
          isAuthenticated: false,
          isAdmin:         false,
          tier:            'free',
          features:        DEFAULT_FEATURES,
          isLoading:       false,
        }),

      hasFeature: (feature) => {
        const { features, isAdmin } = get()
        if (isAdmin) return true
        return Boolean(features[feature])
      },

      canAccess: (requiredTier) => {
        const { tier, isAdmin } = get()
        if (isAdmin) return true
        return TIER_RANK[tier] >= TIER_RANK[requiredTier]
      },
    }),
    {
      name:       'se-auth',
      partialize: (state) => ({
        user: state.user,
        tier: state.tier,
      }),
    }
  )
)