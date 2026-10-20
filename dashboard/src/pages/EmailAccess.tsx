import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Mail, ShieldCheck } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL ?? ''
type Mode = 'login' | 'register' | 'forgot' | 'verify' | 'reset'

type ErrorPayload = { detail?: string | { msg?: string } }

async function postAccount(path: string, body: Record<string, string>): Promise<{ message?: string }> {
  const response = await fetch(`${API_URL}/auth/email/${path}`, {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const data = await response.json() as ErrorPayload & { message?: string }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request could not be completed')
  return data
}

export default function EmailAccess({ fixedMode }: { fixedMode?: 'verify' | 'reset' }) {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const rawMode = searchParams.get('mode')
  const mode: Mode = fixedMode ?? (rawMode === 'register' || rawMode === 'forgot' ? rawMode : 'login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    // Tokens arrive in fragments so they are not transmitted in the initial GET.
    // Remove immediately to avoid browser history persistence.
    if (fixedMode) {
      const match = window.location.hash.match(/^#token=([0-9a-f]{64})$/)
      if (match) setToken(match[1])
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  }, [fixedMode])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setResult('')
    try {
      if (mode === 'register') {
        const data = await postAccount('register', { email, password })
        setResult(data.message ?? 'Check your inbox for the verification link.')
      } else if (mode === 'forgot') {
        const data = await postAccount('request-reset', { email })
        setResult(data.message ?? 'If eligible, a reset link will be sent.')
      } else if (mode === 'verify') {
        const data = await postAccount('verify', { token })
        setResult(data.message ?? 'Verified. You can sign in.')
        setToken('')
      } else if (mode === 'reset') {
        const data = await postAccount('reset', { token, password })
        setResult(data.message ?? 'Password changed. Please sign in.')
        setToken('')
        setPassword('')
      } else {
        await postAccount('login', { email, password })
        navigate('/', { replace: true })
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Request failed. Try again later.')
    } finally {
      setBusy(false)
    }
  }

  const headings: Record<Mode, string> = {
    login: 'Sign in with email', register: 'Create your account',
    forgot: 'Reset your password', verify: 'Verify your email', reset: 'Choose a new password',
  }

  return (
    <main className="min-h-screen bg-background px-4 py-12 text-foreground">
      <div className="mx-auto w-full max-w-md space-y-6">
        <Link to="/login" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft size={16} /> Back to sign in
        </Link>
        <section className="rounded-xl border border-border bg-card p-6 shadow-sm sm:p-8">
          <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-muted">
            {mode === 'verify' || mode === 'reset' ? <ShieldCheck size={19} /> : <Mail size={19} />}
          </div>
          <h1 className="text-xl font-semibold tracking-tight">{headings[mode]}</h1>
          <p className="mt-2 mb-6 text-sm leading-relaxed text-muted-foreground">
            {mode === 'register' ? 'A verification email is required before the account becomes active.' :
             mode === 'forgot' ? 'If an email account exists, you will receive a reset link.' :
             mode === 'verify' ? 'Confirm the verification link sent to your inbox.' :
             mode === 'reset' ? 'Your previous sessions will be signed out when your password changes.' :
             'Sign in using your verified email account.'}
          </p>
          <form onSubmit={submit} className="space-y-4">
            {mode !== 'verify' && mode !== 'reset' && (
              <label className="block text-sm font-medium">Email address
                <input type="email" autoComplete="email" required maxLength={254} value={email}
                  onChange={event => setEmail(event.target.value)}
                  className="mt-1.5 block w-full rounded-md border border-input bg-background px-3 py-2.5 text-sm" />
              </label>
            )}
            {mode !== 'verify' && mode !== 'forgot' && (
              <label className="block text-sm font-medium">{mode === 'reset' ? 'New password' : 'Password'}
                <input type="password" minLength={mode === 'login' ? undefined : 12} maxLength={128} required
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password} onChange={event => setPassword(event.target.value)}
                  className="mt-1.5 block w-full rounded-md border border-input bg-background px-3 py-2.5 text-sm" />
              </label>
            )}
            {(mode === 'verify' || mode === 'reset') && !token && !result && (
              <p role="alert" className="text-sm text-destructive">The link is missing or invalid. Request a new one.</p>
            )}
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            {result && <p role="status" className="rounded-md bg-muted p-3 text-sm">{result}</p>}
            <button type="submit" disabled={busy || ((mode === 'verify' || mode === 'reset') && !token)}
              className="w-full rounded-md bg-primary px-3 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">
              {busy ? 'Please wait…' : ({ login: 'Sign in', register: 'Send verification email', forgot: 'Send reset link', verify: 'Verify email', reset: 'Change password' }[mode])}
            </button>
          </form>
          <nav aria-label="Account options" className="mt-6 flex flex-wrap justify-between gap-3 text-xs text-muted-foreground">
            {mode === 'login' && <><Link className="hover:text-foreground" to="/account?mode=register">Create an account</Link><Link className="hover:text-foreground" to="/account?mode=forgot">Forgot password?</Link></>}
            {mode !== 'login' && <Link className="hover:text-foreground" to="/account">Sign in with email</Link>}
          </nav>
        </section>
      </div>
    </main>
  )
}
