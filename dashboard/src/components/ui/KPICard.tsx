import { useEffect, useRef, useState } from 'react'
import { animate } from 'framer-motion'
import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface KPICardProps {
  title:           string
  value:           string
  sub?:            string
  subPositive?:    boolean
  icon?:           LucideIcon
  loading?:        boolean
  className?:      string
  valueClassName?: string
  spotlight?:      boolean
}

function extractNumber(value: string): number | null {
  if (!value || value === '—') return null
  const cleaned = value.replace(/[^0-9.-]/g, '')
  const num     = parseFloat(cleaned)
  return isNaN(num) ? null : num
}

function useCountUp(target: string, duration = 800) {
  const [displayed, setDisplayed] = useState(target)
  const prev    = useRef(target)
  const animRef = useRef<ReturnType<typeof animate> | null>(null)

  useEffect(() => {
    if (target === prev.current) return

    const prevNum   = extractNumber(prev.current)
    const targetNum = extractNumber(target)
    prev.current    = target

    if (prevNum === null || targetNum === null) {
      setDisplayed(target)
      return
    }

    if (animRef.current) animRef.current.stop()

    const searchIdx  = target.search(/[0-9]/)
    const prefix     = searchIdx >= 0 ? target.slice(0, searchIdx) : ''
    const matchRes   = target.match(/[0-9.,]+/)
    const matchLen   = matchRes?.[0]?.length ?? 0
    const suffix     = searchIdx >= 0 ? target.slice(searchIdx + matchLen) : ''
    const decimals   = (target.match(/\.(\d+)/) ?? [])[1]?.length ?? 0

    animRef.current = animate(prevNum, targetNum, {
      duration:  duration / 1000,
      ease:      'easeOut',
      onUpdate:  (v) => {
        const formatted  = v.toFixed(decimals)
        const withCommas = parseFloat(formatted).toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
        setDisplayed(`${prefix}${withCommas}${suffix}`)
      },
      onComplete: () => setDisplayed(target),
    })

    return () => { if (animRef.current) animRef.current.stop() }
  }, [target])

  return displayed
}

export default function KPICard({
  title,
  value,
  sub,
  subPositive,
  icon: Icon,
  loading     = false,
  className,
  valueClassName,
  spotlight   = true,
}: KPICardProps) {
  const displayed  = useCountUp(value)
  const prevVal    = useRef(value)
  const [flash, setFlash] = useState(false)
  const cardRef    = useRef<HTMLDivElement>(null)
  const lastUpdate = useRef(0)
  const [spotPos,  setSpotPos] = useState('')

  useEffect(() => {
    if (value !== prevVal.current) {
      prevVal.current = value
      setFlash(true)
      const t = setTimeout(() => setFlash(false), 500)
      return () => clearTimeout(t)
    }
  }, [value])

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!spotlight) return
    const now = Date.now()
    if (now - lastUpdate.current < 32) return
    lastUpdate.current = now
    if (!cardRef.current) return
    const rect = cardRef.current.getBoundingClientRect()
    const x    = e.clientX - rect.left
    const y    = e.clientY - rect.top
    setSpotPos(
      `radial-gradient(300px circle at ${x}px ${y}px, hsl(var(--foreground)/0.04), transparent 70%)`
    )
  }

  const handleMouseLeave = () => setSpotPos('')

  if (loading) {
    return (
      <div className={cn('rounded-lg border border-border bg-card p-6', className)}>
        <div className="flex items-center justify-between mb-4">
          <div className="h-3 w-24 rounded shimmer" />
          <div className="h-8 w-8 rounded-md shimmer" />
        </div>
        <div className="h-8 w-32 rounded shimmer" />
        <div className="mt-2 h-3 w-20 rounded shimmer" />
      </div>
    )
  }

  return (
    <div
      ref           = {cardRef}
      onMouseMove   = {handleMouseMove}
      onMouseLeave  = {handleMouseLeave}
      className     = {cn(
        'relative overflow-hidden rounded-lg border border-border bg-card p-6',
        'transition-colors duration-200',
        flash && 'border-border/80',
        className
      )}
    >
      {spotPos && (
        <div
          className = "pointer-events-none absolute inset-0 transition-opacity duration-300"
          style     = {{ background: spotPos }}
        />
      )}

      <div className="relative">
        <div className="flex items-start justify-between gap-2 mb-4">
          <p className="label-xs">{title}</p>
          {Icon && (
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
              <Icon className="h-4 w-4 text-muted-foreground" />
            </div>
          )}
        </div>

        <p className={cn('value-lg text-foreground', valueClassName)}>
          {displayed}
        </p>

        {sub !== undefined && (
          <p className={cn(
            'mt-1.5 text-xs',
            subPositive === true  && 'text-[hsl(var(--chart-1))]',
            subPositive === false && 'text-[hsl(var(--chart-2))]',
            subPositive === undefined && 'text-muted-foreground',
          )}>
            {sub}
          </p>
        )}
      </div>
    </div>
  )
}