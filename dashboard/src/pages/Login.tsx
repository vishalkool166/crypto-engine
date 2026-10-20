import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Check, ShieldCheck, TrendingUp } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'

export default function Login() {
  const { isAuthenticated } = useAuthStore()
  const navigate = useNavigate()
  const reduceMotion = useReducedMotion()

  useEffect(() => { if (isAuthenticated) navigate('/', { replace: true }) }, [isAuthenticated, navigate])

  return (
    <main className="auth-screen">
      <header className="auth-header">
        <Link to="/welcome" className="flex items-center gap-3"><span className="brand-mark"><TrendingUp className="h-[17px] w-[17px]" /></span><span className="text-sm font-semibold tracking-[-0.02em]">Signal Engine</span></Link>
        <Link to="/welcome" className="marketing-link inline-flex items-center gap-2"><ArrowLeft className="h-3.5 w-3.5" /> Back to overview</Link>
      </header>

      <section className="auth-content">
        <motion.div initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="auth-intro">
          <p className="eyebrow">Your research workspace</p>
          <h1>Welcome back.</h1>
          <p className="auth-lede">Sign in to review current market signals, your positions, and the performance context available to your account.</p>
          <ul className="auth-points">
            <li><Check /> Structured market signals with risk levels</li>
            <li><Check /> Trade and performance history in one workspace</li>
            <li><Check /> Account access protected by secure sign-in</li>
          </ul>
        </motion.div>

        <motion.div initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.08 }} className="auth-card">
          <div className="auth-card-heading"><ShieldCheck className="h-5 w-5 text-muted-foreground" /><div><h2>Sign in to Signal Engine</h2><p>Continue securely with your Google account.</p></div></div>
          <a href="/auth/google" className="google-button"><GoogleIcon />Continue with Google<ArrowRight className="ml-auto h-4 w-4 text-muted-foreground" /></a>
          <div className="auth-divider"><span>or</span></div>
          <button onClick={() => navigate('/demo')} className="button-secondary w-full">Explore the interactive demo</button>
          <p className="auth-note">The demo uses sample data. Your account and trading data are not available in demo mode.</p>
          <p className="mt-6 text-center text-[11px] leading-5 text-muted-foreground">By continuing, you agree to use Signal Engine as an analytical tool. It does not provide personalized financial advice.</p>
        </motion.div>
      </section>

      <footer className="auth-footer"><span className="inline-flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--chart-1))]" /> Secure account access</span><span>Crypto assets involve risk.</span></footer>
    </main>
  )
}

function GoogleIcon() {
  return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="h-4 w-4 shrink-0" aria-hidden="true">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
  </svg>
}
