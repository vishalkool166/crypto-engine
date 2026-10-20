import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, useMotionValue, useSpring } from 'framer-motion'
import { TrendingUp, Sun, Moon } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useTheme } from 'next-themes'

const API_URL = import.meta.env.VITE_API_URL ?? ''

function ThemeBar({ onThemeToggle, theme }: { onThemeToggle: () => void; theme: string | undefined }) {
  return (
    <header className="relative z-20 flex items-center justify-between border-b border-border/40 bg-background/80 px-5 py-3">
      <span className="text-xs font-semibold tracking-wide text-muted-foreground">SIGNAL ENGINE</span>
      <button type="button" onClick={onThemeToggle} aria-label="Toggle color theme"
        className="rounded-md border border-border p-2 text-muted-foreground hover:bg-accent hover:text-foreground">
        {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    </header>
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
  }, [mouseX, mouseY])

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
  const [emailAccountsAvailable, setEmailAccountsAvailable] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${API_URL}/auth/email/status`, { signal: controller.signal })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.enabled === true) setEmailAccountsAvailable(true) })
      .catch(() => {})
    return () => controller.abort()
  }, [])
  const { isAuthenticated } = useAuthStore()
  const navigate            = useNavigate()
  const { theme, setTheme } = useTheme()

  useEffect(() => {
    if (isAuthenticated) navigate('/', { replace: true })
  }, [isAuthenticated, navigate])

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

      <ThemeBar onThemeToggle={handleThemeToggle} theme={theme} />

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

              {emailAccountsAvailable && (
                <Link to="/account" className="block w-full rounded-md border border-border bg-background px-4 py-2.5 text-center text-sm font-medium text-foreground hover:bg-accent">
                  Continue with email
                </Link>
              )}

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

            <p className="mt-5 text-center text-xs leading-relaxed text-muted-foreground">
              Account access is secured by Signal Engine. Trading data becomes available after sign-in.
            </p>
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
