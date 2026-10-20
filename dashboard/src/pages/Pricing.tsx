import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, X, ChevronDown } from 'lucide-react'
import { pricingApi } from '@/lib/endpoints'
import { useAuthStore } from '@/stores/authStore'
import { getTierConfig } from '@/lib/tokens'
import { cn } from '@/lib/utils'

type TierId = 'free' | 'pro' | 'elite'
type TierFeature = { text: string; available: boolean; highlight: boolean }
type Plan = {
  id: TierId
  name: string
  price_monthly: number
  price_annual: number
  description: string
  popular: boolean
  features: TierFeature[]
}
type Comparison = {
  feature: string
  free: string | null
  pro: string | null
  elite: string | null
  free_bool: boolean | null
  pro_bool: boolean | null
  elite_bool: boolean | null
}
type PricingResponse = {
  tiers: Plan[]
  comparison: Comparison[]
  faq: { question: string; answer: string }[]
}

export default function Pricing() {
  const { tier } = useAuthStore()
  const [billing, setBilling] = useState<'monthly' | 'annual'>('monthly')
  const [openFaq, setOpenFaq] = useState<number | null>(null)
  const { data, isLoading, isError, refetch } = useQuery<PricingResponse>({
    queryKey: ['pricing-catalogue'],
    queryFn: async () => (await pricingApi.get()).data as PricingResponse,
    staleTime: 60_000,
  })

  return (
    <main className="mx-auto max-w-5xl space-y-8 p-4 md:p-6">
      <header className="space-y-2">
        <h1 className="text-xl font-semibold text-foreground">Plans and access</h1>
        <p className="text-sm text-muted-foreground">
          Your current plan controls which research and analysis tools are visible. Changes are managed by the administrator.
        </p>
      </header>

      {isLoading && <p role="status" className="text-sm text-muted-foreground">Loading current plan details…</p>}
      {isError && (
        <section role="alert" className="rounded-lg border border-border bg-card p-5">
          <p className="text-sm text-foreground">Plan details are temporarily unavailable. No pricing estimates are being shown.</p>
          <button className="mt-3 rounded-md border border-border px-3 py-1.5 text-sm" onClick={() => refetch()}>Try again</button>
        </section>
      )}

      {data && (
        <>
          <div className="inline-flex overflow-hidden rounded-md border border-border">
            {(['monthly', 'annual'] as const).map(option => (
              <button
                key={option}
                type="button"
                aria-pressed={billing === option}
                onClick={() => setBilling(option)}
                className={cn('px-4 py-2 text-xs font-medium capitalize',
                  billing === option ? 'bg-foreground text-background' : 'bg-background text-muted-foreground hover:text-foreground')}
              >{option}</button>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {data.tiers.map(plan => {
              const current = plan.id === tier
              const price = billing === 'monthly' ? plan.price_monthly : plan.price_annual
              return (
                <section key={plan.id} className={cn('rounded-lg border bg-card p-5', plan.popular ? 'border-foreground/30' : 'border-border')}>
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <h2 className={cn('text-sm font-semibold', getTierConfig(plan.id).text)}>{plan.name}</h2>
                    {current && <span className="rounded-full bg-muted px-2 py-1 text-xs text-foreground">Current plan</span>}
                  </div>
                  <p className="min-h-10 text-xs text-muted-foreground">{plan.description}</p>
                  <p className="my-4 text-2xl font-semibold text-foreground">
                    {price === 0 ? 'Free' : `$${price}`}
                    {price !== 0 && <span className="ml-1 text-xs font-normal text-muted-foreground">/month</span>}
                  </p>
                  <ul className="space-y-2 border-t border-border pt-4">
                    {plan.features.map(feature => (
                      <li key={feature.text} className="flex items-start gap-2 text-xs">
                        {feature.available
                          ? <Check aria-label="Included" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[hsl(var(--chart-1))]" />
                          : <X aria-label="Unavailable" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />}
                        <span className={feature.available ? 'text-foreground' : 'text-muted-foreground'}>{feature.text}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-5 border-t border-border pt-4 text-xs text-muted-foreground">
                    {current ? 'Your current access level' : 'Contact an administrator to request this plan'}
                  </p>
                </section>
              )
            })}
          </div>

          <p className="text-xs text-muted-foreground">
            Self-service billing and checkout are not enabled. Displayed plan amounts are catalogue values, not an offer to charge your account.
          </p>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Compare access</h2>
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full min-w-[520px] text-xs">
                <thead className="border-b border-border">
                  <tr><th className="p-3 text-left">Feature</th><th className="p-3 text-center">Basic</th><th className="p-3 text-center">Pro</th><th className="p-3 text-center">Elite</th></tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.comparison.map(row => (
                    <tr key={row.feature}>
                      <td className="p-3 text-foreground">{row.feature}</td>
                      {(['free', 'pro', 'elite'] as const).map(plan => {
                        const available = row[`${plan}_bool`]
                        return (
                          <td key={plan} className="p-3 text-center text-muted-foreground">
                            {available === true ? <Check aria-label="Included" className="mx-auto h-3.5 w-3.5 text-[hsl(var(--chart-1))]" />
                              : available === false ? <X aria-label="Not included" className="mx-auto h-3.5 w-3.5" />
                                : row[plan] ?? '—'}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-semibold text-foreground">Questions</h2>
            {data.faq.map((item, index) => (
              <div key={item.question} className="rounded-lg border border-border bg-card">
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 p-4 text-left text-sm font-medium text-foreground"
                  aria-expanded={openFaq === index}
                  onClick={() => setOpenFaq(openFaq === index ? null : index)}
                >{item.question}<ChevronDown className={cn('h-4 w-4 shrink-0 text-muted-foreground', openFaq === index && 'rotate-180')} /></button>
                {openFaq === index && <p className="border-t border-border px-4 py-3 text-sm text-muted-foreground">{item.answer}</p>}
              </div>
            ))}
          </section>
        </>
      )}
    </main>
  )
}
