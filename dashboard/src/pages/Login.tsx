import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, useAnimationFrame, useMotionValue, useSpring } from 'framer-motion'
import { TrendingUp, Sun, Moon } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useTheme } from 'next-themes'

const API_URL = import.meta.env.VITE_API_URL ?? ''

const MOCK_TICKER = [
  { coin: 'BTC',   price: '67,420', change: '+2.34%', pos: true  },
  { coin: 'ETH',   price: '3,521',  change: '+1.87%', pos: true  },
  { coin: 'SOL',   price: '101.98', change: '+4.21%', pos: true  },
  { coin: 'BNB',   price: '687.09', change: '-0.54%', pos: false },
  { coin: 'ARB',   price: '1.24',   change: '+3.12%', pos: true  },
  { coin: 'AVAX',  price: '38.92',  change: '-1.23%', pos: false },
  { coin: 'LINK',  price: '18.74',  change: '+2.91%', pos: true  },
  { coin: 'XRP',   price: '1.3776', change: '+1.44%', pos: true  },
  { coin: 'DOGE',  price: '0.1842', change: '-0.88%', pos: false },
  { coin: 'MATIC', price: '0.892',  change: '+1.62%', pos: true  },
]

const STATS = [
  { label: 'signals generated', value: 847,  prefix: '',  suffix: ''  },
  { label: 'win rate',          value: 68.4, prefix: '',  suffix: '%' },
  { label: 'PnL tracked',       value: 2841, prefix: '$', suffix: ''  },
]

function useCountUp(target: number, duration = 1200, delay = 0) {
  const [current, setCurrent] = useState(0)

  useEffect(() => {
    const timeout = setTimeout(() => {
      const start = performance.now()
      const step  = (now: number) => {
        const elapsed  = now - start
        const progress = Math.min(elapsed / duration, 1)
        const ease     = 1 - Math.pow(1 - progress, 3)
        setCurrent(target * ease)
        if (progress < 1) requestAnimationFrame(step)
        else setCurrent(target)
      }
      requestAnimationFrame(step)
    }, delay)
    return () => clearTimeout(timeout)
  }, [target, duration, delay])

  return current
}

function StatCounter({ stat, delay }: { stat: typeof STATS[0]; delay: number }) {
  const value   = useCountUp(stat.value, 1400, delay)
  const display = stat.value % 1 !== 0
    ? value.toFixed(1)
    : Math.floor(value).toLocaleString()

  return (
    <motion.div
      initial    = {{ opacity: 0, y: 8 }}
      animate    = {{ opacity: 1, y: 0 }}
      transition = {{ delay: delay / 1000 + 0.8, duration: 0.4 }}
      className  = "flex items-center gap-1.5 text-xs text-muted-foreground"
    >
      <span className="font-mono font-semibold text-foreground">
        {stat.prefix}{display}{stat.suffix}
      </span>
      <span>{stat.label}</span>
    </motion.div>
  )
}

function TickerBar({ onThemeToggle, theme }: { onThemeToggle: () => void; theme: string | undefined }) {
  const trackRef  = useRef<HTMLDivElement>(null)
  const offsetRef = useRef(0)
  const lastRef   = useRef(0)
  const items     = [...MOCK_TICKER, ...MOCK_TICKER]

  useAnimationFrame((t) => {
    if (!trackRef.current) return
    const delta     = lastRef.current ? t - lastRef.current : 0
    lastRef.current = t
    const total     = trackRef.current.scrollWidth / 2
    if (total > 0) {
      offsetRef.current = (offsetRef.current + (28 * delta) / 1000) % total
      trackRef.current.style.transform = `translateX(-${offsetRef.current}px)`
    }
  })

  return (
    <div className="relative z-20 flex items-center border-b border-border/40 bg-background/80 backdrop-blur-sm">
      <div className="flex-1 overflow-hidden">
        <div
          ref       = {trackRef}
          className = "flex items-center gap-8 py-2 px-4 whitespace-nowrap will-change-transform"
          style     = {{ width: 'max-content' }}
        >
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-2 shrink-0">
              <span className="text-xs font-mono font-semibold text-foreground/70">{item.coin}</span>
              <span className="text-xs font-mono text-muted-foreground/60">{item.price}</span>
              <span className={`text-xs font-mono ${item.pos ? 'text-[hsl(var(--chart-1)/0.7)]' : 'text-[hsl(var(--chart-2)/0.7)]'}`}>
                {item.change}
              </span>
            </div>
          ))}
        </div>
      </div>
      <button
        onClick   = {onThemeToggle}
        className = "relative z-30 shrink-0 flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors mr-3"
      >
        {theme === 'dark'
          ? <Sun  className="h-4 w-4" />
          : <Moon className="h-4 w-4" />
        }
      </button>
    </div>
  )
}

function CursorGrid({ isDark }: { isDark: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const maskRef      = useRef<HTMLDivElement>(null)
  const mouseX       = useMotionValue(-1000)
  const mouseY       = useMotionValue(-1000)
  const springX      = useSpring(mouseX, { stiffness: 100, damping: 25 })
  const springY      = useSpring(mouseY, { stiffness: 100, damping: 25 })

  const gridColor    = isDark
    ? 'rgba(255,255,255,0.15)'
    : 'rgba(0,0,0,0.12)'

  const glowColor    = isDark
    ? 'rgba(255,255,255,0.9)'
    : 'rgba(0,0,0,0.7)'

  const glowMid      = isDark
    ? 'rgba(255,255,255,0.4)'
    : 'rgba(0,0,0,0.3)'

  useEffect(() => {
    const update = () => {
      if (!maskRef.current) return
      const x = springX.get()
      const y = springY.get()
      maskRef.current.style.maskImage =
        `radial-gradient(350px circle at ${x}px ${y}px, black 0%, black 20%, transparent 70%)`
      maskRef.current.style.webkitMaskImage =
        `radial-gradient(350px circle at ${x}px ${y}px, black 0%, black 20%, transparent 70%)`
    }
    const unsubX = springX.on('change', update)
    const unsubY = springY.on('change', update)
    return () => { unsubX(); unsubY() }
  }, [springX, springY])

  useEffect(() => {
    const handleMove = (e: MouseEvent) => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      mouseX.set(e.clientX - rect.left)
      mouseY.set(e.clientY - rect.top)
    }
    const handleLeave = () => {
      mouseX.set(-1000)
      mouseY.set(-1000)
    }
    window.addEventListener('mousemove',  handleMove)
    window.addEventListener('mouseleave', handleLeave)
    return () => {
      window.removeEventListener('mousemove',  handleMove)
      window.removeEventListener('mouseleave', handleLeave)
    }
  }, [])

  return (
    <div
      ref       = {containerRef}
      className = "absolute inset-0 overflow-hidden pointer-events-none"
    >
      <svg
        className = "absolute inset-0 w-full h-full opacity-[0.07]"
        xmlns     = "http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern
            id           = "basegrid"
            width        = "48"
            height       = "48"
            patternUnits = "userSpaceOnUse"
          >
            <path
              d           = "M 48 0 L 0 0 0 48"
              fill        = "none"
              stroke      = {gridColor}
              strokeWidth = "1"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#basegrid)" />
      </svg>

      <div
        ref   = {maskRef}
        className = "absolute inset-0"
        style = {{
          maskImage:       'radial-gradient(350px circle at -1000px -1000px, black 0%, transparent 70%)',
          WebkitMaskImage: 'radial-gradient(350px circle at -1000px -1000px, black 0%, transparent 70%)',
        }}
      >
        <svg
          className = "absolute inset-0 w-full h-full"
          xmlns     = "http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern
              id           = "glowgrid"
              width        = "48"
              height       = "48"
              patternUnits = "userSpaceOnUse"
            >
              <path
                d           = "M 48 0 L 0 0 0 48"
                fill        = "none"
                stroke      = {glowColor}
                strokeWidth = "1"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#glowgrid)" />
        </svg>

        <svg
          className = "absolute inset-0 w-full h-full"
          xmlns     = "http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern
              id           = "glowgrid2"
              width        = "48"
              height       = "48"
              patternUnits = "userSpaceOnUse"
            >
              <path
                d           = "M 48 0 L 0 0 0 48"
                fill        = "none"
                stroke      = {glowMid}
                strokeWidth = "0.5"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#glowgrid2)" opacity="0.6" />
        </svg>
      </div>

      <div className="absolute inset-0 bg-gradient-to-b from-background/0 via-background/20 to-background pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-r from-background/60 via-background/0 to-background/60 pointer-events-none" />
    </div>
  )
}

function ParticleField() {
  const mouseX  = useMotionValue(0)
  const mouseY  = useMotionValue(0)
  const springX = useSpring(mouseX, { stiffness: 30, damping: 20 })
  const springY = useSpring(mouseY, { stiffness: 30, damping: 20 })

  const particles = Array.from({ length: 8 }, (_, i) => ({
    id:    i,
    x:     20 + (i * 37) % 60,
    y:     15 + (i * 53) % 70,
    size:  1 + (i % 3) * 0.5,
    delay: i * 0.15,
  }))

  return (
    <div
      onMouseMove = {e => {
        const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect()
        mouseX.set(((e.clientX - rect.left) / rect.width  - 0.5) * 12)
        mouseY.set(((e.clientY - rect.top)  / rect.height - 0.5) * 12)
      }}
      className = "absolute inset-0 pointer-events-none overflow-hidden rounded-lg"
    >
      {particles.map(p => (
        <motion.div
          key       = {p.id}
          className = "absolute rounded-full bg-[hsl(var(--chart-3)/0.25)]"
          style     = {{
            width:  p.size * 3,
            height: p.size * 3,
            left:   `${p.x}%`,
            top:    `${p.y}%`,
            x:      springX,
            y:      springY,
          }}
          animate   = {{
            opacity: [0.2, 0.5, 0.2],
            scale:   [1, 1.3, 1],
          }}
          transition = {{
            duration: 3 + p.delay,
            repeat:   Infinity,
            delay:    p.delay,
            ease:     'easeInOut',
          }}
        />
      ))}
    </div>
  )
}

function LogoMark() {
  return (
    <motion.div
      initial    = {{ opacity: 0, scale: 0.8 }}
      animate    = {{ opacity: 1, scale: 1   }}
      transition = {{ duration: 0.4, delay: 0.2 }}
      className  = "relative flex h-14 w-14 items-center justify-center"
    >
      <motion.div
        animate    = {{
          boxShadow: [
            '0 0 0px hsl(var(--foreground)/0)',
            '0 0 32px hsl(var(--chart-3)/0.2)',
            '0 0 0px hsl(var(--foreground)/0)',
          ],
        }}
        transition = {{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        className  = "flex h-14 w-14 items-center justify-center rounded-xl border border-border bg-card"
      >
        <TrendingUp className="h-7 w-7 text-foreground" />
      </motion.div>

      <motion.div
        className  = "absolute inset-0 rounded-xl border border-[hsl(var(--chart-3)/0.3)]"
        animate    = {{ scale: [1, 1.15, 1], opacity: [0.3, 0, 0.3] }}
        transition = {{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      />
    </motion.div>
  )
}

function FloatingOrb({ className, delay = 0 }: { className?: string; delay?: number }) {
  return (
    <motion.div
      animate    = {{ y: [-16, 16, -16], opacity: [0.2, 0.45, 0.2] }}
      transition = {{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay }}
      className  = {className}
    />
  )
}

export default function Login() {
  const { isAuthenticated } = useAuthStore()
  const navigate            = useNavigate()
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    if (isAuthenticated) navigate('/', { replace: true })
  }, [isAuthenticated])

  const handleGoogle = () => {
    window.location.href = `${API_URL}/auth/google`
  }

  const handleDemo = () => {
    navigate('/demo')
  }

  const handleThemeToggle = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  const isDark = theme === 'dark'

  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-background">

      <TickerBar onThemeToggle={handleThemeToggle} theme={theme} />

      <div className="relative flex flex-1 flex-col overflow-hidden">

        <CursorGrid isDark={isDark} />

        <FloatingOrb
          className = "absolute h-80 w-80 rounded-full blur-3xl pointer-events-none bg-[hsl(var(--chart-3)/0.05)] -top-20 -left-20"
          delay     = {0}
        />
        <FloatingOrb
          className = "absolute h-64 w-64 rounded-full blur-3xl pointer-events-none bg-[hsl(var(--chart-5)/0.05)] bottom-20 right-8"
          delay     = {2}
        />
        <FloatingOrb
          className = "absolute h-48 w-48 rounded-full blur-3xl pointer-events-none bg-[hsl(var(--chart-1)/0.04)] top-1/3 right-1/4"
          delay     = {1}
        />

        <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-4">

          <motion.div
            initial    = {{ opacity: 0, y: 20 }}
            animate    = {{ opacity: 1, y: 0  }}
            transition = {{ duration: 0.5, ease: 'easeOut' }}
            className  = "w-full max-w-sm"
          >
            <motion.div
              initial    = {{ opacity: 0, scale: 0.95 }}
              animate    = {{ opacity: 1, scale: 1    }}
              transition = {{ duration: 0.4, delay: 0.1 }}
              className  = "mb-8 flex flex-col items-center gap-4"
            >
              <LogoMark />

              <div className="text-center">
                <motion.h1
                  initial    = {{ opacity: 0, y: 6 }}
                  animate    = {{ opacity: 1, y: 0 }}
                  transition = {{ delay: 0.35 }}
                  className  = "text-2xl font-bold text-foreground tracking-tight"
                >
                  Signal Engine
                </motion.h1>
                <motion.p
                  initial    = {{ opacity: 0, y: 6 }}
                  animate    = {{ opacity: 1, y: 0 }}
                  transition = {{ delay: 0.45 }}
                  className  = "mt-1 text-sm text-muted-foreground"
                >
                  Automated crypto futures intelligence
                </motion.p>
              </div>
            </motion.div>

            <motion.div
              initial    = {{ opacity: 0, y: 12 }}
              animate    = {{ opacity: 1, y: 0  }}
              transition = {{ delay: 0.5 }}
              className  = "relative rounded-lg border border-border bg-card p-6 shadow-2xl space-y-4 overflow-hidden"
            >
              <ParticleField />

              <div className="relative space-y-0.5">
                <p className="text-sm font-semibold text-foreground">Welcome back</p>
                <p className="text-xs text-muted-foreground">
                  Sign in to access your dashboard
                </p>
              </div>

              <motion.button
                whileHover = {{ scale: 1.01 }}
                whileTap   = {{ scale: 0.99 }}
                onClick    = {handleGoogle}
                className  = "relative flex w-full items-center justify-center gap-3 rounded-md border border-border bg-background px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-accent overflow-hidden group"
              >
                <motion.div
                  className = "absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 ease-in-out"
                  style     = {{
                    background: 'linear-gradient(90deg, transparent, hsl(var(--foreground)/0.04), transparent)',
                  }}
                />
                <GoogleIcon />
                Continue with Google
              </motion.button>

              <div className="relative flex items-center gap-3">
                <div className="flex-1 h-px bg-border" />
                <span className="text-xs text-muted-foreground">or</span>
                <div className="flex-1 h-px bg-border" />
              </div>

              <motion.button
                whileHover = {{ scale: 1.01 }}
                whileTap   = {{ scale: 0.99 }}
                onClick    = {handleDemo}
                className  = "flex w-full items-center justify-center gap-2 rounded-md border border-border bg-background px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <TrendingUp className="h-4 w-4" />
                Explore Demo
              </motion.button>

              <div className="rounded-md bg-muted/60 px-3 py-2.5">
                <p className="text-xs text-muted-foreground text-center leading-relaxed">
                  Access is restricted to authorized accounts.
                </p>
              </div>
            </motion.div>

            <motion.div
              initial    = {{ opacity: 0 }}
              animate    = {{ opacity: 1 }}
              transition = {{ delay: 0.9 }}
              className  = "mt-6 flex items-center justify-center gap-6 flex-wrap"
            >
              {/* These numbers and market prices are decorative samples, not engine telemetry. */}
              <span className="text-[10px] font-medium tracking-wide text-muted-foreground">Illustrative figures</span>
              {STATS.map((stat, i) => (
                <StatCounter key={stat.label} stat={stat} delay={900 + i * 150} />
              ))}
            </motion.div>

            <motion.div
              initial    = {{ opacity: 0 }}
              animate    = {{ opacity: 1 }}
              transition = {{ delay: 1.2 }}
              className  = "mt-4 flex items-center justify-center gap-4"
            >
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--chart-1))] animate-pulse-dot" />
                <span className="text-xs text-muted-foreground">System operational</span>
              </div>
              <span className="text-xs text-muted-foreground/30">·</span>
              <span className="text-xs text-muted-foreground">
                v{import.meta.env.VITE_APP_VERSION ?? '5.0.0'}
              </span>
            </motion.div>
          </motion.div>

        </div>
      </div>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg
      xmlns     = "http://www.w3.org/2000/svg"
      viewBox   = "0 0 24 24"
      className = "h-4 w-4 shrink-0"
    >
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  )
}