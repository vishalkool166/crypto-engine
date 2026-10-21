import { Link } from "react-router-dom";
import { ArrowUpRight, ArrowRight, BookOpen } from "lucide-react";
import { useResource, number, price, time, words } from "../api";

import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

import {
  Panel,
  PageHead,
  Metric,
  Resource,
  Refresh,
  Fact,
  DataTable,
  OutcomeBars,
  signalColumns,
} from "../components/workspace";
import { TrendChart, OutcomeDonut } from "../components/Analytics";

export function PublicOverview() {
  const r = useResource("/api/v1/public/overview"),
    d = r.data;
  const outcomes = d?.recorded_outcomes || {};
  return (
    <>
      <PageHead
        eyebrow="MARKET RESEARCH"
        title="Research overview"
        description="Signals, recorded outcomes, and the market behind them."
        action={<Refresh onClick={r.refresh} />}
      />
      <Resource resource={r}>
        <div className="finance-metrics">
          <Metric
            label="Signal records"
            value={number(d?.signal_count, 0)}
            note="Persisted by this installation"
          />
          <Metric
            label="Tracked instruments"
            value={number(d?.universe?.length, 0)}
            note="USDⓈ-M perpetual futures"
          />
          <Metric
            label="Latest scan"
            value={
              d?.data_age_seconds != null
                ? number(d.data_age_seconds / 60, 0) + " min ago"
                : "Awaiting data"
            }
            note={time(d?.last_scan_at)}
          />
          <Metric
            label="Research status"
            value={words(d?.status)}
            note="Based on completed scan freshness"
          />
        </div>
        <div className="finance-grid">
          <Panel title="Signal outcomes" aside={<Badge>Recorded data</Badge>}>
            <OutcomeDonut outcomes={outcomes} />
          </Panel>
          <Panel
            title="Signal activity"
            aside={
              <span className="muted chart-period">Last 14 days · UTC</span>
            }
          >
            <TrendChart
              data={d?.activity || []}
              valueKey="count"
              label="Signals"
              bars
            />
            <p className="panel-note">
              Daily signal counts from the stored ledger.
            </p>
          </Panel>
          <Panel title="Research workspace">
            <div className="execution-card">
              <BookOpen size={22} />
              <h3>A setup you can inspect.</h3>
              <p>
                Open a signal to review its entry, stop, targets, and the
                decision trace recorded when it was generated.
              </p>
              <Button asChild>
                <Link to="/signals">
                  Explore signals <ArrowUpRight size={14} />
                </Link>
              </Button>
              <div className="research-divider" />
              <p>
                Research outputs are experimental. Strategy performance has not
                been independently validated.
              </p>
              <Link className="text-link" to="/methodology">
                Read the methodology <ArrowRight size={14} />
              </Link>
            </div>
          </Panel>
        </div>
        <Panel
          title="Latest signals"
          aside={
            <Link className="text-link" to="/signals">
              View ledger <ArrowUpRight size={14} />
            </Link>
          }
        >
          <DataTable rows={d?.signals || []} columns={signalColumns} />
        </Panel>
        <div className="two-column">
          <Panel title="Instrument coverage">
            <div className="universe-list">
              {d?.universe?.map((coin: string) => (
                <Link key={coin} to={"/signals?coin=" + coin}>
                  <span className="coin-icon">{coin.slice(0, 1)}</span>
                  <strong>{coin}</strong>
                  <span>USDT perpetual</span>
                  <ArrowUpRight size={14} />
                </Link>
              ))}
            </div>
          </Panel>
          <Panel title="How a setup is formed">
            <ol className="method-list">
              <li>
                <span>01</span>
                <div>
                  <strong>Establish market direction</strong>
                  <p>
                    Closed candles, volatility, and higher-timeframe alignment.
                  </p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <strong>Evaluate confluence</strong>
                  <p>A defined score combines ADX, RSI, and relative volume.</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <strong>Record risk and outcome</strong>
                  <p>
                    Entry, stop, and target levels remain linked to each
                    decision.
                  </p>
                </div>
              </li>
            </ol>
          </Panel>
        </div>
      </Resource>
    </>
  );
}

export function Methodology() {
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

export function PublicPerformance() {
  const r = useResource("/api/v1/public/overview");
  return (
    <>
      <PageHead
        eyebrow="RECORDED EVIDENCE"
        title="Research performance"
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
              <Fact label="Operating mode" value={words(r.data?.mode)} />
              <Fact
                label="Persisted signal sample"
                value={number(r.data?.signal_count, 0)}
              />
              <Fact label="Out-of-sample edge" value="Not evaluated" />
              <Fact label="Independent validation" value="Not completed" />
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

export function PublicStatus() {
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
