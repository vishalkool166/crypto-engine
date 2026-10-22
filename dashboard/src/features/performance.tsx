import { Link } from "react-router-dom";

import { useResource, number, time, words } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";

import {
  Panel,
  PageHead,
  Metric,
  Resource,
  Refresh,
  DataTable,
  EquityCurve,
} from "../components/workspace";

export function AdminPerformance() {
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
        title="Performance"
        description="Recorded trade results, equity, grade attribution, and instrument performance. Historical results can include both environments."
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
          <Metric
            label="Closed trades"
            value={number(p.closed, 0)}
            note="Wins and losses recorded"
          />
          <Metric
            label="Win rate"
            value={`${number(p.win_rate, 1)}%`}
            note={`${number(p.wins, 0)} wins · ${number(p.losses, 0)} losses`}
          />
          <Metric
            label="Net P&L"
            value={number(p.total_pnl, 4)}
            note="Recorded closed-trade net result"
          />
          <Metric
            label="Profit factor"
            value={number(p.profit_factor, 2)}
            note="Gross profit ÷ gross loss"
          />
          <Metric
            label="Maximum drawdown"
            value={`${number(p.max_drawdown, 2)}%`}
            note="Calculated from cumulative closed-trade P&L"
          />
          <Metric
            label="Best trade"
            value={number(p.best_trade, 4)}
            note={p.best_trade_coin || "No trade recorded"}
          />
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
                {
                  key: "win_rate",
                  label: "Win rate",
                  render: (r) => `${number(r.win_rate, 1)}%`,
                },
                {
                  key: "pnl",
                  label: "Net P&L",
                  render: (r) => number(r.pnl, 4),
                },
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
                {
                  key: "win_rate",
                  label: "Win rate",
                  render: (r) => `${number(r.win_rate, 1)}%`,
                },
                {
                  key: "profit_abs",
                  label: "Net P&L",
                  render: (r) => number(r.profit_abs, 4),
                },
                {
                  key: "commission",
                  label: "Fees",
                  render: (r) => number(r.commission, 4),
                },
                {
                  key: "funding",
                  label: "Funding",
                  render: (r) => number(r.funding, 4),
                },
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
                  {
                    key: "win_rate",
                    label: "Win rate",
                    render: (row) => `${number(row.win_rate, 1)}%`,
                  },
                  {
                    key: "pnl",
                    label: "Net P&L",
                    render: (row) => number(row.pnl, 4),
                  },
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
                  {
                    key: "regime_at_entry",
                    label: "Regime",
                    render: (row) => words(row.regime_at_entry),
                  },
                  { key: "total", label: "Trades" },
                  {
                    key: "win_rate",
                    label: "Win rate",
                    render: (row) => `${number(row.win_rate, 1)}%`,
                  },
                  {
                    key: "pnl",
                    label: "Net P&L",
                    render: (row) => number(row.pnl, 4),
                  },
                ]}
                empty="No closed trades have a recorded market regime"
              />
            </Resource>
          </Panel>
        </div>
        <Panel title="Factor observations">
          <Resource resource={context}>
            <p className="panel-note">
              {context.data?.factor_note ||
                "Descriptive averages from stored factor scores."}
            </p>
            <DataTable
              rows={context.data?.factors || []}
              columns={[
                { key: "factor", label: "Factor" },
                { key: "observations", label: "Observations" },
                {
                  key: "mean_score_wins",
                  label: "Mean score · wins",
                  render: (row) =>
                    row.mean_score_wins == null
                      ? "—"
                      : number(row.mean_score_wins, 3),
                },
                {
                  key: "mean_score_losses",
                  label: "Mean score · losses",
                  render: (row) =>
                    row.mean_score_losses == null
                      ? "—"
                      : number(row.mean_score_losses, 3),
                },
                {
                  key: "score_difference",
                  label: "Difference",
                  render: (row) =>
                    row.score_difference == null
                      ? "—"
                      : number(row.score_difference, 3),
                },
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
                { key: "execution_mode", label: "Environment" },
                { key: "outcome", label: "Outcome" },
                {
                  key: "pnl",
                  label: "Net P&L",
                  render: (r) => number(r.pnl, 4),
                },
                {
                  key: "timestamp",
                  label: "Opened",
                  render: (r) => time(r.timestamp),
                },
              ]}
            />
          </Resource>
        </Panel>
        <Panel
          title="Recent signal history"
          aside={
            <Link className="panel-link" to="/signals">
              Open signal ledger
            </Link>
          }
        >
          <Resource resource={signals}>
            <DataTable
              rows={Array.isArray(signals.data) ? signals.data : []}
              columns={[
                {
                  key: "timestamp",
                  label: "Time",
                  render: (row) => time(row.timestamp),
                },
                {
                  key: "coin",
                  label: "Instrument",
                  render: (row) => <strong>{row.coin}</strong>,
                },
                { key: "direction", label: "Side" },
                { key: "grade", label: "Grade" },
                {
                  key: "score",
                  label: "Score",
                  render: (row) => number(row.score, 1),
                },
                {
                  key: "outcome",
                  label: "Outcome",
                  render: (row) => words(row.outcome),
                },
                {
                  key: "pnl",
                  label: "Recorded P&L",
                  render: (row) => (row.pnl == null ? "—" : number(row.pnl, 4)),
                },
              ]}
              empty="No signals have been recorded"
            />
          </Resource>
        </Panel>
        <Panel title="Cached-data backtests">
          <p className="panel-note">
            Run and review research backtests from the Research page. Backtests
            use stored market data and do not place orders.
          </p>
          <Button asChild variant="outline">
            <Link to="/strategy-lab">Open Strategy Laboratory</Link>
          </Button>
        </Panel>
      </Resource>
    </>
  );
}
