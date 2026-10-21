import { useId } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { number, words } from "../api";
const tooltip = {
  background: "hsl(var(--popover))",
  color: "hsl(var(--popover-foreground))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  fontSize: 12,
};
export function TrendChart({
  data,
  valueKey = "equity",
  label = "Net P&L",
  bars = false,
}: {
  data: any[];
  valueKey?: string;
  label?: string;
  bars?: boolean;
}) {
  const id = useId().replace(/:/g, "");
  if (!data.length)
    return (
      <div className="chart-empty">
        <span className="chart-empty-grid" />
        <strong>No recorded series yet</strong>
        <p>Charts appear when this installation stores results.</p>
      </div>
    );
  const common = (
    <>
      <CartesianGrid
        vertical={false}
        stroke="hsl(var(--border))"
        strokeDasharray="3 5"
      />
      <XAxis
        dataKey="date"
        axisLine={false}
        tickLine={false}
        tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
        minTickGap={28}
        tickFormatter={(v) => String(v).slice(5, 10)}
      />
      <YAxis
        width={45}
        axisLine={false}
        tickLine={false}
        tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }}
        tickFormatter={(v) => number(v, 0)}
      />
      <Tooltip
        contentStyle={tooltip}
        labelStyle={{ color: "hsl(var(--muted-foreground))" }}
        cursor={{ stroke: "hsl(var(--border))" }}
        formatter={(value: any) => [number(value, 4), label]}
      />
    </>
  );
  return (
    <div
      className="analytics-chart"
      role="img"
      aria-label={`${label}: ${data.length} recorded observations; latest ${number(data[data.length - 1]?.[valueKey], 4)}`}
    >
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        {bars ? (
          <BarChart
            data={data}
            margin={{ top: 16, right: 16, bottom: 0, left: 0 }}
          >
            {common}
            <Bar
              dataKey={valueKey}
              fill="hsl(var(--foreground) / .6)"
              radius={[5, 5, 0, 0]}
              maxBarSize={34}
              isAnimationActive={false}
            />
          </BarChart>
        ) : (
          <AreaChart
            data={data}
            margin={{ top: 16, right: 16, bottom: 0, left: 0 }}
          >
            <defs>
              <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor="hsl(var(--chart-3))"
                  stopOpacity={0.2}
                />
                <stop
                  offset="100%"
                  stopColor="hsl(var(--chart-3))"
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            {common}
            <Area
              type="linear"
              dataKey={valueKey}
              stroke="hsl(var(--chart-3))"
              strokeWidth={2}
              fill={`url(#${id})`}
              isAnimationActive={false}
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
export function OutcomeDonut({
  outcomes,
}: {
  outcomes: Record<string, number>;
}) {
  const entries = Object.entries(outcomes || {})
    .filter(([, n]) => n > 0)
    .map(([name, value]) => ({ name, value }));
  const total = entries.reduce((sum, e) => sum + e.value, 0);
  const colors = [
    "hsl(var(--foreground))",
    "hsl(var(--muted-foreground))",
    "hsl(var(--input))",
    "hsl(var(--border))",
    "hsl(var(--chart-3))",
  ];
  return (
    <div className="distribution">
      <div
        className="donut-wrap"
        role="img"
        aria-label={`${number(total, 0)} recorded outcomes`}
      >
        {total > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={entries}
                dataKey="value"
                nameKey="name"
                innerRadius="70%"
                outerRadius="90%"
                paddingAngle={2}
                stroke="none"
                isAnimationActive={false}
              >
                {entries.map((e, i) => (
                  <Cell key={e.name} fill={colors[i % colors.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={tooltip}
                formatter={(v: any) => number(v, 0)}
              />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-donut" />
        )}
        <div className="donut-label">
          <strong>{number(total, 0)}</strong>
          <small>Recorded</small>
        </div>
      </div>
      <div className="donut-legend">
        {entries.length ? (
          entries.map((e, i) => (
            <div key={e.name}>
              <span style={{ background: colors[i % colors.length] }} />
              <span>{words(e.name)}</span>
              <strong>{number((e.value / total) * 100, 1)}%</strong>
            </div>
          ))
        ) : (
          <p className="muted">No outcomes recorded yet.</p>
        )}
      </div>
    </div>
  );
}
