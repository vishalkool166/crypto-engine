import {
  lazy,
  Suspense,
  useState,
  useEffect,
  type ReactNode,
  type FormEvent,
} from "react";
import {
  Routes,
  Route,
  NavLink,
  Link,
  useParams,
  useLocation,
  Navigate,
} from "react-router-dom";
import {
  ArrowUpRight,
  ArrowRight,
  ArrowLeft,
  Activity,
  Layers3,
  Radio,
  ShieldCheck,
  FlaskConical,
  Globe2,
  Settings2,
  Send,
  Menu,
  X,
  RefreshCw,
  LogOut,
  Check,
  AlertCircle,
  ChevronRight,
  ExternalLink,
  BookOpen,
  Wallet,
  Database,
  ScrollText,
  Moon,
  Sun,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import {
  request,
  useResource,
  useConnection,
  number,
  price,
  time,
  words,
  ApiError,
} from "./api";
const PWA =
  __APP_TARGET__ === "public" ? lazy(() => import("./PWA")) : () => null;
const ADMIN = __APP_TARGET__ === "admin";
const base = "/api/v1/admin";

function Brand({ admin = false }: { admin?: boolean }) {
  return (
    <Link to="/" className="brand" aria-label="Signal Engine home">
      <span className="brand-symbol">
        <span />
        <span />
        <span />
      </span>
      <span>
        Signal Engine
        <small>{admin ? "OPERATOR CONSOLE" : "MARKET RESEARCH"}</small>
      </span>
    </Link>
  );
}
function ThemeToggle() {
  const [dark, setDark] = useState(
    () => localStorage.getItem("signal-engine-theme") !== "light",
  );
  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("signal-engine-theme", next ? "dark" : "light");
    setDark(next);
  }
  return (
    <Button variant="ghost" size="icon" aria-label={dark ? "Use light theme" : "Use dark theme"} onClick={toggle}>
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </Button>
  );
}
function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={"badge badge-" + tone}>{children}</span>;
}
function Panel({
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
    <section className={"panel " + className}>
      {title && (
        <div className="panel-heading">
          <h2>{title}</h2>
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}
function PageHead({
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
function Metric({
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
function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <Radio size={25} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Resource({
  resource,
  children,
}: {
  resource: ReturnType<typeof useResource>;
  children: ReactNode;
}) {
  if (resource.loading)
    return (
      <div className="loading" role="status">
        <span className="spinner" />
        Loading service data
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
function Refresh({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="outline" size="sm" onClick={onClick}>
      <RefreshCw size={14} /> Refresh
    </Button>
  );
}
function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
function DataTable({
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
    <div className="table-scroll">
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
function OutcomeBars({ outcomes }: { outcomes: Record<string, number> }) {
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
        return <div key={key} className={tone}>
          <span>{words(key)}</span>
          <div className="bar-track">
            <span style={{ width: Math.max(2, (count / max) * 100) + "%" }} />
          </div>
          <strong>{number(count, 0)}</strong>
        </div>;
      })}
    </div>
  ) : (
    <Empty title="No recorded outcomes">
      A complete history will appear after signals are persisted and tracked.
    </Empty>
  );
}
const signalColumns = [
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
function PublicOverview() {
  const r = useResource("/api/v1/public/overview"),
    d = r.data;
  return (
    <>
      <PageHead
        eyebrow="AN OPEN RESEARCH WORKSPACE"
        title="The market, with a record."
        description="Follow a defined signal strategy. Inspect the levels, understand the rules, and see the recorded outcomes."
        action={<Badge tone="amber">Paper environment</Badge>}
      />
      <Resource resource={r}>
        <div className="hero-grid">
          <section className="research-intro">
            <div className="intro-number">01 / OBSERVE</div>
            <h2>
              Every setup starts
              <br />
              with a reason.
            </h2>
            <p>
              A transparent view of the engine’s crypto futures research.
              Signals use closed candles, a defined scoring model, and explicit
              risk levels.
            </p>
            <Link className="text-link" to="/signals">
              Explore the signal ledger <ArrowRight size={16} />
            </Link>
            <div className="intro-bottom">
              <span className="pulse-dot" />
              {d ? words(d.status) : "Unavailable"}
              <span>Last scan {time(d?.last_scan_at)}</span>
            </div>
          </section>
          <Panel
            title="Research snapshot"
            aside={<Refresh onClick={r.refresh} />}
          >
            <div className="metric-grid">
              <Metric
                label="Configured instruments"
                value={d ? number(d.universe.length, 0) : "—"}
                note="USDⓈ-M perpetual futures"
              />
              <Metric
                label="Persisted signals"
                value={d ? number(d.signal_count, 0) : "—"}
                note="Recorded by this installation"
              />
              <Metric
                label="Strategy evidence"
                value="Not evaluated"
                note="No verified profitability claim"
              />
              <Metric
                label="Data freshness"
                value={
                  d?.data_age_seconds != null
                    ? number(d.data_age_seconds / 60, 0) + " min"
                    : "Awaiting scan"
                }
                note="Time since last completed scan"
              />
            </div>
            <div className="universe-strip">
              {d?.universe?.map((coin: string) => (
                <span key={coin}>{coin}</span>
              ))}
            </div>
          </Panel>
        </div>
        <Panel
          title="Latest signal records"
          aside={
            <Link className="text-link" to="/signals">
              Full ledger <ArrowUpRight size={14} />
            </Link>
          }
        >
          <DataTable rows={d?.signals || []} columns={signalColumns} />
        </Panel>
        <div className="two-column">
          <Panel title="How a decision is formed">
            <ol className="method-list">
              <li>
                <span>01</span>
                <div>
                  <strong>Market regime and direction</strong>
                  <p>Volatility, ADX, and higher-timeframe moving averages.</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <strong>A defined confluence score</strong>
                  <p>
                    ADX, RSI, and relative volume contribute up to 100 points.
                  </p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <strong>Risk levels and paper observation</strong>
                  <p>
                    Stops and targets are recorded; account-specific sizing
                    stays private.
                  </p>
                </div>
              </li>
            </ol>
            <Link className="text-link panel-footer" to="/methodology">
              Read the methodology <ArrowRight size={15} />
            </Link>
          </Panel>
          <Panel title="Recorded outcome distribution">
            <OutcomeBars outcomes={d?.recorded_outcomes} />
            <p className="panel-note">
              Outcome labels describe recorded signals. They do not establish
              realized net returns.
            </p>
          </Panel>
        </div>
      </Resource>
    </>
  );
}
function SignalList() {
  const [coin, setCoin] = useState(""),
    [grade, setGrade] = useState(""),
    [offset, setOffset] = useState(0),
    [filter, setFilter] = useState("");
  const r = useResource(
    "/api/v1/public/signals?limit=20&offset=" +
      offset +
      "&coin=" +
      encodeURIComponent(filter) +
      "&grade=" +
      encodeURIComponent(grade),
  );
  const traces = useResource(ADMIN ? base + "/engine/traces?limit=20" : null);
  return (
    <>
      <PageHead
        eyebrow="SIGNAL LEDGER"
        title={ADMIN ? "Decisions, in view." : "Inspect the setup."}
        description="Timestamped model outputs with recorded levels and outcomes. These are paper-research signals, not execution instructions."
        action={
          <Refresh
            onClick={() => {
              r.refresh();
              traces.refresh();
            }}
          />
        }
      />
      <Panel>
        <form
          className="filters"
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            setFilter(coin.toUpperCase().trim());
          }}
        >
          <label>
            Instrument
            <input
              value={coin}
              maxLength={12}
              onChange={(e) => setCoin(e.target.value)}
              placeholder="Search symbol"
              aria-label="Filter by instrument"
            />
          </label>
          <label>
            Grade
            <select
              value={grade}
              onChange={(e) => {
                setGrade(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All grades</option>
              <option>A+</option>
              <option>A</option>
              <option>B</option>
              <option>F</option>
            </select>
          </label>
          <Button variant="outline" type="submit">
            Apply filter
          </Button>
          <span className="muted">
            {r.data ? number(r.data.total, 0) + " records" : ""}
          </span>
        </form>
        <Resource resource={r}>
          <DataTable rows={r.data?.items || []} columns={signalColumns} />
          <div className="pagination">
            <span>Page {offset / 20 + 1}</span>
            <div>
              <Button
                variant="ghost"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset((v) => Math.max(0, v - 20))}
              >
                <ArrowLeft size={14} />
                Previous
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={!r.data || offset + 20 >= r.data.total}
                onClick={() => setOffset((v) => v + 20)}
              >
                Next
                <ArrowRight size={14} />
              </Button>
            </div>
          </div>
        </Resource>
      </Panel>
      {ADMIN && (
        <Panel title="Recent decision traces">
          <Resource resource={traces}>
            {traces.data?.traces?.length ? (
              <div className="trace-list">
                {traces.data.traces.map((trace: any, i: number) => (
                  <details key={i}>
                    <summary>
                      <strong>{trace.coin}</strong>
                      <Badge>{words(trace.final_decision)}</Badge>
                      <span>
                        {trace.stopped_at
                          ? words(trace.stopped_at)
                          : trace.final_grade}
                      </span>
                      <small>{time(trace.datetime || trace.timestamp)}</small>
                    </summary>
                    <Trace steps={trace.steps || []} />
                  </details>
                ))}
              </div>
            ) : (
              <Empty title="No decision traces recorded">
                New scans will record approvals and rejections here.
              </Empty>
            )}
          </Resource>
        </Panel>
      )}
    </>
  );
}
function Trace({ steps }: { steps: any[] }) {
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
function SignalDetail() {
  const { id } = useParams(),
    r = useResource("/api/v1/public/signals/" + id),
    d = r.data;
  return (
    <>
      <Link className="text-link back-link" to="/signals">
        <ArrowLeft size={14} /> Signal ledger
      </Link>
      <PageHead
        eyebrow={"RECORD / " + id}
        title={d ? d.coin + " · " + d.direction : "Signal record"}
        description="Persisted model levels at generation time. Prices may have changed since this record was created."
        action={
          d && <Badge>{d.grade + " · " + number(d.score, 0) + "/100"}</Badge>
        }
      />
      <Resource resource={r}>
        <div className="two-column">
          <Panel title="Signal specification">
            <dl className="facts">
              <Fact label="Generated" value={time(d?.timestamp)} />
              <Fact label="Model entry" value={price(d?.entry)} />
              <Fact label="Stop level" value={price(d?.sl)} />
              <Fact label="Target 1" value={price(d?.tp1)} />
              <Fact label="Target 2" value={price(d?.tp2)} />
              <Fact
                label="Recorded outcome"
                value={<Badge>{words(d?.outcome)}</Badge>}
              />
              <Fact
                label="Strategy version"
                value={d?.system_version || "Not recorded"}
              />
            </dl>
          </Panel>
          <Panel title="Decision trace">
            {d?.trace?.length ? (
              <Trace steps={d.trace} />
            ) : (
              <Empty title="Trace not recorded">
                Earlier records may predate persisted decision traces. No
                reconstructed trace is substituted.
              </Empty>
            )}
          </Panel>
        </div>
        <div className="notice">
          <FlaskConical size={20} />
          <p>
            Grades represent a rule-based score. They are not a measured
            probability of a profitable trade. The strategy has not completed
            out-of-sample validation.
          </p>
        </div>
      </Resource>
    </>
  );
}
function Methodology() {
  return (
    <>
      <PageHead
        eyebrow="METHOD & LIMITATIONS"
        title="Rules you can inspect."
        description="The current crypto pipeline is deterministic. The dashboard describes the active rules without attributing unmeasured predictive confidence."
      />
      <div className="method-grid">
        {[
          {
            n: "01",
            title: "Regime",
            body: "Closed 4h candles establish volatility and ADX context. Invalid market indicators and extreme ATR-to-price ratios veto entries.",
          },
          {
            n: "02",
            title: "Direction",
            body: "Price relative to EMA200 establishes long or short bias. EMA20/EMA50 alignment and the configured per-coin ADX threshold must agree.",
          },
          {
            n: "03",
            title: "Score",
            body: "ADX contributes up to 40 points, directional RSI up to 30, and relative volume up to 30. A+ starts at 80; A at 65; B at 50.",
          },
          {
            n: "04",
            title: "Risk",
            body: "The stop is placed beyond the recent swing with a 0.5 ATR buffer. Targets are configured R multiples. Position sizing is private and subject to portfolio limits.",
          },
        ].map((m) => (
          <Panel key={m.n} className="method-card">
            <span>{m.n}</span>
            <h2>{m.title}</h2>
            <p>{m.body}</p>
          </Panel>
        ))}
      </div>
      <Panel title="What the record can establish">
        <div className="reading">
          <h3>Research status</h3>
          <p>
            The current configuration is not certified profitable. Unit tests
            verify software behavior, not trading edge. The historical research
            gate remains incomplete.
          </p>
          <h3>Required evidence</h3>
          <p>
            Contiguous candles and actual funding settlements, frozen holdouts,
            multi-fold walk-forward results, net costs and slippage sensitivity,
            and independent paper-forward reconciliation are required before
            performance claims.
          </p>
          <h3>Execution limitations</h3>
          <p>
            OHLC replay does not reconstruct tick order, limit-order queue
            position, market impact, or all portfolio-state effects. Paper
            exchange fills can differ from real execution.
          </p>
        </div>
      </Panel>
    </>
  );
}
function PublicPerformance() {
  const r = useResource("/api/v1/public/overview");
  return (
    <>
      <PageHead
        eyebrow="RECORDED EVIDENCE"
        title="Outcomes without embellishment."
        description="This page summarizes persisted signal labels. Account balances, private positions, and monetary performance are not published."
        action={<Badge tone="amber">Research incomplete</Badge>}
      />
      <Resource resource={r}>
        <div className="two-column">
          <Panel title="Signal outcomes">
            <OutcomeBars outcomes={r.data?.recorded_outcomes} />
          </Panel>
          <Panel title="Evidence status">
            <dl className="facts">
              <Fact label="Operating mode" value="Paper" />
              <Fact
                label="Persisted signal sample"
                value={number(r.data?.signal_count, 0)}
              />
              <Fact label="Out-of-sample edge" value="Not evaluated" />
              <Fact label="Live-trading approval" value="Not approved" />
            </dl>
            <Link to="/methodology" className="text-link panel-footer">
              Research methodology <ArrowUpRight size={14} />
            </Link>
          </Panel>
        </div>
      </Resource>
    </>
  );
}
function EquityCurve({ points }: { points: any[] }) {
  const valid = points.filter((p) => Number.isFinite(Number(p.equity)));
  if (valid.length < 2)
    return (
      <Empty title="Not enough closed trades for a curve">
        The curve appears after at least two closed paper trades have recorded
        their net result.
      </Empty>
    );
  const width = 720,
    height = 220,
    pad = 16,
    values = valid.map((p) => Number(p.equity)),
    min = Math.min(0, ...values),
    max = Math.max(0, ...values),
    span = Math.max(max - min, 1),
    coords = values.map((value, i) => ({
      x: pad + (i / Math.max(values.length - 1, 1)) * (width - 2 * pad),
      y: height - pad - ((value - min) / span) * (height - 2 * pad),
    })),
    path = coords.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" ");
  return (
    <div className="equity-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Cumulative net paper trade equity curve"
        preserveAspectRatio="none"
      >
        <line
          x1={pad}
          x2={width - pad}
          y1={height - pad - ((0 - min) / span) * (height - 2 * pad)}
          y2={height - pad - ((0 - min) / span) * (height - 2 * pad)}
          className="chart-zero"
        />
        <path d={path} className="chart-line" />
      </svg>
      <div className="chart-caption">
        <span>{valid[0]?.date || "First recorded close"}</span>
        <span>{valid[valid.length - 1]?.date || "Latest close"}</span>
      </div>
    </div>
  );
}
function AdminPerformance() {
  const perf = useResource(base + "/dashboard/performance"),
    byCoin = useResource(base + "/trades/performance"),
    history = useResource(base + "/dashboard/history?limit=100"),
    signals = useResource(base + "/signals?limit=100"),
    context = useResource(base + "/performance/context");
  const p = perf.data || {},
    historyRows = Array.isArray(history.data) ? history.data : [];
  return (
    <>
      <PageHead
        eyebrow="PRIVATE PERFORMANCE RECORD"
        title="See what the closed trades say."
        description="This page reports recorded paper results. Metrics use stored net P&L where available and do not establish a profitable strategy."
        action={
          <Refresh
            onClick={() => {
              perf.refresh();
              byCoin.refresh();
              history.refresh();
              signals.refresh();
              context.refresh();
            }}
          />
        }
      />
      <Resource resource={perf}>
        <div className="metric-grid performance-metrics">
          <Metric label="Closed trades" value={number(p.closed, 0)} note="Wins and losses recorded" />
          <Metric label="Win rate" value={`${number(p.win_rate, 1)}%`} note={`${number(p.wins, 0)} wins · ${number(p.losses, 0)} losses`} />
          <Metric label="Net P&L" value={number(p.total_pnl, 4)} note="Recorded closed-trade net result" />
          <Metric label="Profit factor" value={number(p.profit_factor, 2)} note="Gross profit ÷ gross loss" />
          <Metric label="Maximum drawdown" value={`${number(p.max_drawdown, 2)}%`} note="Calculated from cumulative closed-trade P&L" />
          <Metric label="Best trade" value={number(p.best_trade, 4)} note={p.best_trade_coin || "No trade recorded"} />
        </div>
        <div className="two-column performance-grid">
          <Panel title="Cumulative net P&L">
            <EquityCurve points={p.equity_curve || []} />
          </Panel>
          <Panel title="Performance by signal grade">
            <DataTable
              rows={[
                { grade: "A+", ...(p.aplus || {}) },
                { grade: "A", ...(p.a || {}) },
                { grade: "B", ...(p.b || {}) },
              ]}
              columns={[
                { key: "grade", label: "Grade" },
                { key: "total", label: "Closed" },
                { key: "wins", label: "Wins" },
                { key: "win_rate", label: "Win rate", render: (r) => `${number(r.win_rate, 1)}%` },
                { key: "pnl", label: "Net P&L", render: (r) => number(r.pnl, 4) },
              ]}
            />
          </Panel>
        </div>
        <Panel title="Results by instrument">
          <Resource resource={byCoin}>
            <DataTable
              rows={Array.isArray(byCoin.data) ? byCoin.data : []}
              columns={[
                { key: "coin", label: "Instrument" },
                { key: "wins", label: "Wins" },
                { key: "losses", label: "Losses" },
                { key: "win_rate", label: "Win rate", render: (r) => `${number(r.win_rate, 1)}%` },
                { key: "profit_abs", label: "Net P&L", render: (r) => number(r.profit_abs, 4) },
                { key: "commission", label: "Fees", render: (r) => number(r.commission, 4) },
                { key: "funding", label: "Funding", render: (r) => number(r.funding, 4) },
              ]}
            />
          </Resource>
        </Panel>
        <div className="two-column">
          <Panel title="Performance by system version">
            <Resource resource={context}>
              <DataTable
                rows={context.data?.by_version || []}
                columns={[
                  { key: "system_version", label: "Version" },
                  { key: "total", label: "Trades" },
                  { key: "win_rate", label: "Win rate", render: (row) => `${number(row.win_rate, 1)}%` },
                  { key: "pnl", label: "Net P&L", render: (row) => number(row.pnl, 4) },
                ]}
                empty="No closed trades have a recorded system version"
              />
            </Resource>
          </Panel>
          <Panel title="Performance by market regime">
            <Resource resource={context}>
              <DataTable
                rows={context.data?.by_regime || []}
                columns={[
                  { key: "regime_at_entry", label: "Regime", render: (row) => words(row.regime_at_entry) },
                  { key: "total", label: "Trades" },
                  { key: "win_rate", label: "Win rate", render: (row) => `${number(row.win_rate, 1)}%` },
                  { key: "pnl", label: "Net P&L", render: (row) => number(row.pnl, 4) },
                ]}
                empty="No closed trades have a recorded market regime"
              />
            </Resource>
          </Panel>
        </div>
        <Panel title="Factor observations">
          <Resource resource={context}>
            <p className="panel-note">{context.data?.factor_note || "Descriptive averages from stored factor scores."}</p>
            <DataTable
              rows={context.data?.factors || []}
              columns={[
                { key: "factor", label: "Factor" },
                { key: "observations", label: "Observations" },
                { key: "mean_score_wins", label: "Mean score · wins", render: (row) => row.mean_score_wins == null ? "—" : number(row.mean_score_wins, 3) },
                { key: "mean_score_losses", label: "Mean score · losses", render: (row) => row.mean_score_losses == null ? "—" : number(row.mean_score_losses, 3) },
                { key: "score_difference", label: "Difference", render: (row) => row.score_difference == null ? "—" : number(row.score_difference, 3) },
              ]}
              empty="No numeric factor scores are stored with closed signal outcomes"
            />
          </Resource>
        </Panel>
        <Panel title="Recent closed trades">
          <Resource resource={history}>
            <DataTable
              rows={historyRows}
              columns={[
                { key: "coin", label: "Instrument" },
                { key: "direction", label: "Side" },
                { key: "grade", label: "Grade" },
                { key: "outcome", label: "Outcome" },
                { key: "pnl", label: "Net P&L", render: (r) => number(r.pnl, 4) },
                { key: "timestamp", label: "Opened", render: (r) => time(r.timestamp) },
              ]}
            />
          </Resource>
        </Panel>
        <Panel title="Recent signal history" aside={<Link className="panel-link" to="/signals">Open signal ledger</Link>}>
          <Resource resource={signals}>
            <DataTable
              rows={Array.isArray(signals.data) ? signals.data : []}
              columns={[
                { key: "timestamp", label: "Time", render: (row) => time(row.timestamp) },
                { key: "coin", label: "Instrument", render: (row) => <strong>{row.coin}</strong> },
                { key: "direction", label: "Side" },
                { key: "grade", label: "Grade" },
                { key: "score", label: "Score", render: (row) => number(row.score, 1) },
                { key: "outcome", label: "Outcome", render: (row) => words(row.outcome) },
                { key: "pnl", label: "Recorded P&L", render: (row) => row.pnl == null ? "—" : number(row.pnl, 4) },
              ]}
              empty="No signals have been recorded"
            />
          </Resource>
        </Panel>
        <Panel title="Cached-data backtests">
          <p className="panel-note">Run and review research backtests from the Research page. Backtests use stored market data and do not place orders.</p>
          <Button asChild variant="outline"><Link to="/research">Open Research</Link></Button>
        </Panel>
      </Resource>
    </>
  );
}
function JourneyChart({ points }: { points: any[] }) {
  const valid = points.filter((p) => Number.isFinite(Number(p.price)));
  if (!valid.length)
    return <Empty title="No journey points recorded">The monitor stores price snapshots while the trade is open. This trade has no journey points yet.</Empty>;
  const first = valid[0],
    levels = [
      { key: "entry", value: Number(first.entry_price) },
      { key: "stop", value: Number(first.sl_price) },
      { key: "target", value: Number(first.tp_price) },
    ].filter((level) => Number.isFinite(level.value) && level.value > 0);
  const width = 680,
    height = 240,
    pad = 20,
    values = [...valid.map((p) => Number(p.price)), ...levels.map((level) => level.value)],
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
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Trade price journey chart">
        <line x1={pad} x2={width - pad} y1={height - pad} y2={height - pad} className="chart-zero" />
        {levels.map((level) => {
          const y = height - pad - ((level.value - min) / span) * (height - 2 * pad);
          return <line key={level.key} x1={pad} x2={width - pad} y1={y} y2={y} className={`journey-level journey-level-${level.key}`} />;
        })}
        <path d={path} className="chart-line" />
        {coords.filter((p) => p.point.is_entry || p.point.is_exit).map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="5" className={p.point.is_exit ? "journey-exit" : "journey-entry"} />
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
function PublicStatus() {
  const r = useResource("/api/v1/public/status");
  return (
    <>
      <PageHead
        eyebrow="SERVICE STATUS"
        title="A clear operational record."
        description="A minimal public health surface. Infrastructure details and account connections remain private."
        action={<Refresh onClick={r.refresh} />}
      />
      <Resource resource={r}>
        <Panel title="Signal service">
          <dl className="facts">
            <Fact
              label="Current state"
              value={
                <Badge
                  tone={r.data?.status === "operational" ? "green" : "amber"}
                >
                  {words(r.data?.status)}
                </Badge>
              }
            />
            <Fact
              label="Last completed scan"
              value={time(r.data?.last_scan_at)}
            />
            <Fact
              label="Data age"
              value={
                r.data?.data_age_seconds == null
                  ? "Not available"
                  : number(r.data.data_age_seconds, 0) + " seconds"
              }
            />
            <Fact label="Mode" value="Paper" />
            <Fact label="Observed at" value={time(r.data?.timestamp)} />
          </dl>
        </Panel>
      </Resource>
    </>
  );
}
function AdminOverview() {
  const r = useResource(base + "/overview"),
    d = r.data;
  const [pending, setPending] = useState(false),
    [message, setMessage] = useState("");
  async function scan() {
    setPending(true);
    setMessage("");
    try {
      const result = await request(base + "/scan", { method: "POST" });
      setMessage(
        "Scan completed: " + result.analyzed + " instruments analyzed.",
      );
      r.refresh();
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHead
        eyebrow="OPERATOR OVERVIEW"
        title="Keep the engine accountable."
        description="Private operational state, paper-trade results, and the checks that govern this installation."
        action={
          <Button
            disabled={pending || d?.health?.runtime !== "running"}
            onClick={scan}
          >
            <Radio size={15} />
            {pending ? "Scanning…" : "Run scan"}
          </Button>
        }
      />
      {message && (
        <div role="status" className="notice">
          {message}
        </div>
      )}
      <Resource resource={r}>
        <div className="metric-band">
          <Metric
            label="Paper P&L today"
            value={number(d?.summary?.today_pnl) + " USDT"}
            note="Reported by the private paper ledger"
          />
          <Metric
            label="Signals recorded"
            value={number(d?.summary?.total_signals, 0)}
            note="All persisted signal records"
          />
          <Metric
            label="Engine runtime"
            value={words(d?.health?.runtime)}
            note="Startup reconciliation state"
          />
          <Metric
            label="Redis"
            value={words(d?.health?.checks?.redis)}
            note="Bounded connection probe"
          />
        </div>
        <div className="two-column">
          <Panel title="Operational checks">
            <dl className="facts">
              {Object.entries(d?.health?.checks || {}).map(([k, v]) => (
                <Fact
                  key={k}
                  label={words(k)}
                  value={
                    <Badge tone={v === "connected" ? "green" : "red"}>
                      {String(v)}
                    </Badge>
                  }
                />
              ))}
              <Fact
                label="Last scan"
                value={time(d?.health?.scan?.last_scan_at)}
              />
              <Fact
                label="Paper credentials"
                value={
                  d?.health?.integrations?.binance_demo
                    ? "Configured"
                    : "Required"
                }
              />
            </dl>
            <Link to="/system" className="text-link panel-footer">
              Inspect system health <ArrowRight size={14} />
            </Link>
          </Panel>
          <Panel title="Research boundary">
            <div className="reading">
              <h3>Paper mode is enforced.</h3>
              <p>
                The application will refuse a live configuration. The original
                strategy parameters remain unchanged. Out-of-sample validation
                has not been completed.
              </p>
              <Link to="/research" className="text-link">
                Review the evidence gate <ArrowRight size={14} />
              </Link>
            </div>
          </Panel>
        </div>
      </Resource>
    </>
  );
}
function PaperTrades() {
  const r = useResource(base + "/trades/open"),
    history = useResource(base + "/trades/history?limit=30&offset=0");
  const [selected, setSelected] = useState<any>(null),
    [journeyTrade, setJourneyTrade] = useState<any>(null),
    [journeyPoints, setJourneyPoints] = useState<any[]>([]),
    [journeyLoading, setJourneyLoading] = useState(false),
    [journeyError, setJourneyError] = useState(""),
    [totp, setTotp] = useState(""),
    [error, setError] = useState(""),
    [pending, setPending] = useState(false);
  async function inspectJourney(trade: any) {
    const tradeId = trade.trade_id ?? trade.id;
    setJourneyTrade(trade);
    setJourneyPoints([]);
    setJourneyError("");
    setJourneyLoading(true);
    try {
      const data = await request(`${base}/trades/${encodeURIComponent(tradeId)}/journey`);
      setJourneyPoints(Array.isArray(data.journey) ? data.journey : []);
    } catch (e) {
      setJourneyError((e as Error).message);
    } finally {
      setJourneyLoading(false);
    }
  }
  async function close(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      await request(base + "/trades/close", {
        method: "POST",
        body: JSON.stringify({
          trade_id: selected.id || selected.trade_id,
          totp_code: totp,
        }),
      });
      setSelected(null);
      setTotp("");
      r.refresh();
      history.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  const columns = [
    {
      key: "coin",
      label: "Instrument",
      render: (t: any) => <strong>{t.coin || t.symbol}</strong>,
    },
    {
      key: "direction",
      label: "Direction",
      render: (t: any) => (
        <Badge>{t.direction || (t.is_short ? "SHORT" : "LONG")}</Badge>
      ),
    },
    {
      key: "entry_price",
      label: "Entry",
      render: (t: any) => price(t.entry_price || t.open_rate),
    },
    {
      key: "current_price",
      label: "Mark",
      render: (t: any) => price(t.current_price || t.current_rate),
    },
    {
      key: "profit_abs",
      label: "Unrealized P&L",
      render: (t: any) => number(t.profit_abs ?? t.unrealized_pnl),
    },
    {
      key: "journey",
      label: "History",
      render: (t: any) => <Button variant="outline" size="sm" onClick={() => void inspectJourney(t)}>Trade journey</Button>,
    },
    {
      key: "action",
      label: "Action",
      render: (t: any) => (
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setSelected(t);
            setError("");
          }}
        >
          Close position
        </Button>
      ),
    },
  ];
  return (
    <>
      <PageHead
        eyebrow="PRIVATE PAPER LEDGER"
        title="Positions and their lifecycle."
        description="Exchange-demo positions and stored trade history. Closing a position requires your authenticator code."
        action={
          <Refresh
            onClick={() => {
              r.refresh();
              history.refresh();
            }}
          />
        }
      />
      <Panel title="Open positions">
        <Resource resource={r}>
          <DataTable
            rows={Array.isArray(r.data) ? r.data : []}
            columns={columns}
            empty="No open paper positions"
          />
        </Resource>
      </Panel>
      <Panel title="Recent closed records">
        <Resource resource={history}>
          <DataTable
            rows={history.data?.trades || []}
            columns={[
              { key: "coin", label: "Instrument" },
              { key: "direction", label: "Direction" },
              {
                key: "entry_price",
                label: "Entry",
                render: (t) => price(t.entry_price),
              },
              { key: "outcome", label: "Outcome" },
              {
                key: "net_pnl",
                label: "Net P&L",
                render: (t) => number(t.net_pnl),
              },
              {
                key: "closed_at",
                label: "Closed",
                render: (t) => time(t.closed_at),
              },
              {
                key: "journey",
                label: "Details",
                render: (t) => <Button variant="outline" size="sm" onClick={() => void inspectJourney(t)}>Trade journey</Button>,
              },
            ]}
          />
        </Resource>
      </Panel>
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!pending && !open) setSelected(null);
        }}
        title="Close this paper position?"
        description="This submits a closing order to the demo exchange. Confirm the instrument and authenticate the action."
      >
        <form onSubmit={close}>
          <p className="confirm-instrument">
            {selected?.coin || selected?.symbol}
          </p>
          <label className="field">
            Authenticator code
            <input
              required
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={totp}
              onChange={(e) => setTotp(e.target.value)}
              autoComplete="one-time-code"
            />
          </label>
          {error && (
            <p className="error-text" role="alert">
              {error}
            </p>
          )}
          <Button variant="destructive" disabled={pending} type="submit">
            {pending ? "Closing…" : "Confirm close"}
          </Button>
        </form>
      </Dialog>
      <Dialog
        open={!!journeyTrade}
        onOpenChange={(open) => {
          if (!open) setJourneyTrade(null);
        }}
        title={`${journeyTrade?.coin || "Trade"} · trade journey`}
        description="Recorded price snapshots for this paper trade, with the stored entry, stop, and target levels."
      >
        {journeyLoading ? <div className="loading" role="status">Loading trade journey…</div> : null}
        {journeyError ? <div className="error-state" role="alert">{journeyError}</div> : null}
        {!journeyLoading && !journeyError ? <JourneyChart points={journeyPoints} /> : null}
      </Dialog>
    </>
  );
}
function System() {
  const r = useResource(base + "/health"),
    reject = useResource(base + "/engine/rejections"),
    engine = useResource(base + "/engine/health"),
    traces = useResource(base + "/engine/traces?limit=50"),
    filters = useResource(base + "/engine/filter-analysis"),
    strength = useResource(base + "/engine/relative-strength");
  return (
    <>
      <PageHead
        eyebrow="SYSTEM HEALTH"
        title="Inspect the dependencies."
        description="Readiness checks and scanner telemetry. A reachable API alone does not establish engine readiness."
        action={
          <Refresh
            onClick={() => {
              r.refresh();
              reject.refresh();
              engine.refresh();
              traces.refresh();
              filters.refresh();
              strength.refresh();
            }}
          />
        }
      />
      <Resource resource={r}>
        <div className="two-column">
          <Panel title="Dependencies">
            <dl className="facts">
              {Object.entries(r.data?.checks || {}).map(([key, v]) => (
                <Fact
                  key={key}
                  label={words(key)}
                  value={
                    <Badge tone={v === "connected" ? "green" : "red"}>
                      {String(v)}
                    </Badge>
                  }
                />
              ))}
              <Fact label="Runtime" value={words(r.data?.runtime)} />
              <Fact label="Observed" value={time(r.data?.timestamp)} />
            </dl>
          </Panel>
          <Panel title="Scan telemetry">
            <dl className="facts">
              <Fact
                label="Last completed scan"
                value={time(r.data?.scan?.last_scan_at)}
              />
              <Fact
                label="Scan duration"
                value={number(r.data?.scan?.last_scan_ms, 0) + " ms"}
              />
              <Fact
                label="Instruments analyzed"
                value={number(r.data?.scan?.last_scan_count, 0)}
              />
              <Fact
                label="Total scans"
                value={number(r.data?.scan?.total_scans, 0)}
              />
            </dl>
          </Panel>
        </div>
      </Resource>
      <Panel title="Rejection reasons">
        <Resource resource={reject}>
          <DataTable
            rows={Array.isArray(reject.data?.top) ? reject.data.top : []}
            columns={[
              {
                key: "reason",
                label: "Reason",
                render: (r) => words(r.reason || r.filter),
              },
              {
                key: "count",
                label: "Count",
                render: (r) => number(r.count, 0),
              },
            ]}
            empty="No rejection summary available"
          />
        </Resource>
      </Panel>
      <div className="two-column">
        <Panel title="Engine diagnostics">
          <Resource resource={engine}>
            <dl className="facts">
              {Object.entries(engine.data || {})
                .filter(([, value]) => value === null || ["string", "number", "boolean"].includes(typeof value))
                .map(([key, value]) => <Fact key={key} label={words(key)} value={String(value ?? "—")} />)}
              {engine.data?.scan_stats && <Fact label="Scan statistics" value={<code>{JSON.stringify(engine.data.scan_stats)}</code>} />}
            </dl>
          </Resource>
        </Panel>
        <Panel title="Relative strength ranking">
          <Resource resource={strength}>
            <dl className="facts">
              <Fact label="Ranked instruments" value={number(strength.data?.total, 0)} />
              <Fact label="High tier" value={number(strength.data?.high_tier, 0)} />
              <Fact label="Medium tier" value={number(strength.data?.medium_tier, 0)} />
              <Fact label="Low tier" value={number(strength.data?.low_tier, 0)} />
            </dl>
            <DataTable
              rows={strength.data?.top_5 || []}
              columns={[
                { key: "rank", label: "Rank" },
                { key: "coin", label: "Instrument" },
                { key: "total_score", label: "Score", render: (row) => number(row.total_score, 2) },
                { key: "rs", label: "Relative strength", render: (row) => number(row.rs, 2) + "%" },
                { key: "tier", label: "Tier", render: (row) => words(row.tier) },
              ]}
              empty="Relative strength data is not available yet"
            />
          </Resource>
        </Panel>
      </div>
      <Panel title="Decision traces">
        <Resource resource={traces}>
          <DataTable
            rows={traces.data?.traces || []}
            columns={[
              { key: "datetime", label: "Time", render: (row) => time(row.datetime || row.timestamp) },
              { key: "coin", label: "Instrument", render: (row) => <strong>{row.coin}</strong> },
              { key: "direction", label: "Direction" },
              { key: "final_decision", label: "Decision", render: (row) => words(row.final_decision) },
              { key: "final_grade", label: "Grade" },
              { key: "final_score", label: "Score", render: (row) => number(row.final_score, 1) },
              { key: "stopped_at", label: "Stopped at", render: (row) => words(row.stopped_at || "Completed") },
              { key: "steps", label: "Filter steps", render: (row) => Array.isArray(row.steps) ? row.steps.map((step: any) => `${step.name}: ${step.result}`).join(" · ") : "—" },
            ]}
            empty="No decision traces have been recorded in the active trace window"
          />
        </Resource>
      </Panel>
      <Panel title="Filter analysis">
        <Resource resource={filters}>
          <div className="metric-grid">
            <Metric label="Scans evaluated" value={number(filters.data?.total_scans, 0)} note="Recent filter telemetry" />
            <Metric label="Signals produced" value={number(filters.data?.total_signals, 0)} note="Signals recorded by the scanner" />
            <Metric label="Signal rate" value={number(filters.data?.signal_rate, 0) + "%"} note="Recorded signals per scan" />
          </div>
          <DataTable
            rows={filters.data?.filter_analysis || []}
            columns={[
              { key: "filter", label: "Filter" },
              { key: "total_count", label: "Rejections", render: (row) => number(row.total_count, 0) },
              { key: "pct_of_scans", label: "Share", render: (row) => number(row.pct_of_scans, 1) + "%" },
              { key: "impact", label: "Impact", render: (row) => words(row.impact) },
            ]}
            empty="No filter analysis is available yet"
          />
        </Resource>
      </Panel>
    </>
  );
}
function Markets() {
  const r = useResource(base + "/coins"),
    [pending, setPending] = useState(""),
    [message, setMessage] = useState("");
  async function toggle(row: any) {
    setPending(row.coin);
    setMessage("");
    try {
      await request(base + "/coins/toggle", {
        method: "POST",
        body: JSON.stringify({ coin: row.coin, enabled: !row.enabled }),
      });
      r.refresh();
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setPending("");
    }
  }
  return (
    <>
      <PageHead
        eyebrow="CONFIGURED UNIVERSE"
        title="A deliberate market scope."
        description="Enable or pause existing instruments. Strategy parameters are preserved; unsupported markets are not added through this interface."
        action={<Refresh onClick={r.refresh} />}
      />
      {message && (
        <p className="notice" role="alert">
          {message}
        </p>
      )}
      <Panel title="Crypto futures">
        <Resource resource={r}>
          <DataTable
            rows={r.data || []}
            columns={[
              {
                key: "coin",
                label: "Instrument",
                render: (r) => <strong>{r.coin} / USDT</strong>,
              },
              { key: "state", label: "Engine state" },
              {
                key: "price",
                label: "Last observed price",
                render: (r) => (r.price ? price(r.price) : "Awaiting data"),
              },
              { key: "grade", label: "Latest grade" },
              {
                key: "enabled",
                label: "Scanning",
                render: (r) => (
                  <Badge tone={r.enabled ? "green" : "neutral"}>
                    {r.enabled ? "Enabled" : "Paused"}
                  </Badge>
                ),
              },
              {
                key: "action",
                label: "Action",
                render: (r) => (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!!pending}
                    onClick={() => toggle(r)}
                  >
                    {pending === r.coin
                      ? "Updating…"
                      : r.enabled
                        ? "Pause"
                        : "Enable"}
                  </Button>
                ),
              },
            ]}
          />
        </Resource>
      </Panel>
    </>
  );
}
function India() {
  const status = useResource(base + "/indian/status"),
    signals = useResource(base + "/indian/signals?limit=30");
  return (
    <>
      <PageHead
        eyebrow="PRIVATE INDIAN MARKETS"
        title="Opening-range research."
        description="The existing Angel One integration is retained as an operator-only surface. Credentials and data availability govern its readiness."
        action={
          <Refresh
            onClick={() => {
              status.refresh();
              signals.refresh();
            }}
          />
        }
      />
      <Resource resource={status}>
        <Panel title="Session status">
          <dl className="facts">
            <Fact
              label="Market"
              value={status.data?.market_open ? "Open" : "Closed"}
            />
            <Fact
              label="Opening range"
              value={status.data?.orb_ready ? "Ready" : "Awaiting range"}
            />
            <Fact
              label="Signals today"
              value={number(status.data?.signals_today, 0)}
            />
            <Fact
              label="Rate limited"
              value={status.data?.rate_limited ? "Yes" : "No"}
            />
            <Fact
              label="Data age"
              value={
                status.data?.data_age_secs == null
                  ? "Not available"
                  : number(status.data.data_age_secs, 0) + " seconds"
              }
            />
          </dl>
        </Panel>
      </Resource>
      <Panel title="Indian signal history">
        <Resource resource={signals}>
          <DataTable
            rows={signals.data || []}
            columns={[
              { key: "instrument", label: "Instrument" },
              { key: "direction", label: "Direction" },
              { key: "entry", label: "Entry", render: (r) => price(r.entry) },
              { key: "sl", label: "Stop", render: (r) => price(r.sl) },
              { key: "tp1", label: "Target", render: (r) => price(r.tp1) },
              { key: "outcome", label: "Outcome" },
              {
                key: "timestamp",
                label: "Generated",
                render: (r) => time(r.timestamp),
              },
            ]}
          />
        </Resource>
      </Panel>
    </>
  );
}
function Research() {
  const r = useResource(base + "/research"),
    universe = useResource(base + "/coins"),
    history = useResource(base + "/backtest/history/all"),
    assistant = useResource(base + "/assistant/status");
  const [coin, setCoin] = useState(""),
    [result, setResult] = useState<any>(null),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState<any>(null),
    [asking, setAsking] = useState(false);
  async function replay(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError("");
    try {
      setResult(
        await request(base + "/research/backtest", {
          method: "POST",
          body: JSON.stringify({ coin }),
        }),
      );
      history.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  async function ask(e: FormEvent) {
    e.preventDefault();
    setAsking(true);
    setAnswer(null);
    try {
      setAnswer(
        await request(base + "/assistant", {
          method: "POST",
          body: JSON.stringify({ question }),
        }),
      );
    } catch (e) {
      setAnswer({ answer: (e as Error).message });
    } finally {
      setAsking(false);
    }
  }
  return (
    <>
      <PageHead
        eyebrow="RESEARCH & EVIDENCE"
        title="Test the assumptions."
        description="Historical replay and a visible evidence gate. A replay run does not certify a strategy or enable real-money execution."
      />
      <Resource resource={r}>
        <Panel
          title="Evidence gate"
          aside={<Badge tone="amber">Not approved for live trading</Badge>}
        >
          <div className="metric-grid">
            <Metric
              label="Symbols evaluated"
              value={number(r.data?.gate?.tested_symbols, 0)}
              note={
                "Required universe: " +
                (r.data?.gate?.required_symbols || "not recorded")
              }
            />
            <Metric
              label="Review complete"
              value={r.data?.gate?.research_complete_for_review ? "Yes" : "No"}
              note="Full research evidence gate"
            />
          </div>
          <div className="reading">
            <p>
              Preserve chronological holdouts, record fees and funding, compare
              multiple regimes, and validate paper-forward execution.
              Cached-candle replay below uses a simulated 1,000 USDT account and
              1× leverage.
            </p>
          </div>
        </Panel>
      </Resource>
      <Panel title="Run a cached-data replay">
        <form className="filters" onSubmit={replay}>
          <label>
            Configured instrument
            <select
              required
              value={coin}
              onChange={(e) => setCoin(e.target.value)}
            >
              <option value="">Choose instrument</option>
              {universe.data?.map((c: any) => (
                <option key={c.coin}>{c.coin}</option>
              ))}
            </select>
          </label>
          <Button disabled={pending || !coin} type="submit">
            <FlaskConical size={15} />
            {pending ? "Replaying…" : "Run research replay"}
          </Button>
        </form>
        {error && (
          <p className="error-text panel-note" role="alert">
            {error}
          </p>
        )}
        {result && (
          <dl className="facts">
            <Fact label="Status" value={words(result.status)} />
            <Fact
              label="Recorded trades"
              value={number(result.result?.total_trades, 0)}
            />
            <Fact
              label="Net P&L (simulation)"
              value={number(result.result?.total_pnl)}
            />
            <Fact
              label="Maximum drawdown"
              value={number(result.result?.max_drawdown)}
            />
          </dl>
        )}
      </Panel>
      <Panel title="Stored research runs">
        <Resource resource={history}>
          <DataTable
            rows={history.data || []}
            columns={[
              { key: "coin", label: "Instrument" },
              {
                key: "run_at",
                label: "Run time",
                render: (r) => time(r.run_at),
              },
              { key: "total_trades", label: "Trades" },
              {
                key: "win_rate",
                label: "Win rate",
                render: (r) => number(r.win_rate) + "%",
              },
              {
                key: "total_pnl",
                label: "Simulated P&L",
                render: (r) => number(r.total_pnl),
              },
              {
                key: "max_drawdown",
                label: "Drawdown",
                render: (r) => number(r.max_drawdown),
              },
            ]}
          />
        </Resource>
      </Panel>
      <Panel title="Private research assistant">
        <Resource resource={assistant}>
          {assistant.data?.configured ? (
            <form className="assistant-form" onSubmit={ask}>
              <p className="muted">
                Queries may send relevant private trade context to Groq.
                Generated answers require verification against source records.
              </p>
              <label className="field">
                Question
                <textarea
                  required
                  minLength={3}
                  maxLength={1000}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask about recorded trade history"
                />
              </label>
              <Button disabled={asking} type="submit">
                {asking ? "Retrieving context…" : "Ask assistant"}
              </Button>
              {answer && (
                <div className="assistant-answer">
                  {answer.answer ||
                    answer.response ||
                    answer.message ||
                    "No answer returned."}
                  {answer.sources && (
                    <small>
                      Sources:{" "}
                      {Array.isArray(answer.sources)
                        ? answer.sources.join(", ")
                        : String(answer.sources)}
                    </small>
                  )}
                </div>
              )}
            </form>
          ) : (
            <div className="reading">
              <p>
                The private research assistant is not configured. The retained
                RAG and ML modules remain research tools; no generated analysis
                is shown as a trading decision.
              </p>
            </div>
          )}
        </Resource>
      </Panel>
    </>
  );
}
function Telegram() {
  const r = useResource(base + "/integrations"),
    [pending, setPending] = useState(false),
    [error, setError] = useState(""),
    [registration, setRegistration] = useState<any>(null);
  async function register() {
    setPending(true);
    setError("");
    try {
      const result = await request(base + "/telegram/register", { method: "POST" });
      setRegistration(result?.telegram?.registration || null);
      r.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <PageHead
        eyebrow="TELEGRAM OPERATIONS"
        title="Reports with a purpose."
        description="Private command access and trading reports use the configured operator chat. Signal, account, and research output stays on Telegram."
        action={
          <Button variant="outline" disabled={pending} onClick={register}>
            <RefreshCw size={14} />
            {pending ? "Registering…" : "Register webhook"}
          </Button>
        }
      />
      {error && (
        <p className="notice" role="alert">
          {error}
        </p>
      )}
      <Resource resource={r}>
        <Panel title="Integration state">
          <dl className="facts">
            <Fact
              label="Credentials"
              value={r.data?.telegram?.configured ? "Configured" : "Required"}
            />
            <Fact
              label="Provider status"
              value={words(r.data?.telegram?.status || "not_configured")}
            />
            <Fact
              label="Webhook"
              value={r.data?.telegram?.webhook?.url || "Not registered"}
            />
            <Fact
              label="Webhook destination check"
              value={
                r.data?.telegram?.status === "registered"
                  ? "Matches the configured admin domain"
                  : words(r.data?.telegram?.status || "not_configured")
              }
            />
            <Fact
              label="Pending updates"
              value={number(r.data?.telegram?.webhook?.pending_update_count, 0)}
            />
            <Fact
              label="Latest Telegram delivery error"
              value={r.data?.telegram?.webhook?.last_error_message || "None reported"}
            />
            <Fact
              label="Allowed sender IDs"
              value={r.data?.telegram?.allowed_users_configured ? "Configured" : "Empty · private chat only"}
            />
            <Fact
              label="Last registration"
              value={
              registration || r.data?.telegram?.registration
                ? `Webhook ${(registration || r.data.telegram.registration).webhook ? "registered" : "failed"} · commands ${(registration || r.data.telegram.registration).commands ? "registered" : "failed"}`
                  : "No registration attempt this session"
              }
            />
          </dl>
        </Panel>
      </Resource>
      <Panel title="Command reference">
        <div className="command-grid">
          {[
            ["/health", "Dependency readiness and data freshness"],
            ["/status", "Operator summary and paper mode"],
            ["/scan", "Trigger a guarded market scan"],
            ["/coin ETH", "Inspect one configured instrument"],
            ["/trades", "Open paper positions"],
            ["/position ETH", "Inspect a paper position"],
            ["/journey 42", "Inspect the recorded price path for trade 42"],
            ["/performance", "Recorded performance breakdown"],
            ["/candles", "Stored candle availability"],
            ["/backtest ETH", "Cached-data research replay"],
            ["/india", "Private Indian-market status"],
            ["/help", "Complete command reference"],
          ].map(([cmd, desc]) => (
            <div key={cmd}>
              <code>{cmd}</code>
              <p>{desc}</p>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
function StoredData() {
  const catalog = useResource(base + "/data/catalog"),
    [table, setTable] = useState(""),
    [offset, setOffset] = useState(0),
    [query, setQuery] = useState(""),
    [appliedQuery, setAppliedQuery] = useState("");
  useEffect(() => {
    if (!table && catalog.data?.tables?.length) setTable(catalog.data.tables[0].name);
  }, [table, catalog.data]);
  const params = new URLSearchParams({ limit: "50", offset: String(offset) });
  if (appliedQuery) params.set("q", appliedQuery);
  const rows = useResource(table ? `${base}/data/${encodeURIComponent(table)}?${params}` : null);
  const tables = catalog.data?.tables || [],
    active = tables.find((item: any) => item.name === table),
    columns = (rows.data?.columns || []).map((column: any) => ({
      key: column.name,
      label: `${column.name}${column.redacted ? " · redacted" : ""}`,
      render: (row: any) => {
        const value = row[column.name];
        if (value === null || value === undefined || value === "") return "—";
        const display = typeof value === "object" ? JSON.stringify(value) : String(value);
        return display.length > 240 ? display.slice(0, 237) + "…" : display;
      },
    }));
  function exportCurrentPage() {
    const data = rows.data;
    if (!data?.rows?.length) return;
    const fields = data.columns.map((column: any) => column.name);
    const escape = (value: any) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [fields.map(escape).join(","), ...data.rows.map((row: any) => fields.map((field: string) => escape(typeof row[field] === "object" ? JSON.stringify(row[field]) : row[field])).join(","))].join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${table}-${offset + 1}-${offset + data.rows.length}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      <PageHead
        eyebrow="PERSISTED RECORDS"
        title="Inspect what this installation stores."
        description="Read-only, paginated access to the application tables. Sensitive credentials and session material are redacted."
        action={<Refresh onClick={() => { catalog.refresh(); rows.refresh(); }} />}
      />
      <Panel title="Database inventory">
        <Resource resource={catalog}>
          <div className="metric-grid">
            <Metric label="Application tables" value={number(catalog.data?.total_tables, 0)} note="SQLite application tables, excluding SQLite internals" />
            <Metric label="Selected records" value={number(active?.rows, 0)} note={active?.name || "Choose a table"} />
            <Metric label="Table purpose" value={active?.purpose || "—"} note={active?.sensitive ? "Contains redacted fields" : "No credential fields detected"} />
          </div>
          <form className="filters data-filters" onSubmit={(event) => { event.preventDefault(); setOffset(0); setAppliedQuery(query.trim()); }}>
            <label>
              Stored table
              <select value={table} onChange={(event) => { setOffset(0); setTable(event.target.value); }}>
                {tables.map((item: any) => <option key={item.name} value={item.name}>{item.name} · {number(item.rows ?? 0, 0)}</option>)}
              </select>
            </label>
            <label>
              Search records
              <input value={query} onChange={(event) => setQuery(event.target.value)} maxLength={100} placeholder="Instrument, outcome, status…" />
            </label>
            <Button type="submit">Apply search</Button>
            <Button type="button" variant="outline" disabled={!rows.data?.rows?.length} onClick={exportCurrentPage}>Export page CSV</Button>
          </form>
          {active && <p className="panel-note">{active.purpose}. {active.sensitive ? "Credential-like values are redacted in the table and exports." : "Rows are read-only; no database writes are available from this view."}</p>}
        </Resource>
      </Panel>
      <Panel title={table ? `Records · ${table}` : "Records"} aside={<span className="panel-note">{number(rows.data?.total ?? active?.rows, 0)} total</span>}>
        <Resource resource={rows}>
          <DataTable rows={rows.data?.rows || []} columns={columns} empty="No rows match this view" />
          <div className="data-pagination">
            <Button variant="outline" size="sm" disabled={offset <= 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous 50</Button>
            <span>Rows {rows.data?.total ? offset + 1 : 0}–{Math.min(offset + 50, rows.data?.total || 0)} of {number(rows.data?.total, 0)}</span>
            <Button variant="outline" size="sm" disabled={offset + 50 >= (rows.data?.total || 0)} onClick={() => setOffset(offset + 50)}>Next 50</Button>
          </div>
        </Resource>
      </Panel>
      <Panel title="Legacy account and plan records">
        <p className="panel-note">Customer signup, subscriptions, API-key access, and billing workflows are disabled. Historical rows remain in the database for review or export. Credential and session secrets are always redacted.</p>
      </Panel>
    </>
  );
}
function Audit() {
  const r = useResource(base + "/audit/log?limit=100");
  return (
    <>
      <PageHead
        eyebrow="OPERATOR AUDIT"
        title="A record of access and actions."
        description="Security and operator events from this installation. Account-level data is restricted to the administrator."
        action={<Refresh onClick={r.refresh} />}
      />
      <Panel>
        <Resource resource={r}>
          <DataTable
            rows={r.data || []}
            columns={[
              {
                key: "timestamp",
                label: "Time",
                render: (r) => time(r.timestamp),
              },
              {
                key: "action",
                label: "Event",
                render: (r) => <strong>{words(r.action)}</strong>,
              },
              { key: "source", label: "Source" },
              {
                key: "success",
                label: "Result",
                render: (r) => (
                  <Badge tone={r.success ? "green" : "red"}>
                    {r.success ? "Success" : "Denied / failed"}
                  </Badge>
                ),
              },
              { key: "detail", label: "Detail" },
            ]}
          />
        </Resource>
      </Panel>
    </>
  );
}
function Settings() {
  const r = useResource(base + "/settings");
  return (
    <>
      <PageHead
        eyebrow="DEPLOYMENT CONFIGURATION"
        title="Explicit settings. Private secrets."
        description="Read-only runtime configuration. Secret changes are made on AWS and Cloudflare, then applied through a controlled restart."
      />
      <Resource resource={r}>
        <div className="two-column">
          <Panel title="Canonical origins">
            <dl className="facts">
              <Fact label="Public application" value={r.data?.public_origin} />
              <Fact label="Operator application" value={r.data?.admin_origin} />
              <Fact
                label="Allowed administrator"
                value={r.data?.admin_emails?.join(", ")}
              />
              <Fact
                label="Session lifetime"
                value={r.data?.session_hours + " hours"}
              />
              <Fact label="Strategy version" value={r.data?.strategy_version} />
              <Fact label="Execution mode" value="Paper only" />
            </dl>
          </Panel>
          <Panel title="Credential presence">
            <dl className="facts">
              {Object.entries(r.data?.credentials || {}).map(([key, v]) => (
                <Fact
                  key={key}
                  label={words(key)}
                  value={
                    <Badge tone={v ? "green" : "amber"}>
                      {v ? "Configured" : "Not configured"}
                    </Badge>
                  }
                />
              ))}
            </dl>
            <p className="panel-note">
              Secret values are never returned to this application.
            </p>
          </Panel>
        </div>
      </Resource>
    </>
  );
}
function Login() {
  const reason = new URLSearchParams(location.search).get("error");
  return (
    <main className="login-layout">
      <section className="login-form">
        <div className="login-card">
          <Brand admin />
          <p className="eyebrow">OPERATOR ACCESS</p>
          <h1>Sign in to Signal Engine</h1>
          <p>
            Continue with the Google account on the administrator allowlist.
          </p>
          {reason && (
            <div className="notice" role="alert">
              {reason === "unauthorized"
                ? "This Google account is not an authorized administrator."
                : "Google sign-in could not be completed. Try again or check the server configuration."}
            </div>
          )}
          <Button asChild className="google-button">
            <a href="/auth/google">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  fill="currentColor"
                  d="M21.6 12.2c0-.7-.1-1.4-.2-2H12v3.8h5.4a4.6 4.6 0 0 1-2 3v2.5h3.2c1.9-1.8 3-4.3 3-7.3ZM12 22c2.7 0 5-.9 6.6-2.4l-3.2-2.5c-.9.6-2 1-3.4 1-2.6 0-4.9-1.8-5.7-4.2H3v2.6A10 10 0 0 0 12 22ZM6.3 13.9a6 6 0 0 1 0-3.8V7.5H3a10 10 0 0 0 0 9l3.3-2.6ZM12 5.9c1.5 0 2.8.5 3.8 1.5l2.9-2.8A9.5 9.5 0 0 0 12 2a10 10 0 0 0-9 5.5l3.3 2.6A6 6 0 0 1 12 5.9Z"
                />
              </svg>
              Continue with Google
              <ArrowUpRight size={16} />
            </a>
          </Button>
          <div className="login-security">
            <ShieldCheck size={14} /> Google verifies your identity
            <Check size={14} /> Access is checked by the server
          </div>
          <p className="login-fineprint">
            This application has no customer registration. Access is limited to
            the configured operator.
          </p>
        </div>
      </section>
    </main>
  );
}
function AdminGate() {
  const r = useResource("/auth/session", 60000);
  if (r.loading)
    return (
      <div className="screen-loading">
        <Brand admin />
        <span className="spinner" />
        Verifying operator session
      </div>
    );
  if (r.error) {
    if (r.error instanceof ApiError && r.error.status === 401) return <Login />;
    return (
      <div className="login-error">
        <Brand admin />
        <Resource resource={r}>{null}</Resource>
      </div>
    );
  }
  return <AdminShell email={r.data.user.email} />;
}
const publicNav = [
  ["/", "Overview"],
  ["/signals", "Signals"],
  ["/performance", "Performance"],
  ["/methodology", "Methodology"],
  ["/status", "Status"],
];
const adminNav = [
  { path: "/", name: "Overview", icon: Layers3 },
  { path: "/signals", name: "Signals", icon: Radio },
  { path: "/trades", name: "Paper trades", icon: Wallet },
  { path: "/performance", name: "Performance", icon: Activity },
  { path: "/markets", name: "Crypto universe", icon: Globe2 },
  { path: "/india", name: "Indian markets", icon: Activity },
  { path: "/research", name: "Research", icon: FlaskConical },
  { path: "/data", name: "Stored data", icon: Database },
  { path: "/system", name: "System health", icon: Activity },
  { path: "/telegram", name: "Telegram", icon: Send },
  { path: "/audit", name: "Audit trail", icon: ScrollText },
  { path: "/settings", name: "Settings", icon: Settings2 },
];
function AdminShell({ email }: { email: string }) {
  const [open, setOpen] = useState(false),
    [logoutError, setLogoutError] = useState(""),
    conn = useConnection(true),
    location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  async function logout() {
    try {
      await request("/auth/logout", { method: "POST" });
      window.location.assign("/login");
    } catch (e) {
      setLogoutError((e as Error).message);
    }
  }
  return (
    <div className="admin-shell">
      {open && (
        <button
          className="sidebar-scrim"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <aside className={"sidebar " + (open ? "is-open" : "")}>
        <Brand admin />
        <button
          className="mobile-close"
          onClick={() => setOpen(false)}
          aria-label="Close navigation"
        >
          <X />
        </button>
        <div className="sidebar-section">WORKSPACE</div>
        <nav aria-label="Operator navigation">
          {adminNav.map(({ path, name, icon: Icon }) => (
            <NavLink key={path} to={path} end={path === "/"}>
              <Icon size={17} />
              {name}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="avatar">{email.charAt(0).toUpperCase()}</span>
          <div>
            <strong>Administrator</strong>
            <small title={email}>{email}</small>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Sign out"
            onClick={logout}
          >
            <LogOut size={16} />
          </Button>
        </div>
      </aside>
      <div className="admin-content">
        <header className="operator-bar">
          <button
            className="mobile-menu"
            aria-label="Open navigation"
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            <Menu size={22} />
          </button>
          <span className="operator-breadcrumb">
            Workspace <ChevronRight size={13} />
            <strong>
              {adminNav.find((item) => item.path === location.pathname)?.name ||
                "Signal detail"}
            </strong>
          </span>
          <div>
            <ThemeToggle />
            <Badge tone="amber">PAPER</Badge>
            <span
              className={"connection " + (conn === "connected" ? "online" : "")}
            >
              <span />
              {conn === "connected" ? "Stream connected" : "Polling fallback"}
            </span>
          </div>
        </header>
        <main className="workspace">
          {logoutError && (
            <div className="notice" role="alert">
              {logoutError}
            </div>
          )}
          <Routes>
            <Route path="/" element={<AdminOverview />} />
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/signals" element={<SignalList />} />
            <Route path="/signals/:id" element={<SignalDetail />} />
            <Route path="/trades" element={<PaperTrades />} />
            <Route path="/performance" element={<AdminPerformance />} />
            <Route path="/markets" element={<Markets />} />
            <Route path="/india" element={<India />} />
            <Route path="/research" element={<Research />} />
            <Route path="/data" element={<StoredData />} />
            <Route path="/system" element={<System />} />
            <Route path="/telegram" element={<Telegram />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="operator-footer">
          Private operator workspace <span>Paper mode · No live execution</span>
        </footer>
      </div>
    </div>
  );
}
function NotFound() {
  return (
    <>
      <PageHead
        eyebrow="404"
        title="This view does not exist."
        description="Use the navigation to return to the workspace."
      />
      <Button asChild variant="outline">
        <Link to="/">Return to overview</Link>
      </Button>
    </>
  );
}
function PublicShell() {
  const [open, setOpen] = useState(false),
    conn = useConnection(false),
    location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);
  return (
    <div className="public-shell">
      <header className="public-header">
        <Brand />
        <nav className={open ? "open" : ""} aria-label="Public navigation">
          {publicNav.map(([path, label]) => (
            <NavLink key={path} end={path === "/"} to={path}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="header-status">
          <ThemeToggle />
          <span
            className={"connection " + (conn === "connected" ? "online" : "")}
          >
            <span />
            {conn === "connected" ? "Connected" : "Reconnecting"}
          </span>
          <button
            className="mobile-menu"
            aria-label={open ? "Close navigation" : "Open navigation"}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </header>
      <main className="public-main">
        <Routes>
          <Route path="/" element={<PublicOverview />} />
          <Route path="/signals" element={<SignalList />} />
          <Route path="/signals/:id" element={<SignalDetail />} />
          <Route path="/performance" element={<PublicPerformance />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/status" element={<PublicStatus />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="public-footer">
        <Brand />
        <p>
          Open research. Recorded decisions.
          <small>
            Paper signals are experimental model outputs. No validated trading
            edge is claimed.
          </small>
        </p>
        <Link to="/methodology">
          Method & limitations <ArrowUpRight size={14} />
        </Link>
      </footer>
      <Suspense fallback={null}>
        <PWA />
      </Suspense>
    </div>
  );
}
export default function App() {
  return ADMIN ? <AdminGate /> : <PublicShell />;
}
