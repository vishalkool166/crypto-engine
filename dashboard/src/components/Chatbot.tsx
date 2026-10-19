import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle, X, Send, Trash2, Bot, Database } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/chatStore'
import { useAuthStore } from '@/stores/authStore'
import api from '@/lib/api'

export default function Chatbot() {
  const { hasFeature, isAdmin }                      = useAuthStore()
  const { messages, isOpen, toggle, close,
          addMessage, updateMessage, clearMessages } = useChatStore()
  const [input,   setInput]                         = useState('')
  const [loading, setLoading]                       = useState(false)
  const bottomRef                                   = useRef<HTMLDivElement>(null)
  const inputRef                                    = useRef<HTMLInputElement>(null)

  const canUse = hasFeature('api_key_access') || isAdmin

  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 100)
  }, [isOpen])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setLoading(true)

    addMessage({ role: 'user', content: text, loading: false })

    const assistantId = addMessage({
      role:    'assistant',
      content: '',
      loading: true,
    })

    try {
      const res    = await api.post('/api/chat', { message: text })
      const answer = res.data?.answer   ??
                     res.data?.reply    ??
                     res.data?.response ??
                     res.data?.message  ??
                     'No response'

      const sources = res.data?.sources  ?? []
      const ragUsed = res.data?.rag_used ?? false

      let content = answer

      if (ragUsed && sources.length > 0) {
        const uniqueSources = [...new Set(
          sources
            .filter((s: { collection: string }) => s.collection)
            .map((s: { collection: string }) => s.collection)
        )] as string[]

        if (uniqueSources.length > 0) {
          content = answer + `\n\n__sources:${uniqueSources.join(',')}__`
        }
      }

      updateMessage(assistantId, { content, loading: false })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? 'Something went wrong.'
      updateMessage(assistantId, { content: msg, loading: false })
    } finally {
      setLoading(false)
    }
  }

  const sourceLabels: Record<string, string> = {
    trades:        'Trades',
    signals:       'Signals',
    daily:         'Daily',
    coins:         'Coins',
    docs:          'Docs',
    coin_filtered: 'Coin',
  }

  const renderMessage = (content: string) => {
    const sourceMatch = content.match(/__sources:(.+)__$/)
    if (!sourceMatch) {
      return <p className="whitespace-pre-wrap">{content}</p>
    }

    const text    = content.replace(/__sources:.+__$/, '').trim()
    const sources = sourceMatch[1].split(',')

    return (
      <>
        <p className="whitespace-pre-wrap">{text}</p>
        <div className="mt-2 flex flex-wrap gap-1">
          {sources.map((s, i) => (
            <span
              key       = {i}
              className = "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] bg-background/60 text-muted-foreground border border-border/50"
            >
              <Database className="h-2.5 w-2.5" />
              {sourceLabels[s] ?? s}
            </span>
          ))}
        </div>
      </>
    )
  }

  if (!canUse) return null

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              initial    = {{ opacity: 0 }}
              animate    = {{ opacity: 1 }}
              exit       = {{ opacity: 0 }}
              transition = {{ duration: 0.15 }}
              className  = "fixed inset-0 z-40 md:hidden"
              onClick    = {close}
            />
            <motion.div
              initial    = {{ opacity: 0, y: 12, scale: 0.97 }}
              animate    = {{ opacity: 1, y: 0,  scale: 1    }}
              exit       = {{ opacity: 0, y: 12, scale: 0.97 }}
              transition = {{ duration: 0.2, ease: 'easeOut' }}
              className  = {cn(
                'fixed z-50 flex flex-col',
                'bottom-20 right-4 left-4',
                'md:bottom-20 md:right-6 md:left-auto md:w-80',
                'rounded-lg border border-border bg-card shadow-2xl overflow-hidden',
                'h-[420px]'
              )}
            >
              <div className="flex items-center justify-between border-b border-border px-4 py-3 shrink-0">
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-md bg-muted">
                    <Bot className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground leading-none">
                      Signal Assistant
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      RAG · powered by your trade history
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {messages.length > 0 && (
                    <button
                      onClick   = {clearMessages}
                      className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button
                    onClick   = {close}
                    className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-none">
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-center px-4">
                    <Bot className="h-8 w-8 text-muted-foreground/20 mb-3" />
                    <p className="text-sm font-semibold text-foreground">
                      Signal Assistant
                    </p>
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                      Ask about your trades, signals, performance, or how the engine works.
                      Answers come from your actual trading history.
                    </p>
                    <div className="mt-4 space-y-1.5 w-full">
                      {[
                        'Why do my signals fail?',
                        'What is an order block?',
                        'How is position size calculated?',
                      ].map(q => (
                        <button
                          key       = {q}
                          onClick   = {() => { setInput(q); inputRef.current?.focus() }}
                          className = "w-full rounded-md border border-border bg-background px-3 py-2 text-xs text-left text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <>
                    {messages.map(msg => (
                      <div
                        key       = {msg.id}
                        className = {cn(
                          'flex',
                          msg.role === 'user' ? 'justify-end' : 'justify-start'
                        )}
                      >
                        <div className={cn(
                          'max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed',
                          msg.role === 'user'
                            ? 'bg-foreground text-background rounded-br-sm'
                            : 'bg-muted text-foreground rounded-bl-sm'
                        )}>
                          {msg.loading ? (
                            <div className="flex items-center gap-1 py-0.5">
                              {[0, 150, 300].map(delay => (
                                <span
                                  key       = {delay}
                                  className = "h-1.5 w-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
                                  style     = {{ animationDelay: `${delay}ms` }}
                                />
                              ))}
                            </div>
                          ) : (
                            renderMessage(msg.content)
                          )}
                        </div>
                      </div>
                    ))}
                    <div ref={bottomRef} />
                  </>
                )}
              </div>

              <div className="border-t border-border p-3 shrink-0">
                <div className="flex items-center gap-2">
                  <input
                    ref         = {inputRef}
                    value       = {input}
                    onChange    = {e => setInput(e.target.value)}
                    onKeyDown   = {e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                    placeholder = "Ask about your trades..."
                    disabled    = {loading}
                    className   = "flex-1 h-8 rounded-md border border-border bg-background px-3 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-foreground/40 transition-colors disabled:opacity-50"
                  />
                  <button
                    onClick   = {handleSend}
                    disabled  = {!input.trim() || loading}
                    className = "flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-foreground text-background hover:bg-foreground/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <Send className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <motion.button
        onClick    = {toggle}
        whileHover = {{ scale: 1.04 }}
        whileTap   = {{ scale: 0.96 }}
        className  = {cn(
          'fixed bottom-20 right-4 z-40 md:bottom-6 md:right-6',
          'flex h-11 w-11 items-center justify-center rounded-full',
          'border border-border shadow-lg transition-colors',
          isOpen
            ? 'bg-foreground text-background'
            : 'bg-card text-foreground hover:bg-accent'
        )}
      >
        <AnimatePresence mode="wait">
          {isOpen ? (
            <motion.div
              key        = "close"
              initial    = {{ rotate: -90, opacity: 0 }}
              animate    = {{ rotate: 0,   opacity: 1 }}
              exit       = {{ rotate: 90,  opacity: 0 }}
              transition = {{ duration: 0.15 }}
            >
              <X className="h-4 w-4" />
            </motion.div>
          ) : (
            <motion.div
              key        = "open"
              initial    = {{ rotate: 90,  opacity: 0 }}
              animate    = {{ rotate: 0,   opacity: 1 }}
              exit       = {{ rotate: -90, opacity: 0 }}
              transition = {{ duration: 0.15 }}
            >
              <MessageCircle className="h-4 w-4" />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>
    </>
  )
}