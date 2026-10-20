import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Check, X, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import { getTierConfig } from '@/lib/tokens'

const PLANS = [
  {
    id:          'free',
    monthly:     0,
    annual:      0,
    description: 'Explore the signal workflow',
    features: [
      'Signals delayed 30 minutes',
      '3 signals per day',
      'Grade visibility (A+/A/B)',
      'Score visible',
      '5 coins monitored',
      'Signal universe view',
    ],
    locked: [
      'Entry / SL / TP levels',
      'Live positions',
      'Performance analytics',
      'Signal thesis',
    ],
    popular: false,
  },
  {
    id:          'pro',
    monthly:     29,
    annual:      23,
    description: 'Live signals with full entry levels',
    features: [
      'Live signals — zero delay',
      'Unlimited signals per day',
      'Entry / SL / TP levels',
      'Live positions view',
      'Full performance history',
      'All coins monitored',
    ],
    locked: [
      'Signal thesis',
      'Confluence factors',
      'ML probability',
      'Backtest access',
    ],
    popular: true,
  },
  {
    id:          'elite',
    monthly:     79,
    annual:      63,
    description: 'Deeper signal analysis and research tools',
    features: [
      'Everything in Pro',
      'Signal thesis explanation',
      'Confluence factor breakdown',
      'ML probability score',
      'Backtest access',
      'API key access (3 keys)',
    ],
    locked: [],
    popular: false,
  },
]

const COMPARISON = [
  { feature: 'Signal delivery',       free: '30 min delay', pro: 'Live',  elite: 'Live'      },
  { feature: 'Signals per day',       free: '3',         pro: 'Unlimited', elite: 'Unlimited' },
  { feature: 'Score visible',         free: true,        pro: true,        elite: true        },
  { feature: 'Entry / SL / TP',       free: false,       pro: true,        elite: true        },
  { feature: 'Live positions',        free: false,       pro: true,        elite: true        },
  { feature: 'Performance history',   free: false,       pro: true,        elite: true        },
  { feature: 'Signal thesis',         free: false,       pro: false,       elite: true        },
  { feature: 'Confluence factors',    free: false,       pro: false,       elite: true        },
  { feature: 'ML probability',        free: false,       pro: false,       elite: true        },
  { feature: 'Backtest access',       free: false,       pro: false,       elite: true        },
  { feature: 'API key access',        free: false,       pro: false,       elite: true        },
  { feature: 'Coins monitored',       free: '5',         pro: 'All',       elite: 'All'       },
]

const FAQ = [
  {
    q: 'What is a signal?',
    a: 'A signal is a trading opportunity identified by the engine. It includes the coin, direction (LONG/SHORT), grade (A+/A/B), and for paid tiers — entry price, stop loss, and take profit levels.',
  },
  {
    q: 'How is the grade calculated?',
    a: 'The grade summarizes the engine’s evaluation of a setup. Where available in your plan, factor-level context explains the conditions that contributed to its score.',
  },
  {
    q: 'What is the signal delay on the free plan?',
    a: 'Free plan signals are delayed by 30 minutes. Pro and Elite receive signals as they are generated.',
  },
  {
    q: 'Is this financial advice?',
    a: 'No. Signal Engine provides automated technical analysis for educational purposes only. Always do your own research.',
  },
]

export default function Pricing() {
  const { tier: currentTier, isAuthenticated } = useAuthStore()
  const [billing, setBilling]     = useState<'monthly' | 'annual'>('monthly')
  const [openFaq, setOpenFaq]     = useState<number | null>(null)

  return (
    <div className="p-4 md:p-8 space-y-10 max-w-6xl">

      <div className="text-center space-y-2">
        <h1 className="text-xl font-semibold text-foreground">
          Plans built around how you research
        </h1>
        <p className="text-sm text-muted-foreground">
          Compare signal access, risk detail, and historical context before choosing a level.
        </p>
      </div>

      <div className="flex justify-center">
        <div className="flex items-center gap-px rounded-md border border-border overflow-hidden">
          {(['monthly', 'annual'] as const).map(b => (
            <button
              key       = {b}
              onClick   = {() => setBilling(b)}
              className = {cn(
                'px-5 py-2 text-xs font-medium capitalize transition-colors',
                billing === b
                  ? 'bg-foreground text-background'
                  : 'text-muted-foreground hover:text-foreground bg-background'
              )}
            >
              {b}
              {b === 'annual' && (
                <span className="ml-1.5 text-[hsl(var(--chart-1))]">
                  −20%
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {PLANS.map((plan, i) => {
          const price    = billing === 'annual' ? plan.annual : plan.monthly
          const isCurrent= isAuthenticated && currentTier === plan.id
          const tierCfg  = getTierConfig(plan.id)

          return (
            <motion.div
              key        = {plan.id}
              initial    = {{ opacity: 0, y: 10 }}
              animate    = {{ opacity: 1, y: 0  }}
              transition = {{ delay: i * 0.08 }}
              className  = {cn(
                'relative rounded-lg border bg-card p-6 space-y-5',
                plan.popular
                  ? 'border-foreground/20'
                  : 'border-border'
              )}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="inline-flex items-center rounded-full border border-border bg-card px-3 py-0.5 text-xs font-medium text-foreground">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="space-y-1">
                <p className={cn('text-sm font-semibold', tierCfg.text)}>
                  {tierCfg.label}
                </p>
                <p className="text-xs text-muted-foreground">
                  {plan.description}
                </p>
              </div>

              <div className="flex items-baseline gap-1">
                {price === 0 ? (
                  <span className="value-lg text-foreground">Free</span>
                ) : (
                  <>
                    <span className="value-lg text-foreground">${price}</span>
                    <span className="text-xs text-muted-foreground">/mo</span>
                    {billing === 'annual' && (
                      <span className="text-xs text-muted-foreground">
                        billed annually
                      </span>
                    )}
                  </>
                )}
              </div>

              <div className="space-y-2">
                {plan.features.map(f => (
                  <div key={f} className="flex items-start gap-2">
                    <Check className="h-3.5 w-3.5 shrink-0 text-[hsl(var(--chart-1))] mt-0.5" />
                    <span className="text-xs text-foreground">{f}</span>
                  </div>
                ))}
                {plan.locked.map(f => (
                  <div key={f} className="flex items-start gap-2">
                    <X className="h-3.5 w-3.5 shrink-0 text-muted-foreground/30 mt-0.5" />
                    <span className="text-xs text-muted-foreground/50">{f}</span>
                  </div>
                ))}
              </div>

              {isCurrent ? <button disabled className="w-full cursor-default rounded-md border border-border bg-muted px-4 py-2.5 text-sm font-medium text-muted-foreground">Current plan</button>
                : plan.id === 'free' && !isAuthenticated ? <Link to="/login" className="button-primary w-full">Continue with Google</Link>
                : <button disabled className="w-full cursor-not-allowed rounded-md border border-border bg-background px-4 py-2.5 text-sm font-medium text-muted-foreground/70">Unavailable</button>}
            </motion.div>
          )
        })}
      </div>

      <div className="rounded-md border border-[hsl(var(--chart-4)/0.2)] bg-[hsl(var(--chart-4)/0.06)] px-4 py-3 text-center">
        <p className="text-sm font-medium text-[hsl(var(--chart-4))]">Paid plan checkout is not enabled for this deployment.</p>
        <p className="mt-1 text-xs text-[hsl(var(--chart-4)/0.7)]">Plan details are shown for reference. Upgrades stay unavailable until billing is configured.</p>
      </div>

      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Compare Plans</h2>
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <table className="w-full">
            <thead className="border-b border-border">
              <tr>
                <th className="table-header-cell w-1/2">Feature</th>
                {['Basic', 'Pro', 'Elite'].map(h => (
                  <th key={h} className="table-header-cell text-center">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {COMPARISON.map(row => (
                <tr key={row.feature} className="table-row">
                  <td className="table-cell text-xs text-foreground">
                    {row.feature}
                  </td>
                  {[row.free, row.pro, row.elite].map((val, i) => (
                    <td key={i} className="table-cell text-center">
                      {typeof val === 'boolean' ? (
                        val
                          ? <Check className="h-3.5 w-3.5 text-[hsl(var(--chart-1))] mx-auto" />
                          : <X     className="h-3.5 w-3.5 text-muted-foreground/30 mx-auto" />
                      ) : (
                        <span className="text-xs text-foreground">{val}</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">
          Frequently Asked Questions
        </h2>
        <div className="space-y-2">
          {FAQ.map((item, i) => (
            <div
              key       = {i}
              className = "rounded-lg border border-border bg-card overflow-hidden"
            >
              <button
                onClick   = {() => setOpenFaq(openFaq === i ? null : i)}
                className = "flex w-full items-center justify-between px-5 py-4 text-left"
              >
                <span className="text-sm font-medium text-foreground">
                  {item.q}
                </span>
                <ChevronDown className={cn(
                  'h-4 w-4 text-muted-foreground transition-transform duration-200 shrink-0 ml-3',
                  openFaq === i && 'rotate-180'
                )} />
              </button>
              <AnimatePresence>
                {openFaq === i && (
                  <motion.div
                    initial    = {{ height: 0, opacity: 0 }}
                    animate    = {{ height: 'auto', opacity: 1 }}
                    exit       = {{ height: 0, opacity: 0 }}
                    transition = {{ duration: 0.2 }}
                    className  = "overflow-hidden"
                  >
                    <div className="border-t border-border px-5 py-4">
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {item.a}
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
