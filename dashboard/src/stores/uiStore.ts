import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UiState {
  sidebarCollapsed:     boolean
  commandPaletteOpen:   boolean
  activeCoin:           string | null
  activeUserId:         number | null
  toggleSidebar:        () => void
  setSidebarCollapsed:  (v: boolean) => void
  setCommandPaletteOpen:(v: boolean) => void
  setActiveCoin:        (coin: string | null) => void
  setActiveUserId:      (id: number | null) => void
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarCollapsed:    false,
      commandPaletteOpen:  false,
      activeCoin:          null,
      activeUserId:        null,

      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

      setSidebarCollapsed: (v) =>
        set({ sidebarCollapsed: v }),

      setCommandPaletteOpen: (v) =>
        set({ commandPaletteOpen: v }),

      setActiveCoin: (coin) =>
        set({ activeCoin: coin }),

      setActiveUserId: (id) =>
        set({ activeUserId: id }),
    }),
    {
      name:       'se-ui',
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed }),
    }
  )
)