import { SignalField } from "../components/SignalField";
import { ArrowDown, ArrowRight, ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useResource, number, time, words } from "../api";

import { Badge } from "../components/ui/badge";

import {
  Panel,
  PageHead,
  Resource,
  Refresh,
  Fact,
  DataTable,
  OutcomeBars,
  signalColumns,
} from "../components/workspace";
import { TrendChart, OutcomeDonut } from "../components/Analytics";

/** The public home is an editorial explanation layered over real, stored research data.
 * The kinetic field is labeled abstract; no invented trading results appear in it. */
export function PublicOverview() {
  const r = useResource("/api/v1/public/overview");
  const d = r.data;
  const outcomes = d?.recorded_outcomes || {};
  return <div className="studio-home">
    <section className="studio-hero" aria-labelledby="studio-title">
      <div className="studio-hero-meta"><span>Independent research / system-led decisions</span><span>EST. IN EVIDENCE, NOT CERTAINTY</span></div>
      <h1 id="studio-title">Every move<br/><em>has a reason.</em></h1>
      <p className="studio-hero-lede">Four perspectives on an unpredictable market. One accountable decision process. A clearer way to see why a signal exists, and why another doesn't.</p>
      <div className="studio-hero-actions"><Link className="studio-button-dark" to="/signals">Explore the signal ledger <ArrowUpRight size={17}/></Link><Link className="studio-button-quiet" to="/methodology">Read the methodology <ArrowRight size={16}/></Link></div>
      <div className="studio-hero-art"><SignalField/></div>
      <div className="studio-hero-bottom"><span>MARKET RESEARCH, MADE LEGIBLE.</span><span>SCROLL TO FOLLOW THE REASONING <ArrowDown size={14}/></span></div>
    </section>

    <section className="studio-thesis" aria-labelledby="studio-thesis-title">
      <span className="studio-small-heading">The discipline</span>
      <div><h2 id="studio-thesis-title">A signal deserves<br/><em>a second look.</em></h2><p>Markets create endless opportunities to act. Our system is designed to examine them first. Every proposed entry moves through independent strategy rules, conflict resolution, and account-level risk checks.</p></div>
      <div className="studio-large-bars" aria-hidden="true"><span/><span/><span/></div>
    </section>

    <section className="studio-narrative" aria-labelledby="studio-narrative-title">
      <div className="studio-narrative-sticky"><div className="studio-narrative-copy"><span className="studio-small-heading">How an idea becomes a decision</span><h2 id="studio-narrative-title">The engine<br/><em>shows its work.</em></h2><p>From raw market context to a recorded outcome, the decision is built in distinct stages. Explore each one as you move through the page.</p><Link to="/methodology" className="studio-button-quiet">Inspect the rules <ArrowUpRight size={16}/></Link></div>
        <div className="studio-narrative-stage" aria-hidden="true"><div className="studio-stage-grid"/><div className="studio-stage-lines"><i/><i/><i/><i/></div><div className="studio-stage-gate"><span className="brand-symbol"><span/><span/><span/></span><small>RISK GATE</small></div></div>
      </div>
      <div className="studio-narrative-steps">
        <article className="studio-narrative-step" data-story-step="0"><span>01 / INPUT</span><h3>Observe the market.</h3><p>Binance price structure, closed candles, volatility and funding feed one timestamped view of conditions.</p></article>
        <article className="studio-narrative-step" data-story-step="1"><span>02 / STRATEGIES</span><h3>Let four ideas disagree.</h3><p>Continuation, breakout, reversion and reversal independently evaluate the same snapshot.</p></article>
        <article className="studio-narrative-step" data-story-step="2"><span>03 / RISK</span><h3>Respect the limits.</h3><p>Conflicts, order permissions and account exposure are resolved before any eligible order reaches execution.</p></article>
        <article className="studio-narrative-step" data-story-step="3"><span>04 / RECORD</span><h3>Keep the evidence.</h3><p>Signals and rejections remain available for inspection. Historical outcomes aren't forecasts.</p></article>
      </div>
    </section>

    <section className="studio-evidence" aria-labelledby="studio-evidence-heading">
      <div className="studio-evidence-intro"><span className="studio-small-heading">The public record</span><div><h2 id="studio-evidence-heading">Make the work<br/><em>visible.</em></h2><p>Numbers below come from stored engine records, not marketing simulations. Missing observations stay missing.</p></div><Refresh onClick={r.refresh}/></div>
      <Resource resource={r}>
        <div className="studio-evidence-stats">
          <div><span>Signals recorded</span><strong>{number(d?.signal_count,0)}</strong><small>Persisted observations</small></div>
          <div><span>Market coverage</span><strong>{number(d?.universe?.length,0)}</strong><small>Configured instruments</small></div>
          <div><span>Most recent scan</span><strong>{d?.data_age_seconds != null ? number(d.data_age_seconds / 60,0)+"m" : "—"}</strong><small>{time(d?.last_scan_at)}</small></div>
          <div><span>Current status</span><strong className="studio-stat-text">{words(d?.status)}</strong><small>Derived from service freshness</small></div>
        </div>
        <div className="studio-evidence-charts"><Panel title="Recorded outcomes" aside={<Badge>Ledger labels</Badge>}><OutcomeDonut outcomes={outcomes}/></Panel><Panel title="Recent activity" aside={<span className="muted chart-period">14 days · UTC</span>}><TrendChart data={d?.activity || []} valueKey="count" label="Signals" bars/><p className="panel-note">Actual stored signal counts.</p></Panel></div>
        <div className="studio-ledger-heading"><h3>Every thesis leaves a record.</h3><Link to="/signals">View all signals <ArrowUpRight size={16}/></Link></div>
        <Panel><DataTable rows={d?.signals || []} columns={signalColumns}/></Panel>
      </Resource>
    </section>
    <section className="studio-finale"><span className="studio-small-heading">Research with restraint</span><h2>Knowing when to<br/><em>stay out</em> matters.</h2><Link to="/methodology" className="studio-button-dark">Understand the method <ArrowUpRight size={17}/></Link><p>No independently verified profitable edge is claimed. Research remains experimental.</p></section>
  </div>;
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
            body: "Four independent 4-hour setups assess trend continuation, breakout/retest, range reversion and momentum reversal. Any can reject the market independently.",
          },
          {
            n: "03",
            title: "Score",
            body: "Each candidate receives a heuristic grade from ADX, volume and regime conditions. An arbiter rejects opposing signals, and the risk governor independently validates eligibility. Grades are not win probabilities.",
          },
          {
            n: "04",
            title: "Risk",
            body: "Each strategy uses strategy-specific structural invalidation and a market-observed exit zone (or a measured breakout range where appropriate). Insufficient available reward vetoes a setup. The shared sizing and order governor applies the configured coin limits; live results can differ from candle-close proposals.",
          },
        ].map((m) => (
          <Panel key={m.n} className="method-card">
            <span>{m.n}</span>
            <h2>{m.title}</h2>
            <p>{m.body}</p>
          </Panel>
        ))}
      </div>
      <section className="methodology-strategies" aria-label="Four independently evaluated strategies">
        <div className="methodology-intro"><p className="eyebrow">ONE ENGINE · FOUR INDEPENDENT IDEAS</p><h2>Every strategy needs its own evidence.</h2><p>All four use validated closed Binance candles. Each one can reject a market independently; qualifying proposals then meet at one conflict manager and risk governor.</p></div>
        {[
          {number:'01',title:'Trend continuation',condition:'Trending markets',entry:'Aligned EMA20 / EMA50 / EMA200, confirmed volume and a pullback near the fast average.',stop:'Beyond the prior completed swing invalidation with a modest volatility buffer.',exit:'Nearest observed opposing structure; reject where reward is insufficient.'},
          {number:'02',title:'Breakout and retest',condition:'Range expansion',entry:'Completed breakout on volume followed by a separate confirmed retest candle.',stop:'Beyond the retest rejection point and failed breakout boundary.',exit:'Observed opposing levels; measured prior range only when the breakout enters uncharted price territory.'},
          {number:'03',title:'Range mean reversion',condition:'Established sideways range',entry:'A Bollinger-band excursion and reclaim with RSI confirmation and range regime.',stop:'Beyond the range extreme that invalidates the rejection.',exit:'Range midpoint capped by earlier opposing structure.'},
          {number:'04',title:'Momentum reversal',condition:'Failed sweep and reclaim',entry:'A sweep of the previous range, price reclaim and momentum validation.',stop:'Beyond the sweep extreme that invalidates the reversal.',exit:'Nearest observable swing support or resistance.'}
        ].map(s=><article className="methodology-strategy" key={s.number}><span>{s.number}</span><div><p className="eyebrow">{s.condition}</p><h3>{s.title}</h3></div><dl><div><dt>Entry</dt><dd>{s.entry}</dd></div><div><dt>Invalidation</dt><dd>{s.stop}</dd></div><div><dt>Exit hypothesis</dt><dd>{s.exit}</dd></div></dl></article>)}
      </section>
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
            <Fact label="Mode" value={words(r.data?.mode || "unavailable")} />
            <Fact label="Observed at" value={time(r.data?.timestamp)} />
          </dl>
        </Panel>
      </Resource>
    </>
  );
}
