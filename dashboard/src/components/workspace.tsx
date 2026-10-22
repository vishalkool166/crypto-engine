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
  onRowClick,
}: {
  rows: any[];
  columns: { label: string; key: string; render?: (r: any) => ReactNode }[];
  empty?: string;
  onRowClick?: (r: any) => void;
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
            <tr key={row.id ?? row.coin ?? i}
              className={onRowClick ? "interactive-tr" : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              aria-label={onRowClick ? `Inspect ${row.coin || row.symbol || "trade"} details` : undefined}
              onClick={onRowClick ? (ev) => { if (!(ev.target as HTMLElement).closest("button,a,input,select,textarea")) onRowClick(row); } : undefined}
              onKeyDown={onRowClick ? (ev) => { if ((ev.key === "Enter" || ev.key === " ") && ev.target === ev.currentTarget) {ev.preventDefault();onRowClick(row);} } : undefined}>
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
  const [hover,setHover] = useState<number | null>(null);
  const [windowSize,setWindowSize] = useState<'all'|'50'|'20'>('all');
  const valid = points.filter((p) => Number.isFinite(Number(p.price)) && Number(p.price) > 0);
  const sliced = windowSize === 'all' ? valid : valid.slice(-Number(windowSize));
  if (!valid.length) return <Empty title="No journey points recorded">The monitor records price snapshots while the trade is open. Historical price-path evidence is not yet available for this position.</Empty>;
  const first=valid[0], last=sliced[sliced.length-1];
  const levels=[{key:'entry',value:Number(first.entry_price)},{key:'stop',value:Number(first.sl_price)},{key:'target',value:Number(first.tp_price)}].filter(l=>Number.isFinite(l.value)&&l.value>0);
  const width=680,height=278,padX=44,padY=27;
  const values=[...sliced.map(p=>Number(p.price)),...levels.map(l=>l.value)];
  const min=Math.min(...values),max=Math.max(...values),span=Math.max(max-min,Math.abs(max)*0.0001,0.000001);
  const yOf=(v:number)=>height-padY-(v-min)/span*(height-2*padY);
  const coords=sliced.map((p,i)=>({x:padX+i/Math.max(sliced.length-1,1)*(width-2*padX),y:yOf(Number(p.price)),point:p}));
  const path=coords.map((c,i)=>`${i?'L':'M'}${c.x},${c.y}`).join(' ');
  const current=hover==null?null:coords[Math.max(0,Math.min(hover,coords.length-1))];
  return <div className="journey-chart-wrap" aria-label="Interactive stored price journey">
    <div className="journey-chart-toolbar"><span>Recorded mark path · {valid.length} observations</span><div role="group" aria-label="Price path window">{(['all','50','20'] as const).map(w=><button key={w} type="button" aria-pressed={windowSize===w} className={windowSize===w?'selected':''} onClick={()=>{setWindowSize(w);setHover(null)}}>{w==='all'?'All':`Last ${w}`}</button>)}</div></div>
    <svg viewBox={`0 0 ${width} ${height}`} className="journey-interactive-svg" role="img" aria-label="Price path with stop, entry, target and pointer inspection"
       onPointerMove={e=>{const r=e.currentTarget.getBoundingClientRect();const x=(e.clientX-r.left)/r.width*width;setHover(Math.round((x-padX)/((width-2*padX)/Math.max(coords.length-1,1))));}}
       onPointerLeave={()=>setHover(null)}>
      {[0,.25,.5,.75,1].map(t=><g key={t}><line x1={padX} x2={width-padX} y1={padY+t*(height-2*padY)} y2={padY+t*(height-2*padY)} className="journey-grid"/><text x="2" y={padY+t*(height-2*padY)+4} className="journey-axis">{price(max-t*span)}</text></g>)}
      {levels.map(l=><g key={l.key}><line x1={padX} x2={width-padX} y1={yOf(l.value)} y2={yOf(l.value)} className={`journey-level journey-level-${l.key}`}/><text x={width-padX-4} y={yOf(l.value)-5} textAnchor="end" className={`journey-level-label ${l.key}`}>{l.key.toUpperCase()} {price(l.value)}</text></g>)}
      <path d={path} className="journey-animated-path"/>
      {coords.filter(c=>c.point.is_entry||c.point.is_exit).map((c,i)=><circle key={i} cx={c.x} cy={c.y} r="5" className={c.point.is_exit?'journey-exit':'journey-entry'}/>)}
      {current&&<g><line x1={current.x} x2={current.x} y1={padY} y2={height-padY} className="journey-crosshair"/><circle cx={current.x} cy={current.y} r="5" className="journey-hover-dot"/></g>}
    </svg>
    <div className="journey-chart-inspector" aria-live="off"><span>{current?time(current.point.timestamp):`${time(sliced[0].timestamp)} → ${time(last.timestamp)}`}</span><strong>{current?price(current.point.price):`Last ${price(last.price)}`}</strong></div>
    <div className="journey-stats">{levels.map(l=><span key={l.key}>{l.key} {price(l.value)}</span>)}<span>Current {price(last.price)}</span></div>
    <p className="journey-caveat">Each point is a stored price observation, not a reconstructed tick-by-tick execution path. Hover to inspect; choose a time window above.</p>
  </div>;
}
