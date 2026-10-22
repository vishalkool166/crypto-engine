import { useState } from "react";
import { ArrowUpRight, LockKeyhole, CircleHelp, Radar, ShieldCheck, Eye, ToggleLeft, ToggleRight } from "lucide-react";
import { Link } from "react-router-dom";
import { request, useResource, number, time } from "../api";
import { base } from "../lib/app";
import { StrategyChart } from "./StrategyChart";
import { Button } from "./ui/button";

const descriptions:Record<string,string>={
 trend_continuation:"EMA alignment · ADX strength · pullback proximity",
 breakout_retest:"Range breakout · completed retest · volume",
 range_reversion:"Range-edge rejection · RSI extremes · regime",
 momentum_reversal:"Liquidity sweep · reclaim · momentum exhaustion",
};
const shortName=(s:string)=>s.replaceAll("_"," ");

type Candidate={strategy:string;direction?:string;score?:number;entry?:number;stop?:number;target?:number;reason:string;regime?:string;coin?:string;observed_at?:string;checks?:{name:string;actual:string|number;required:string;passed:boolean}[];target_source?:string;available_rr?:number};

/** Single operator board shows real shared-pipeline decisions; no mocked P&L. */
export function StrategyBoard({controlsEditable=false}:{controlsEditable?:boolean}) {
  const registry=useResource(base+"/strategy-lab/registry",20000);
  const history=useResource(base+"/strategy-lab/shadow?limit=150",25000);
  const [selected,setSelected]=useState("trend_continuation");
  const [coin,setCoin]=useState("ETH");
  const [saving,setSaving]=useState("");
  const [error,setError]=useState("");
  const strategies=(registry.data?.strategies||[]) as {id:string;label:string;scan_enabled:boolean;execution_enabled:boolean;updated_at?:string}[];
  const latest=(history.data?.items||[]).filter((e:any)=>e.strategy===selected && e.coin===coin)[0];
  const observed=latest as Candidate | undefined;
  async function setFlag(id:string,field:"scan_enabled"|"execution_enabled",value:boolean) {
    const item=strategies.find(i=>i.id===id);
    if(!item) return;
    setSaving(id);setError("");
    const state={scan_enabled:field==="scan_enabled"?value:item.scan_enabled,
      execution_enabled:field==="execution_enabled"?value:field==="scan_enabled"&&!value?false:item.execution_enabled};
    try {await request(base+"/strategy-lab/controls/"+id,{method:"PUT",body:JSON.stringify(state)});registry.refresh();}
    catch(e) {setError((e as Error).message);}
    finally {setSaving("");}
  }
  return <section className="se-control-board" aria-label="Unified strategy control center">
    <div className="se-board-intro"><div><p className="se-micro-label"><Radar size={13}/> UNIFIED STRATEGY ENGINE</p><h2>One pipeline. Four perspectives.</h2><p>Each strategy examines the same validated Binance candles independently. The arbiter chooses at most one direction per coin; the shared risk governor handles sizing and execution.</p></div><div className="se-board-status"><ShieldCheck size={17}/><span>Centralized risk & order journal</span></div></div>
    {registry.error && <p className="error-text">Strategy registry unavailable: {registry.error.message}</p>}
    {error && <p className="error-text" role="alert">{error}</p>}
    <div className="se-strategy-rail">
      {strategies.map((item,index)=>{
        const row=(history.data?.items||[]).find((r:any)=>r.strategy===item.id);
        const isSelected=selected===item.id;
        return <div key={item.id} className={"se-strategy-card "+(isSelected?"se-strategy-selected":"")}>
          <button type="button" onClick={()=>{setSelected(item.id);if(row?.coin)setCoin(row.coin);}} className="se-strategy-select" aria-pressed={isSelected}>
            <span className="se-micro-label">S0{index+1} <span className="se-card-indicator"/></span>
            <strong>{item.label}</strong><small>{descriptions[item.id]}</small>
            <span className="se-card-bottom"><span>{!item.scan_enabled?"OFFLINE":row?.reason==="candidate_detected"?"CANDIDATE":row?.reason?"EVALUATED":"AWAITING SCAN"}</span><ArrowUpRight size={14}/></span>
          </button>
          {controlsEditable && <div className="se-strategy-switches">
            <button disabled={!!saving} aria-label={`${item.label} scanning ${item.scan_enabled?"enabled":"disabled"}. Change state`} onClick={()=>setFlag(item.id,"scan_enabled",!item.scan_enabled)} title="Participates in every Binance scan" className={item.scan_enabled?"switch-on":""}>{item.scan_enabled?<ToggleRight size={19}/>:<ToggleLeft size={19}/>} Scan</button>
            <button disabled={!!saving||!item.scan_enabled} aria-label={`${item.label} execution ${item.execution_enabled?"enabled":"disabled"}. Change state`} onClick={()=>setFlag(item.id,"execution_enabled",!item.execution_enabled)} title="Allows eligible proposals to pass to the existing account-mode executor" className={item.execution_enabled?"switch-on":""}>{item.execution_enabled?<ToggleRight size={19}/>:<ToggleLeft size={19}/>} Execute</button>
          </div>}
        </div>;
      })}
      {!registry.loading&&!strategies.length&&<p className="se-empty">No initialized strategies found.</p>}
    </div>
    <div className="se-board-detail">
      <div className="se-board-chart">
        <div className="se-chart-toolbar"><div><p className="se-micro-label">PRICE STRUCTURE / CANDLES</p><h3>{strategies.find(s=>s.id===selected)?.label||shortName(selected)}</h3></div><label>Market <select value={coin} onChange={e=>{setCoin(e.target.value);}}>{(registry.data?.coins||["BTC","ETH","SOL"]).map((c:string)=><option key={c} value={c}>{c}/USDT</option>)}</select></label></div>
        <StrategyChart coin={coin} annotation={observed?.entry ? observed:undefined}/>
      </div>
      <aside className="se-decision-inspector"><p className="se-micro-label">LATEST STORED DECISION</p>
        {observed ? <><h3 className="se-decision-title">{observed.direction?observed.direction+" candidate":"No entry"}</h3><p className="se-rejection">{observed.reason.replaceAll("_"," ")}</p><dl><div><dt>Market</dt><dd>{coin}/USDT</dd></div><div><dt>Regime</dt><dd>{observed.regime||"Unknown"}</dd></div><div><dt>Heuristic score</dt><dd>{observed.score==null?"—":number(observed.score,1)}</dd></div><div><dt>Observed</dt><dd>{time(observed.observed_at)}</dd></div>{observed.entry&&<><div><dt>Proposed entry</dt><dd>{number(observed.entry,3)}</dd></div><div><dt>Protective stop</dt><dd>{number(observed.stop,3)}</dd></div><div><dt>Target</dt><dd>{number(observed.target,3)}</dd></div></>}</dl></>:<div className="se-inspector-empty"><Eye size={22}/><h3>Awaiting evaluation</h3><p>Stored decisions will appear after the next scanner cycle.</p></div>}
        {observed?.checks?.length ? <div className="strategy-checklist" aria-label="Individual strategy filter conditions"><h4>Condition-by-condition evidence</h4>{observed.checks.map((step,i)=><div className="strategy-check" key={i}><span className={step.passed?'passed':'failed'}>{step.passed?'PASS':'BLOCK'}</span><div><strong>{step.name}</strong><small>Observed: {String(step.actual)} · Needed: {step.required}</small></div></div>)}</div>:<p className="muted-copy">Detailed condition values will appear after the next completed scan on this version.</p>}
        {observed?.target_source && <p className="se-inspector-foot">Target basis: {observed.target_source.replaceAll('_',' ')} · Available reward: {observed.available_rr??'—'}R</p>}
        <p className="se-inspector-foot"><CircleHelp size={14}/> An eligible setup is not an exchange fill. All positions require risk approval.</p>
      </aside>
    </div>
    <div className="se-board-footer"><span><LockKeyhole size={15}/> Global paper/live authorization stays separate from strategy switches.</span><Button variant="outline" asChild><Link to="/strategy-lab">Open unified laboratory <ArrowUpRight size={14}/></Link></Button></div>
  </section>;
}
