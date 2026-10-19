import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldCheck, X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface TotpModalProps {
  open:        boolean
  title:       string
  description: string
  onConfirm:   (code: string) => Promise<void>
  onClose:     () => void
  loading?:    boolean
  destructive?: boolean
}

export default function TotpModal({
  open,
  title,
  description,
  onConfirm,
  onClose,
  loading     = false,
  destructive = false,
}: TotpModalProps) {
  const [code,  setCode]  = useState(['', '', '', '', '', ''])
  const [error, setError] = useState<string | null>(null)
  const refs              = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (!open) {
      setCode(['', '', '', '', '', ''])
      setError(null)
    } else {
      setTimeout(() => refs.current[0]?.focus(), 100)
    }
  }, [open])

  const handleChange = (i: number, val: string) => {
    if (!/^\d*$/.test(val)) return
    const next  = [...code]
    next[i]     = val.slice(-1)
    setCode(next)
    setError(null)
    if (val && i < 5) refs.current[i + 1]?.focus()
  }

  const handleKeyDown = (i: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !code[i] && i > 0) {
      refs.current[i - 1]?.focus()
    }
    if (e.key === 'Enter') submit()
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (pasted.length === 6) {
      setCode(pasted.split(''))
      refs.current[5]?.focus()
    }
  }

  const submit = async () => {
    const full = code.join('')
    if (full.length !== 6) { setError('Enter the 6-digit code'); return }
    try {
      setError(null)
      await onConfirm(full)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid code'
      setError(msg)
      setCode(['', '', '', '', '', ''])
      refs.current[0]?.focus()
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial    = {{ opacity: 0 }}
            animate    = {{ opacity: 1 }}
            exit       = {{ opacity: 0 }}
            transition = {{ duration: 0.15 }}
            className  = "fixed inset-0 z-[100] bg-background/80 backdrop-blur-sm"
            onClick    = {onClose}
          />
          <div className="fixed inset-0 z-[101] flex items-center justify-center px-4">
            <motion.div
              initial    = {{ opacity: 0, scale: 0.97, y: -8 }}
              animate    = {{ opacity: 1, scale: 1,    y: 0  }}
              exit       = {{ opacity: 0, scale: 0.97, y: -8 }}
              transition = {{ duration: 0.15 }}
              className  = "w-full max-w-sm"
            >
              <div className="overflow-hidden rounded-lg border border-border bg-card shadow-2xl">
                <div className="flex items-center justify-between border-b border-border px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-md',
                      destructive ? 'bg-[hsl(var(--chart-2)/0.1)]' : 'bg-muted'
                    )}>
                      <ShieldCheck className={cn(
                        'h-4 w-4',
                        destructive
                          ? 'text-[hsl(var(--chart-2))]'
                          : 'text-muted-foreground'
                      )} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-foreground">{title}</p>
                      <p className="text-xs text-muted-foreground">{description}</p>
                    </div>
                  </div>
                  <button
                    onClick   = {onClose}
                    className = "flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>

                <div className="px-5 py-6">
                  <p className="mb-5 text-xs text-muted-foreground text-center">
                    Enter the 6-digit code from your authenticator app
                  </p>

                  <div className="flex items-center justify-center gap-2">
                    {code.map((digit, i) => (
                      <input
                        key         = {i}
                        ref         = {el => { refs.current[i] = el }}
                        type        = "text"
                        inputMode   = "numeric"
                        maxLength   = {1}
                        value       = {digit}
                        onChange    = {e => handleChange(i, e.target.value)}
                        onKeyDown   = {e => handleKeyDown(i, e)}
                        onPaste     = {handlePaste}
                        className   = {cn(
                          'h-11 w-10 rounded-md border text-center text-base font-mono font-semibold',
                          'bg-background text-foreground outline-none',
                          'transition-colors',
                          'focus:border-foreground focus:ring-1 focus:ring-foreground',
                          error  ? 'border-[hsl(var(--chart-2))]' : 'border-border',
                          digit  && !error && 'border-foreground/40'
                        )}
                      />
                    ))}
                  </div>

                  <AnimatePresence>
                    {error && (
                      <motion.p
                        initial    = {{ opacity: 0, y: -4 }}
                        animate    = {{ opacity: 1, y: 0  }}
                        exit       = {{ opacity: 0 }}
                        className  = "mt-3 text-center text-xs text-[hsl(var(--chart-2))]"
                      >
                        {error}
                      </motion.p>
                    )}
                  </AnimatePresence>
                </div>

                <div className="flex items-center gap-2 border-t border-border px-5 py-4">
                  <button
                    onClick   = {onClose}
                    disabled  = {loading}
                    className = "flex-1 rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick   = {submit}
                    disabled  = {loading || code.join('').length !== 6}
                    className = {cn(
                      'flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors',
                      'disabled:opacity-50 disabled:cursor-not-allowed',
                      destructive
                        ? 'bg-[hsl(var(--chart-2))] text-white hover:bg-[hsl(var(--chart-2)/0.9)]'
                        : 'bg-foreground text-background hover:bg-foreground/90'
                    )}
                  >
                    {loading ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                        Verifying
                      </span>
                    ) : 'Confirm'}
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  )
}