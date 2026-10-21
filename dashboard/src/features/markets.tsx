import { useState } from "react";

import { request, useResource, number, price, time } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

import {
  Panel,
  PageHead,
  Resource,
  Refresh,
  Fact,
  DataTable,
} from "../components/workspace";

export function Markets() {
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

export function India() {
  const status = useResource(base + "/indian/status"),
    signals = useResource(base + "/indian/signals?limit=30"),
    performance = useResource(base + "/indian/performance");
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
              performance.refresh();
            }}
          />
        }
      />
      <Resource resource={status}>
        <Panel title="Market session" aside={<Badge tone={status.data?.market_open ? "green" : "neutral"}>{status.data?.market_open ? "Market open" : "Market closed"}</Badge>}>
          <dl className="facts">
            <Fact label="India time" value={status.data?.time_ist || "—"} />
            <Fact label="Opening range" value={status.data?.orb_ready ? "Ready" : "Awaiting range"} />
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
        <div className="india-workspace-grid">
          <Panel title="Running tracked signals" aside={<Badge tone="blue">Paper tracking</Badge>}>
            <div className="india-signal-list">
              {(status.data?.open_signals || []).length ? status.data.open_signals.map((signal: any) => {
                const pnl = Number(signal.live_pnl_pts || 0);
                const progress = Math.min(100, Math.max(0, Number(signal.progress_pct || 0)));
                return <article className="india-open-signal" key={signal.id}>
                  <div className="india-open-heading">
                    <div><strong>{signal.instrument}</strong><span>{signal.direction} · {signal.duration || "Open"}</span></div>
                    <div className={`india-open-pnl ${pnl >= 0 ? "positive-value" : "negative-value"}`}>
                      <strong>{signal.live_pnl_pts == null ? "Awaiting tick" : `${pnl > 0 ? "+" : ""}${number(pnl)} pts`}</strong>
                      <small>{signal.live_rupees == null ? "Paper monitored" : `₹${number(Math.abs(signal.live_rupees), 0)} / lot`}</small>
                    </div>
                  </div>
                  <div className="india-progress-track" role="img" aria-label={`${number(progress)} percent of target distance`}><span style={{ width: `${progress}%` }} /></div>
                  <div className="india-levels"><span>Entry <b>{price(signal.entry)}</b></span><span>Now <b>{price(signal.current_price)}</b></span><span>Stop <b>{price(signal.sl)}</b></span><span>Target <b>{price(signal.tp1)}</b></span></div>
                </article>;
              }) : <div className="empty compact-empty"><h3>No running signals</h3><p>New monitored setups will appear here with live price, stop, target, and paper P&amp;L.</p></div>}
            </div>
          </Panel>
          <Panel title="Indian market performance" aside={<span className="panel-note">Tracked signals</span>}>
            <Resource resource={performance}>
              <div className="india-performance">
                <div className="india-win-rate"><strong>{performance.data?.win_rate == null ? "—" : `${number(performance.data.win_rate, 1)}%`}</strong><span>win rate</span></div>
                <div className="india-outcomes">
                  <div><span className="outcome-dot win"/><strong>{number(performance.data?.wins, 0)}</strong><small>Wins</small></div>
                  <div><span className="outcome-dot loss"/><strong>{number(performance.data?.losses, 0)}</strong><small>Losses</small></div>
                  <div><span className="outcome-dot timeout"/><strong>{number(performance.data?.timeouts, 0)}</strong><small>Timed out</small></div>
                </div>
                <div className="india-perf-row"><span>Net points</span><strong className={Number(performance.data?.total_pts || 0) >= 0 ? "positive-value" : "negative-value"}>{number(performance.data?.total_pts, 2)} pts</strong></div>
                <div className="india-perf-row"><span>Profit factor</span><strong>{number(performance.data?.profit_factor, 2)}</strong></div>
              </div>
            </Resource>
          </Panel>
        </div>
      </Resource>
      <Panel title="Signal history" aside={<span className="panel-note">Closed and recorded setups</span>}>
        <Resource resource={signals}>
          <DataTable
            rows={signals.data || []}
            columns={[
              { key: "instrument", label: "Instrument" },
              { key: "direction", label: "Direction" },
              { key: "entry", label: "Entry", render: (r) => price(r.entry) },
              { key: "sl", label: "Stop", render: (r) => price(r.sl) },
              { key: "tp1", label: "Target", render: (r) => price(r.tp1) },
              { key: "outcome", label: "Outcome", render: (r) => <Badge tone={r.outcome === "win" ? "green" : r.outcome === "loss" ? "red" : r.outcome === "pending" ? "blue" : "neutral"}>{r.outcome || "Unresolved"}</Badge> },
              { key: "pnl_pts", label: "P&L", render: (r) => <strong className={Number(r.pnl_pts || 0) >= 0 ? "positive-value" : "negative-value"}>{r.pnl_pts == null ? "—" : `${Number(r.pnl_pts) > 0 ? "+" : ""}${number(r.pnl_pts, 2)} pts`}</strong> },
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
