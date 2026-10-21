import { useEffect, useId, useState } from "react";
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

function useChartMotion() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: no-preference)");
    const update = () => setEnabled(preference.matches);
    update();
    preference.addEventListener?.("change", update);
    return () => preference.removeEventListener?.("change", update);
  }, []);
  return enabled;
}

function outcomeColor(name: string, index: number) {
  const key = name.toLowerCase();
  if (/(win|profit|positive)/.test(key)) return "hsl(var(--chart-1))";
  if (/(loss|negative|stop)/.test(key)) return "hsl(var(--destructive))";
  if (/(break|timeout|pending|neutral)/.test(key)) return "hsl(var(--muted-foreground))";
  return ["hsl(var(--chart-3))", "hsl(var(--info))", "hsl(var(--chart-4))"][index % 3];
}
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
  const animate = useChartMotion();
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
      data-chart-reveal
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
              fill="hsl(var(--chart-1))"
              radius={[5, 5, 0, 0]}
              maxBarSize={34}
              isAnimationActive={false}
            >
              {data.map((point, index) => (
                <Cell key={`${point.date || index}`} fill={outcomeColor(Number(point[valueKey]) < 0 ? "loss" : "win", index)} />
              ))}
            </Bar>
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
                  stopColor={Number(data[data.length - 1]?.[valueKey]) < 0 ? "hsl(var(--destructive))" : "hsl(var(--chart-1))"}
                  stopOpacity={0.2}
                />
                <stop
                  offset="100%"
                  stopColor={Number(data[data.length - 1]?.[valueKey]) < 0 ? "hsl(var(--destructive))" : "hsl(var(--chart-1))"}
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            {common}
            <Area
              type="linear"
              dataKey={valueKey}
              stroke={Number(data[data.length - 1]?.[valueKey]) < 0 ? "hsl(var(--destructive))" : "hsl(var(--chart-1))"}
              strokeWidth={2.25}
              fill={`url(#${id})`}
              isAnimationActive={false}
              className={animate ? "analytics-area-curve" : undefined}
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
  const animate = useChartMotion();
  const entries = Object.entries(outcomes || {})
    .filter(([, n]) => n > 0)
    .map(([name, value]) => ({ name, value }));
  const total = entries.reduce((sum, e) => sum + e.value, 0);
  return (
    <div className="distribution">
      <div
        className="donut-wrap"
        data-chart-reveal
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
                isAnimationActive={animate}
                animationBegin={90}
                animationDuration={650}
                animationEasing="ease-out"
              >
                {entries.map((e, i) => (
                  <Cell key={e.name} fill={outcomeColor(e.name, i)} />
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
              <span style={{ background: outcomeColor(e.name, i) }} />
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
