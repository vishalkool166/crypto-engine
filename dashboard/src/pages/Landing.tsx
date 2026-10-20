import { Link } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowDownRight, ArrowRight, BarChart3, Check, ChevronRight, CircleHelp, Radio, ShieldCheck, TrendingUp } from 'lucide-react'

const steps = [
  { icon: Radio, title: 'Scan the market', text: 'The engine evaluates a defined crypto universe against its technical setup and market conditions.' },
  { icon: BarChart3, title: 'Review the evidence', text: 'Each signal carries its direction, grade, risk levels, and the context available to your plan.' },
  { icon: ShieldCheck, title: 'Make your own decision', text: 'Use the analysis as research input. You control whether to act, how much to risk, and when to exit.' },
]

export default function Landing() {
  const reduceMotion = useReducedMotion()
  return (
    <div className="marketing-shell min-h-[100dvh] bg-background text-foreground">
      <header className="marketing-nav">
        <Link to="/welcome" className="flex items-center gap-3" aria-label="Signal Engine home">
          <span className="brand-mark"><TrendingUp className="h-[17px] w-[17px]" /></span>
          <span className="text-sm font-semibold tracking-[-0.02em]">Signal Engine</span>
        </Link>
        <nav className="hidden items-center gap-8 sm:flex" aria-label="Main navigation">
          <a href="#how-it-works" className="marketing-link">How it works</a>
          <a href="#about" className="marketing-link">About</a>
          <Link to="/plans" className="marketing-link">Plans</Link>
          <Link to="/demo" className="marketing-link">Explore demo</Link>
        </nav>
        <div className="flex items-center gap-2">
          <Link to="/login" className="button-quiet hidden sm:inline-flex">Sign in</Link>
          <Link to="/demo" className="button-primary">Open demo <ArrowRight className="h-3.5 w-3.5" /></Link>
        </div>
      </header>

      <main>
        <section className="marketing-hero page-container">
          <div className="marketing-copy">
            <motion.p initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="eyebrow">
              Research workspace for crypto markets
            </motion.p>
            <motion.h1 initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.04 }}>
              Market signals, with the reasoning in view.
            </motion.h1>
            <motion.p initial={reduceMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.12 }} className="marketing-lede">
              Signal Engine turns a live crypto market scan into structured setups, risk levels, and performance context—so you can evaluate the evidence before making a decision.
            </motion.p>
            <motion.div initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.2 }} className="mt-7 flex flex-wrap items-center gap-3">
              <Link to="/demo" className="button-primary button-large">Explore the demo <ArrowRight className="h-4 w-4" /></Link>
              <Link to="/login" className="button-secondary button-large">Sign in</Link>
            </motion.div>
            <p className="mt-5 max-w-xl text-xs leading-5 text-muted-foreground">Signals are analytical outputs, not guarantees or personalized financial advice. You remain responsible for every trading decision.</p>
          </div>

          <motion.div initial={reduceMotion ? false : { opacity: 0, y: 16, scale: 0.985 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.55, delay: 0.1 }} className="product-preview" aria-label="Illustration of the Signal Engine workspace">
            <div className="preview-topbar">
              <div className="flex items-center gap-2"><span className="preview-dot" /><span className="text-xs font-medium">Market overview</span></div>
              <span className="preview-label">Research workspace</span>
            </div>
            <div className="preview-summary">
              <div><p className="preview-label">Market scan</p><p className="mt-1 text-2xl font-semibold tracking-tight">Structured signals</p></div>
              <span className="preview-status"><span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--chart-1))]" /> Scanner status</span>
            </div>
            <div className="preview-chart" role="img" aria-label="Illustrative price and signal context chart">
              <div className="chart-axis"><span>Market context</span><span>Signal review</span><span>Risk levels</span></div>
              <svg viewBox="0 0 620 190" preserveAspectRatio="none" aria-hidden="true" className="h-full w-full">
                <defs><linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="hsl(var(--chart-1))" stopOpacity=".22" /><stop offset="1" stopColor="hsl(var(--chart-1))" stopOpacity="0" /></linearGradient></defs>
                {[38, 82, 126, 170].map(y => <line key={y} x1="0" x2="620" y1={y} y2={y} className="chart-gridline" />)}
                <path d="M0 144 C30 132 42 148 68 126 S108 132 133 106 S174 119 200 94 S236 101 262 88 S300 99 328 69 S374 89 402 62 S444 76 470 48 S517 57 541 34 S581 49 620 18 L620 190 L0 190 Z" fill="url(#chart-fill)" />
                <path d="M0 144 C30 132 42 148 68 126 S108 132 133 106 S174 119 200 94 S236 101 262 88 S300 99 328 69 S374 89 402 62 S444 76 470 48 S517 57 541 34 S581 49 620 18" fill="none" stroke="hsl(var(--chart-1))" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                <line x1="0" x2="620" y1="82" y2="82" stroke="hsl(var(--chart-4))" strokeDasharray="5 5" strokeOpacity=".75" />
                <circle cx="470" cy="48" r="4" fill="hsl(var(--chart-1))" stroke="hsl(var(--background))" strokeWidth="2" />
              </svg>
            </div>
            <div className="preview-signal">
              <div className="preview-signal-mark"><TrendingUp className="h-4 w-4" /></div>
              <div className="min-w-0 flex-1"><p className="text-xs font-semibold">Signal review</p><p className="mt-1 truncate text-[11px] text-muted-foreground">Direction · grade · entry · stop · targets</p></div>
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="px-5 pb-4 text-[10px] text-muted-foreground/70">Illustrative interface · no live market values shown</p>
          </motion.div>
        </section>

        <section id="how-it-works" className="section-divider">
          <div className="page-container py-20 md:py-28">
            <div className="section-heading">
              <p className="eyebrow">A clearer way to evaluate setups</p>
              <h2>From market scan to informed review.</h2>
              <p>Every part of the workflow is built around readable evidence and explicit risk context.</p>
            </div>
            <div className="process-grid">
              {steps.map((step, index) => <motion.article key={step.title} initial={reduceMotion ? false : { opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.35 }} transition={{ duration: 0.35, delay: index * 0.06 }} className="process-item">
                <step.icon className="h-5 w-5 text-foreground" strokeWidth={1.7} />
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </motion.article>)}
            </div>
          </div>
        </section>

        <section id="about" className="page-container py-20 md:py-28">
          <div className="principles-panel">
            <div className="max-w-xl">
              <p className="eyebrow">Built for deliberate decisions</p>
              <h2>Useful context. Clear limits.</h2>
              <p className="mt-4 leading-7 text-muted-foreground">The workspace brings together signal history, open positions, and engine context. It shows what the system observed and how the setup is framed; it does not promise outcomes.</p>
            </div>
            <ul className="principles-list">
              <li><Check />Risk levels stay visible alongside a setup.</li>
              <li><Check />Historical results remain separate from future expectations.</li>
              <li><Check />Paper-trading and live states are labeled in the workspace.</li>
              <li><CircleHelp />You decide whether a signal fits your own process.</li>
            </ul>
          </div>
        </section>

        <section className="section-divider">
          <div className="page-container py-16 md:py-20">
            <div className="final-cta">
              <div><p className="eyebrow">Take a look around</p><h2>See the workspace before you sign in.</h2><p>Explore a guided demo or continue to your account.</p></div>
              <div className="flex flex-wrap gap-3"><Link to="/demo" className="button-primary button-large">Open demo <ArrowRight className="h-4 w-4" /></Link><Link to="/login" className="button-secondary button-large">Sign in</Link></div>
              <ArrowDownRight className="cta-mark hidden lg:block" aria-hidden="true" />
            </div>
          </div>
        </section>
      </main>

      <footer className="marketing-footer"><Link to="/welcome" className="flex items-center gap-2"><span className="brand-mark brand-mark-small"><TrendingUp className="h-3.5 w-3.5" /></span><span className="text-xs font-semibold">Signal Engine</span></Link><span className="text-xs text-muted-foreground">Market research software · Crypto assets involve risk.</span><Link to="/login" className="marketing-link">Account sign in</Link></footer>
    </div>
  )
}
