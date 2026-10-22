import { useMemo, useState, type FormEvent } from "react";
import { Activity, FlaskConical, ShieldCheck, Telescope, GitCompareArrows } from "lucide-react";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { request, useResource, number, time } from "../api";
import { base } from "../lib/app";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { PageHead, Panel, Metric, DataTable, Resource } from "../components/workspace";
import { StrategyBoard } from "../components/StrategyBoard";
import { Research } from "./research";

type Experiment = {
  experiment_id: number; coin: string; strategy: string; simulated: boolean;
  version: string; bars: number; holdout_from: string; funding_modeled: boolean;
  data_sha256: string; status: string; development: Record<string, any>;
  holdout: Record<string, any>; limitations: string[]; trades: Array<{ exit_at: string; net_pnl: number; segment: string }>;
  rejection_counts: Record<string, number>;
};

export function StrategyLab() {
  const registry = useResource(base + "/strategy-lab/registry", 120000);
  const history = useResource(base + "/strategy-lab/experiments", 30000);
  const actualPerformance = useResource(base + "/strategy-lab/performance", 30000);
  const shadow = useResource(base + "/strategy-lab/shadow", 30000);
  const [coin, setCoin] = useState("ETH");
  const [strategy, setStrategy] = useState("breakout_retest");
  const [minimumVolume, setMinimumVolume] = useState("1.2");
  const [result, setResult] = useState<Experiment | null>(null);
  const [intel, setIntel] = useState<any>(null);
  const [comparison,setComparison] = useState<any>(null);
  const [comparing,setComparing] = useState(false);
  const [pending, setPending] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [intelError, setIntelError] = useState("");
  const [showEvidence,setShowEvidence] = useState(false);
  const equity = useMemo(() => {
    let cumulative = 1000;
    return result?.trades.map((trade, idx) => {
      cumulative += trade.net_pnl;
      return { index: idx + 1, equity: Number(cumulative.toFixed(2)), segment: trade.segment };
    }) || [];
  }, [result]);
  async function run(e: FormEvent) {
    e.preventDefault();
    setPending(true); setError(""); setResult(null);
    try {
      const result = await request(base + "/strategy-lab/run", {
        method: "POST", body: JSON.stringify({ coin, strategy, min_volume_ratio: Number(minimumVolume) }),
      });
      setResult(result); history.refresh();
    } catch (e) { setError((e as Error).message); }
    finally { setPending(false); }
  }
  async function compareAll() {
    setComparing(true);setError("");setComparison(null);
    try {
      const data=await request(base+"/strategy-lab/compare",{
        method:"POST",body:JSON.stringify({coin,strategy,min_volume_ratio:Number(minimumVolume)})
      });
      setComparison(data);history.refresh();
    } catch (e) {setError((e as Error).message);}
    finally {setComparing(false);}
  }
  async function checkMarket() {
    setChecking(true); setIntelError(""); setIntel(null);
    try { setIntel(await request(base + "/market-intelligence/" + coin)); }
    catch (e) { setIntelError((e as Error).message); }
    finally { setChecking(false); }
  }
  return (
    <>
      <PageHead eyebrow="SIGNAL ENGINE 3.1 / PRIVATE" title="The unified laboratory."
        description="Inspect and control the same four strategies that run in the main scanner. Reproduce their historical outcomes in one workspace." />
      <section className="lab-hero" aria-label="Research and execution separation">
        <div><span className="lab-kicker">SINGLE STRATEGY SOURCE · FOUR MODULES</span><h2>One set of rules. Every market state.</h2><p>Every strategy now participates in the main scanning path. Controls below govern whether its proposals can reach the existing protected Binance executor. Experiments remain simulations—not profitability certificates.</p></div>
        <div className="lab-hero-side"><ShieldCheck size={24} /><strong>One risk governor</strong><span>The account-level live switch remains independent.</span></div>
      </section>
      <StrategyBoard controlsEditable />
      <Panel title="Backtest a registered strategy" aside={<Badge tone="neutral">Replay only · no orders</Badge>}>
        <form className="lab-form" onSubmit={run}>
          <label>Binance market<select required value={coin} onChange={e => {setCoin(e.target.value);setIntel(null);}}>
            {(registry.data?.coins || ["ETH","SOL","BNB"]).map((c:string)=><option key={c} value={c}>{c}/USDT</option>)}
          </select></label>
          <label>Strategy<select value={strategy} onChange={e=>setStrategy(e.target.value)}>
            {(registry.data?.strategies || []).map((s:any)=><option key={s.id} value={s.id}>{s.label}</option>)}
          </select></label>
          <label>Relative volume floor<select value={minimumVolume} onChange={e=>setMinimumVolume(e.target.value)}>
            {["0.8","1.0","1.2","1.5","2.0","2.5"].map(x=><option value={x} key={x}>{x} × average</option>)}
          </select></label>
          <Button type="submit" disabled={pending || comparing || !registry.data?.strategies?.length}><FlaskConical size={15}/>{pending?"Evaluating…":"Replay selected"}</Button>
          <Button type="button" variant="outline" disabled={pending || comparing || !registry.data?.strategies?.length} onClick={()=>void compareAll()}><GitCompareArrows size={15}/>{comparing?"Comparing…":"Compare all four"}</Button>
        </form>
        {error && <p role="alert" className="error-text">{error}</p>}
        <p className="lab-small">Uses existing *closed* cached Binance candles, a 1× notional ceiling, next-open simulated fills, transaction costs and conservative stop-first handling. Funding and order-book liquidity are not modeled.</p>
        {comparison && <div className="se-comparison-result">
          <div className="lab-result-heading"><div><span className="lab-kicker">SIDE-BY-SIDE CHRONOLOGICAL HOLDOUT</span><h3>Four hypotheses. One dataset.</h3></div><Badge tone="amber">Not certified</Badge></div>
          <div className="table-scroll" role="region" aria-label="Strategy holdout comparison"><table><thead><tr><th>Strategy</th><th>Trades</th><th>Win rate</th><th>Net P&L</th><th>Expectancy</th><th>Drawdown</th></tr></thead><tbody>
            {(comparison.items||[]).map((item:any)=><tr key={item.strategy}><td>{item.strategy.replaceAll("_"," ")}</td><td>{number(item.holdout?.trades,0)}</td><td>{item.holdout?.win_rate_pct==null?"—":number(item.holdout.win_rate_pct,2)+"%"}</td><td>{number(item.holdout?.net_pnl_usdt,2)} USDT</td><td>{item.holdout?.net_expectancy_usdt==null?"—":number(item.holdout.net_expectancy_usdt,2)}</td><td>{number(item.holdout?.max_drawdown_pct,2)}%</td></tr>)}
          </tbody></table></div>
          <p className="lab-small">{comparison.notice} These figures are separate simulations, not portfolio results or forecast returns.</p>
        </div>}
        {result && <div className="lab-result">
          <div className="lab-result-heading"><div><span className="lab-kicker">EXPERIMENT #{result.experiment_id} / {result.coin}</span><h3>{result.strategy.replaceAll("_"," ")}</h3></div><Badge tone="amber">Uncertified</Badge></div>
          <div className="metric-grid">
            <Metric label="Holdout trades" value={number(result.holdout.trades,0)} note="Chronological holdout" />
            <Metric label="Holdout net P&L" value={number(result.holdout.net_pnl_usdt,2)+" USDT"} note="Simulated, after fees/slippage" />
            <Metric label="Holdout expectancy" value={result.holdout.net_expectancy_usdt == null ? "Not available" : number(result.holdout.net_expectancy_usdt,2)+" USDT"} note="Per closed simulated trade" />
            <Metric label="Max recorded drawdown" value={number(result.holdout.max_drawdown_pct,2)+"%"} note="Closed equity only; not intratrade risk" />
          </div>
          {equity.length>1 && <div className="lab-chart" aria-label="Simulated closed equity curve"><ResponsiveContainer width="100%" height={220}><LineChart data={equity} margin={{top:12,right:22,left:0,bottom:0}}><CartesianGrid strokeDasharray="3 6" opacity={.2}/><XAxis dataKey="index" tickLine={false} axisLine={false}/><YAxis domain={["auto","auto"]} width={58} tickLine={false} axisLine={false}/><Tooltip formatter={(v:any)=>[Number(v).toFixed(2)+" USDT","Simulation equity"]}/><Line type="linear" dataKey="equity" stroke="currentColor" dot={false} strokeWidth={2}/></LineChart></ResponsiveContainer></div>}
          <div className="lab-run-meta"><span>Bars: {result.bars}</span><span>Holdout starts: {result.holdout_from}</span><span>Dataset SHA-256: {result.data_sha256.slice(0,14)}…</span></div>
          <p className="lab-small">{result.limitations.join(" · ")}</p>
        </div>}
      </Panel>
      <div className="lab-columns">
        <Panel title="Binance futures intelligence" aside={<Badge tone="neutral">Public aggregates</Badge>}>
          <p className="lab-small">Exchange-level sentiment, top-account ratios, open interest and funding—not private wallets or verified whale trades.</p>
          <Button variant="outline" disabled={checking} onClick={()=>void checkMarket()}><Telescope size={16}/>{checking?"Fetching…":"Inspect " + coin + " market"}</Button>
          {intelError && <p role="alert" className="error-text">{intelError}</p>}
          {intel && <><div className="lab-intel-grid">
            {[["Funding rate",intel.funding_rate == null ? "Unavailable" : (intel.funding_rate*100).toFixed(4)+"%"],["Open interest",intel.open_interest_contracts == null?"Unavailable":number(intel.open_interest_contracts,0)+" contracts"],["Global long / short",intel.global_long_short_ratio == null?"Unavailable":number(intel.global_long_short_ratio,3)],["Top-account long / short",intel.top_account_long_short_ratio == null?"Unavailable":number(intel.top_account_long_short_ratio,3)]].map(([key,value])=><div key={key}><span>{key}</span><strong>{value}</strong></div>)}
          </div><p className="lab-small">Observed {time(intel.observed_at)}. Missing Binance endpoints remain unavailable, not estimated.</p></>}
        </Panel>
        <Panel title="Main-pipeline decision history" aside={<Badge tone="blue">Recorded scanner decisions</Badge>}>
          <Resource resource={shadow}>
            <p className="lab-small">Each strategy is evaluated in the main pipeline. All proposals and rejection reasons are retained, including candidates not selected for execution.</p>
            <DataTable rows={shadow.data?.items?.slice(0,12) || []} columns={[{key:"coin",label:"Coin"},{key:"strategy",label:"Strategy",render:(r:any)=>r.strategy.replaceAll("_"," ")},{key:"reason",label:"Decision",render:(r:any)=>r.reason.replaceAll("_"," ")}]} />
          </Resource>
        </Panel>
      </div>
      <Panel title="Executed-trade attribution" aside={<Badge tone="neutral">Recorded closed trades only</Badge>}>
        <Resource resource={actualPerformance}>
          <DataTable rows={actualPerformance.data?.items||[]} empty="No closed strategy-owned trades yet" columns={[
            {key:"strategy",label:"Strategy",render:(r:any)=>r.strategy.replaceAll("_"," ")},
            {key:"mode",label:"Account mode",render:(r:any)=>r.mode},
            {key:"closed_trades",label:"Closed trades"},
            {key:"net_pnl_usdt",label:"Recorded net P&L",render:(r:any)=>number(r.net_pnl_usdt,3)+" USDT"},
          ]}/>
          <p className="lab-small">{actualPerformance.data?.note||"Paper, live, and simulated experiments must never be combined."}</p>
        </Resource>
      </Panel>
      <Panel title="Reproducible experiment history" aside={<span className="lab-small">Stored in the original database</span>}>
        <Resource resource={history}>
          <DataTable rows={history.data?.items || []} columns={[{key:"id",label:"Run"},{key:"coin",label:"Pair"},{key:"strategy",label:"Strategy",render:(r:any)=>r.strategy.replaceAll("_"," ")},{key:"created_at",label:"Timestamp",render:(r:any)=>time(r.created_at)},{key:"holdout",label:"Holdout trades",render:(r:any)=>number(r.summary?.holdout?.trades,0)},{key:"pnl",label:"Simulated net",render:(r:any)=>number(r.summary?.holdout?.net_pnl_usdt,2)}]} />
        </Resource>
      </Panel>
      <details className="se-evidence-drawer" onToggle={e=>setShowEvidence(e.currentTarget.open)}><summary>Research evidence & AI assistant <GitCompareArrows size={15}/></summary>{showEvidence && <div className="se-evidence-body"><Research embedded /></div>}</details>
      <p className="lab-small"><Activity size={14} style={{verticalAlign:"middle"}} /> Production scanning and simulated replay share the same four rule implementations. An experiment never places orders or certifies profitability. Strategy execution is controlled above and globally by the existing paper/live switch.</p>
    </>
  );
}
