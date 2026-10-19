import { create } from 'zustand'

export interface ChatMessage {
  id:        string
  role:      'user' | 'assistant'
  content:   string
  timestamp: number
  loading:   boolean
}

interface ChatState {
  messages:      ChatMessage[]
  isOpen:        boolean
  addMessage:    (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => string
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void
  clearMessages: () => void
  open:          () => void
  close:         () => void
  toggle:        () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isOpen:   false,

  open:   () => set({ isOpen: true }),
  close:  () => set({ isOpen: false }),
  toggle: () => set((s) => ({ isOpen: !s.isOpen })),

  addMessage: (msg) => {
    const id = crypto.randomUUID()
    set((s) => ({
      messages: [
        ...s.messages.slice(-9),
        { ...msg, id, timestamp: Date.now() },
      ],
    }))
    return id
  },

  updateMessage: (id, updates) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, ...updates } : m
      ),
    })),

  clearMessages: () => set({ messages: [] }),
}))