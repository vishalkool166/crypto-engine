import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Radio, FlaskConical, Wallet } from "lucide-react";
import { request, useResource, number, price, time, words } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

import {
  Panel,
  PageHead,
  Metric,
  Resource,
  Fact,
  DataTable,
  signalColumns,
} from "../components/workspace";
import { TrendChart } from "../components/Analytics";
import { ExecutionMode, useExecution } from "../components/ExecutionMode";
import { StrategyBoard } from "../components/StrategyBoard";

export function AdminOverview() {
  const r = useResource(base + "/overview"),
    recent = useResource(base + "/signals?limit=6"),
    d = r.data;
  const execution = useExecution();
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
      recent.refresh();
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setPending(false);
    }
  }
  const mode = execution?.data?.mode;
  const p = d?.performance;
  return (
    <>
      <section className="atelier-command-hero" aria-label="Private operator command header">
        <div className="atelier-command-noise" aria-hidden="true"/>
        <div className="atelier-command-topline"><span><span className="atelier-mini-led"/> THE OPERATOR WORKSPACE</span><span>SIGNAL ENGINE / PRIVATE</span></div>
        <div className="atelier-command-main"><div><p className="atelier-command-eyebrow">ONE PIPELINE / FOUR APPROACHES</p><h1>Decisions, <em>in view.</em></h1><p>One continuous view of strategy decisions, execution permissions, account risk and the full evidence trail.</p></div>
        <div className="atelier-command-action"><div className="engine-status-inline" role="status" aria-live="polite"><span className={d?.health?.runtime==='running'?'engine-status-indicator active':'engine-status-indicator'}/><div><span>Engine status</span><strong>{words(d?.health?.runtime || 'unknown')}</strong><small>{mode ? `Account mode · ${mode}` : 'Account mode unavailable'}</small></div></div>
          <Button disabled={pending || d?.health?.runtime !== "running"} onClick={scan}><Radio size={14}/>{pending ? "Scanning…" : "Run market scan"} <ArrowUpRight size={15}/></Button></div></div>
        <div className="atelier-command-bottom"><span>DECISIONS WITH A RECORD.</span><span>PRIVATE / ACCOUNT-SCOPED</span></div>
      </section>
      {message && (
        <div role="status" className="notice">
          {message}
        </div>
      )}
      <StrategyBoard />
      <Resource resource={r}>
        <div className="finance-metrics">
          <Metric
            label="Net P&L today"
            value={number(d?.summary?.today_pnl, 4)}
            note={`${number(d?.summary?.today_trades, 0)} closed trades · USDT`}
          />
          <Metric
            label="Total net P&L"
            value={number(p?.total_pnl, 4)}
            note="Recorded closed trades · USDT"
          />
          <Metric
            label="Win rate"
            value={p?.win_rate != null ? number(p.win_rate, 1) + "%" : "—"}
            note={`${number(p?.closed, 0)} recorded closed trades`}
          />
          <Metric
            label="Active positions"
            value={number(d?.summary?.in_trade_count, 0)}
            note={`${number(d?.summary?.watching_count, 0)} instruments on watch`}
          />
        </div>
        <div className="finance-grid">
          <Panel
            title="Cumulative net P&L"
            className="finance-wide"
            aside={
              <Link className="text-link" to="/performance">
                Full report <ArrowUpRight size={14} />
              </Link>
            }
          >
            <div className="chart-headline">
              <strong className={(p?.total_pnl || 0) < 0 ? "negative" : ""}>
                {number(p?.total_pnl, 4)} <small>USDT</small>
              </strong>
              <span>Closed-trade equity curve</span>
            </div>
            <TrendChart data={p?.equity_curve || []} />
            <p className="panel-note">
              Historical ledger includes all recorded environments. Review each
              trade’s execution mode.
            </p>
          </Panel>
          <Panel title="Execution environment">
            <div className="execution-card">
              <Badge tone={mode === "live" ? "red" : "blue"}>
                {mode ? mode.toUpperCase() : "UNAVAILABLE"}
              </Badge>
              <h3>
                {mode === "live"
                  ? "Live account connected"
                  : mode === "paper"
                    ? "Paper trading workspace"
                    : "Checking engine mode"}
              </h3>
              <p>
                {mode === "live"
                  ? "Orders use real account funds. Review positions before changing the environment."
                  : "Strategy orders use the Binance demo exchange. Live activation requires TOTP and account checks."}
              </p>
              <div className="execution-summary">
                <span>Runtime</span>
                <strong>{words(d?.health?.runtime)}</strong>
              </div>
              <div className="execution-summary">
                <span>Last scan</span>
                <strong>{time(d?.health?.scan?.last_scan_at)}</strong>
              </div>
              <div className="execution-summary">
                <span>Mode authorization</span>
                <strong>TOTP required</strong>
              </div>
              <ExecutionMode />
            </div>
          </Panel>
        </div>
        <div className="overview-layout">
          <Panel
            title="Recent signal decisions"
            aside={
              <Link to="/signals" className="text-link">
                View all <ArrowUpRight size={14} />
              </Link>
            }
          >
            <Resource resource={recent}>
              <DataTable
                rows={Array.isArray(recent.data) ? recent.data : []}
                columns={signalColumns.filter((c) =>
                  ["coin", "direction", "grade", "outcome"].includes(c.key),
                )}
              />
            </Resource>
          </Panel>
          <Panel
            title="Service health"
            aside={
              <Link className="text-link" to="/system">
                Details <ArrowUpRight size={14} />
              </Link>
            }
          >
            <dl className="facts">
              {Object.entries(d?.health?.checks || {}).map(([k, v]) => (
                <Fact
                  key={k}
                  label={words(k)}
                  value={
                    <Badge tone={v === "connected" ? "green" : "amber"}>
                      {String(v)}
                    </Badge>
                  }
                />
              ))}
            </dl>
          </Panel>
        </div>
        <div className="quick-links">
          {[
            {
              path: "/trades",
              title: "Trade journey",
              note: "Positions, fills, and recorded price paths",
              icon: Wallet,
            },
            {
              path: "/strategy-lab",
              title: "Research & evidence",
              note: "Backtests and strategy diagnostics",
              icon: FlaskConical,
            },
          ].map(({ path, title, note, icon: Icon }) => (
            <Link className="quick-link" to={path} key={path}>
              <Icon size={19} />
              <div>
                <strong>{title}</strong>
                <small>{note}</small>
              </div>
              <ArrowUpRight size={14} />
            </Link>
          ))}
        </div>
      </Resource>
    </>
  );
}
