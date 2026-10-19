import { cn } from '@/lib/utils'
import { formatCurrency } from '@/lib/utils'
import EmptyState from '@/components/ui/EmptyState'
import { BarChart3 } from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'

interface Props {
  equityCurve: Array<{ date: string; pnl: number; equity: number }>
  totalPnl:    number
}

export default function EquityCurve({ equityCurve, totalPnl }: Props) {
  const isNegative = totalPnl < 0
  const chartColor = isNegative ? 'hsl(var(--chart-2))' : 'hsl(var(--chart-1))'
  const gradId     = isNegative ? 'gradRed' : 'gradGreen'

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-6 py-4">
        <p className="text-sm font-semibold text-foreground">Equity Curve</p>
      </div>
      <div className="p-4 h-56">
        {equityCurve.length === 0 ? (
          <EmptyState
            icon        = {BarChart3}
            title       = "No equity data"
            description = "Close trades to see curve"
            compact
          />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={equityCurve}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={chartColor} stopOpacity={0.12} />
                  <stop offset="95%" stopColor={chartColor} stopOpacity={0}    />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray = "3 3"
                stroke          = "hsl(var(--border))"
                vertical        = {false}
              />
              <XAxis
                dataKey  = "date"
                tick     = {{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                axisLine = {false}
                tickLine = {false}
                interval = "preserveStartEnd"
              />
              <YAxis
                tick          = {{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                axisLine      = {false}
                tickLine      = {false}
                tickFormatter = {v => `$${v}`}
              />
              <Tooltip
                contentStyle = {{
                  backgroundColor: 'hsl(var(--card))',
                  border:          '1px solid hsl(var(--border))',
                  borderRadius:    '6px',
                  fontSize:        '12px',
                }}
                formatter = {(v: number) => [formatCurrency(v), 'Equity']}
              />
              <Area
                type        = "monotone"
                dataKey     = "equity"
                stroke      = {chartColor}
                strokeWidth = {1.5}
                fill        = {`url(#${gradId})`}
                dot         = {false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}