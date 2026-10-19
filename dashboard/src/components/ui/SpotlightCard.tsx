import { useRef, useState, ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface SpotlightCardProps {
  children: ReactNode
  className?: string
  spotlightColor?: 'green' | 'red' | 'blue' | 'purple' | 'amber' | 'default'
}

const SPOTLIGHT_COLORS = {
  green:   'radial-gradient(600px circle at {x}px {y}px, rgba(52, 211, 153, 0.15), transparent 40%)',
  red:     'radial-gradient(600px circle at {x}px {y}px, rgba(239, 68, 68, 0.15), transparent 40%)',
  blue:    'radial-gradient(600px circle at {x}px {y}px, rgba(59, 130, 246, 0.15), transparent 40%)',
  purple:  'radial-gradient(600px circle at {x}px {y}px, rgba(168, 85, 247, 0.15), transparent 40%)',
  amber:   'radial-gradient(600px circle at {x}px {y}px, rgba(245, 158, 11, 0.15), transparent 40%)',
  default: 'radial-gradient(600px circle at {x}px {y}px, rgba(255, 255, 255, 0.08), transparent 40%)',
}

export default function SpotlightCard({
  children,
  className,
  spotlightColor = 'default',
}: SpotlightCardProps) {
  const cardRef     = useRef<HTMLDivElement>(null)
  const lastUpdate  = useRef(0)
  const [spotlight, setSpotlight] = useState('')

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const now = Date.now()
    if (now - lastUpdate.current < 33) return
    lastUpdate.current = now

    if (!cardRef.current) return
    const rect     = cardRef.current.getBoundingClientRect()
    const x        = e.clientX - rect.left
    const y        = e.clientY - rect.top
    const gradient = SPOTLIGHT_COLORS[spotlightColor]
      .replace('{x}', String(x))
      .replace('{y}', String(y))
    setSpotlight(gradient)
  }

  const handleMouseLeave = () => {
    setSpotlight('')
  }

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className={cn('relative overflow-hidden', className)}
    >
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-300"
        style={{
          background: spotlight,
          opacity:    spotlight ? 1 : 0,
        }}
      />
      <div className="relative z-10">
        {children}
      </div>
    </div>
  )
}