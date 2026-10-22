import { TrendChart } from "./Analytics";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Radio,
  RefreshCw,
  Check,
  AlertCircle,
  Moon,
  Sun,
} from "lucide-react";
import { useResource, number, price, time, words } from "../api";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Card, CardHeader, CardTitle } from "./ui/card";

export function Brand({ admin = false }: { admin?: boolean }) {
  return (
    <Link to="/" className="brand" aria-label="Signal Engine home">
      <span className="brand-symbol" aria-hidden="true"><span/><span/><span/></span>
      <span>Signal Engine<small>{admin ? "OPERATOR WORKSPACE" : "INDEPENDENT MARKET RESEARCH"}</small></span>
    </Link>
  );
}

export function ThemeToggle() {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  );
  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("signal-engine-theme", next ? "dark" : "light");
    } catch {
      /* Theme still works when browser storage is unavailable. */
    }
    setDark(next);
  }
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? "Use light theme" : "Use dark theme"}
      onClick={toggle}
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </Button>
  );
}

export function Panel({
  title,
  aside,
  children,
  className = "",
}: {
  title?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      {title && (
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          {aside}
        </CardHeader>
      )}
      {children}
    </Card>
  );
}

export function PageHead({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="lede">{description}</p>
      </div>
      {action}
    </header>
  );
}

export function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: ReactNode;
  note: string;
}) {
  return (
    <div className="metric">
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}

export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <Radio size={25} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

export function Resource({
  resource,
  children,
}: {
  resource: ReturnType<typeof useResource>;
  children: ReactNode;
}) {
  if (resource.loading)
    return (
      <div className="loading" role="status">
        <div className="skeleton-stack" aria-label="Loading service data">
          <span className="skeleton" />
          <span className="skeleton" />
          <span className="skeleton" />
        </div>
      </div>
    );
  if (resource.error)
    return (
      <div className="error-state" role="alert">
        <AlertCircle size={20} />
        <div>
          <strong>Data is unavailable</strong>
          <p>{resource.error.message}</p>
        </div>
        <Button variant="outline" size="sm" onClick={resource.refresh}>
          Retry
        </Button>
      </div>
    );
  return <>{children}</>;
}

export function Refresh({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="outline" size="sm" onClick={onClick}>
      <RefreshCw size={14} /> Refresh
    </Button>
  );
}

export function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export function DataTable({
  rows,
  columns,
  empty = "No records yet",
}: {
  rows: any[];
  columns: { label: string; key: string; render?: (r: any) => ReactNode }[];
  empty?: string;
}) {
  if (!rows?.length)
    return (
      <Empty title={empty}>
        Records will appear here when the connected service produces them.
      </Empty>
    );
  return (
    <div
      className="table-scroll"
      role="region"
      aria-label="Scrollable data table"
      tabIndex={0}
    >
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.id ?? row.coin ?? i}>
              {columns.map((c) => (
                <td key={c.key}>
                  {c.render ? c.render(row) : words(row[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OutcomeBars({
  outcomes,
}: {
  outcomes: Record<string, number>;
}) {
  const pairs = Object.entries(outcomes || {}),
    max = Math.max(1, ...pairs.map((p) => p[1]));
  return pairs.length ? (
    <div className="outcome-bars">
      {pairs.map(([key, count]) => {
        const tone = /target|profit|win|tp/i.test(key)
          ? "positive"
          : /stop|loss|sl/i.test(key)
            ? "negative"
            : "neutral";
        return (
          <div key={key} className={tone}>
            <span>{words(key)}</span>
            <div className="bar-track">
              <span style={{ width: Math.max(2, (count / max) * 100) + "%" }} />
            </div>
            <strong>{number(count, 0)}</strong>
          </div>
        );
      })}
    </div>
  ) : (
    <Empty title="No recorded outcomes">
      A complete history will appear after signals are persisted and tracked.
    </Empty>
  );
}

export const signalColumns = [
  {
    key: "coin",
    label: "Instrument",
    render: (r: any) => (
      <Link className="instrument" to={"/signals/" + r.id}>
        <span className="coin-icon">{r.coin?.slice(0, 1)}</span>
        {r.coin}
        <small>USDT PERP</small>
        <ArrowUpRight size={14} />
      </Link>
    ),
  },
  {
    key: "direction",
    label: "Direction",
    render: (r: any) => (
      <Badge tone={r.direction === "LONG" ? "green" : "red"}>
        {r.direction}
      </Badge>
    ),
  },
  {
    key: "grade",
    label: "Grade / score",
    render: (r: any) => (
      <span className="grade">
        {r.grade}
        <small>{number(r.score, 0)} / 100</small>
      </span>
    ),
  },
  {
    key: "entry",
    label: "Model entry",
    render: (r: any) => <span className="numeric">{price(r.entry)}</span>,
  },
  {
    key: "outcome",
    label: "State",
    render: (r: any) => <Badge>{words(r.outcome)}</Badge>,
  },
  {
    key: "timestamp",
    label: "Generated",
    render: (r: any) => (
      <span className="muted nowrap">{time(r.timestamp)}</span>
    ),
  },
];

export function Trace({ steps }: { steps: any[] }) {
  return (
    <ol className="decision-steps">
      {steps.map((step, i) => (
        <li key={i}>
          <span
            className={
              "step-icon " +
              (step.passed === false || step.result === "STOPPED"
                ? "failed"
                : "")
            }
          >
            <Check size={13} />
          </span>
          <div>
            <strong>{words(step.node || step.name)}</strong>
            <p>
              {step.reason
                ? words(step.reason)
                : step.label ||
                  step.grade ||
                  step.direction ||
                  step.result ||
                  "Evaluated"}
            </p>
          </div>
          {step.score != null && (
            <span className="numeric">{number(step.score, 0)}</span>
          )}
        </li>
      ))}
    </ol>
  );
}

export function EquityCurve({ points }: { points: any[] }) {
  const valid = points.filter((p) => Number.isFinite(Number(p.equity)));
  return (
    <>
      <TrendChart data={valid} />
      <p className="panel-note">
        Cumulative recorded closed-trade P&L. Hover or tap the chart to inspect
        observations.
      </p>
    </>
  );
}

export function JourneyChart({ points }: { points: any[] }) {
  const valid = points.filter((p) => Number.isFinite(Number(p.price)));
  if (!valid.length)
    return (
      <Empty title="No journey points recorded">
        The monitor stores price snapshots while the trade is open. This trade
        has no journey points yet.
      </Empty>
    );
  const first = valid[0],
    levels = [
      { key: "entry", value: Number(first.entry_price) },
      { key: "stop", value: Number(first.sl_price) },
      { key: "target", value: Number(first.tp_price) },
    ].filter((level) => Number.isFinite(level.value) && level.value > 0);
  const width = 680,
    height = 240,
    pad = 20,
    values = [
      ...valid.map((p) => Number(p.price)),
      ...levels.map((level) => level.value),
    ],
    min = Math.min(...values),
    max = Math.max(...values),
    span = Math.max(max - min, Math.abs(max) * 0.0001, 0.000001),
    coords = valid.map((p, i) => ({
      x: pad + (i / Math.max(valid.length - 1, 1)) * (width - 2 * pad),
      y: height - pad - ((Number(p.price) - min) / span) * (height - 2 * pad),
      point: p,
    })),
    path = coords.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" ");
  return (
    <div className="journey-chart-wrap">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Trade price journey chart"
      >
        <line
          x1={pad}
          x2={width - pad}
          y1={height - pad}
          y2={height - pad}
          className="chart-zero"
        />
        {levels.map((level) => {
          const y =
            height - pad - ((level.value - min) / span) * (height - 2 * pad);
          return (
            <line
              key={level.key}
              x1={pad}
              x2={width - pad}
              y1={y}
              y2={y}
              className={`journey-level journey-level-${level.key}`}
            />
          );
        })}
        <path d={path} className="chart-line" />
        {coords
          .filter((p) => p.point.is_entry || p.point.is_exit)
          .map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r="5"
              className={p.point.is_exit ? "journey-exit" : "journey-entry"}
            />
          ))}
      </svg>
      <div className="chart-caption">
        <span>{time(valid[0]?.timestamp)}</span>
        <span>{time(valid[valid.length - 1]?.timestamp)}</span>
      </div>
      <div className="journey-stats">
        <span>Entry {price(valid[0]?.entry_price)}</span>
        <span>Stop {price(valid[0]?.sl_price)}</span>
        <span>Target {price(valid[0]?.tp_price)}</span>
        <span>Latest {price(valid[valid.length - 1]?.price)}</span>
      </div>
    </div>
  );
}
