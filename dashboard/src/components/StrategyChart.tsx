import { useMemo } from "react";
import { useResource, number } from "../api";
import { base } from "../lib/app";

type Candle = {time:string;open:number;high:number;low:number;close:number;volume:number};

type Annotation = {strategy:string;direction?:string;entry?:number;stop?:number;target?:number;reason?:string};

/** An SVG OHLC candlestick/volume visualization of STORED CLOSED Binance bars.
 * No simulated price series or fabricated market data are ever substituted. */
export function StrategyChart({coin, annotation}: {coin:string;annotation?:Annotation}) {
  const resource = useResource(base + "/strategy-lab/candles/" + coin, 60000);
  const bars = (resource.data?.candles || []) as Candle[];
  const chart = useMemo(() => {
    const data = bars.slice(-52);
    if (!data.length) return null;
    const priceMin = Math.min(...data.map(d=>d.low), ...(annotation?.entry?[annotation.entry,annotation.stop||annotation.entry,annotation.target||annotation.entry]:[]));
    const priceMax = Math.max(...data.map(d=>d.high), ...(annotation?.entry?[annotation.entry,annotation.stop||annotation.entry,annotation.target||annotation.entry]:[]));
    const extent = Math.max(priceMax-priceMin,priceMax*.0001);
    const lo=priceMin-extent*.085, hi=priceMax+extent*.085;
    const y=(price:number)=>12+(hi-price)/(hi-lo)*213;
    const w=760/(data.length||1);
    const maxVolume=Math.max(...data.map(d=>d.volume),1);
    return {data,y,w,maxVolume,lo,hi};
  },[bars,annotation?.entry,annotation?.stop,annotation?.target]);
  if (resource.loading) return <div className="se-chart-placeholder">Loading closed Binance candles…</div>;
  if (resource.error || !chart) return <div className="se-chart-placeholder">{resource.error?.message || "No stored closed candles yet. The next successful Binance scan will populate the chart."}</div>;
  const {data,y,w,maxVolume,lo,hi} = chart;
  const lines = [annotation?.entry,annotation?.stop,annotation?.target];
  const captions=["ENTRY","STOP","TARGET"];
  return <div className="se-market-visual">
    <div className="se-market-chart-header"><span className="se-chart-symbol">{coin}<small>/USDT · 4H</small></span><span className="se-chart-meta">Binance stored closes · {data.length} bars</span></div>
    <svg viewBox="0 0 860 326" role="img" aria-label={`Stored ${coin} Binance 4-hour candlesticks with volume${annotation?.direction?` and ${annotation.direction} levels`:""}`} preserveAspectRatio="xMidYMid meet">
      {[0,1,2,3,4].map((_,i)=><g key={i}><line x1="28" x2="785" y1={25+i*47} y2={25+i*47} className="se-chart-grid"/><text x="797" y={29+i*47} className="se-chart-text">{number(hi-(hi-lo)*(13+i*47)/213,2)}</text></g>)}
      <line x1="28" x2="785" y1="240" y2="240" className="se-chart-grid"/>
      {data.map((c,i)=>{
        const x=30+i*w+w*.5;
        const up = c.close >= c.open;
        const bodyTop=Math.min(y(c.close),y(c.open));
        const bodyHeight=Math.max(1.5,Math.abs(y(c.close)-y(c.open)));
        return <g key={c.time} className={up?"se-up":"se-down"}>
          <line x1={x} x2={x} y1={y(c.high)} y2={y(c.low)} stroke="currentColor" strokeWidth="1.4" />
          <rect x={x-Math.max(2,w*.29)} y={bodyTop} width={Math.max(4,w*.58)} height={bodyHeight} rx=".65" fill="currentColor" />
          <rect x={x-Math.max(2,w*.28)} y={313-c.volume/maxVolume*49} width={Math.max(4,w*.56)} height={c.volume/maxVolume*49} fill="currentColor" opacity=".35" />
        </g>;
      })}
      {annotation?.entry && lines.map((price,i)=>price && price>=lo && price<=hi?<g key={i}>
        <line x1="28" x2="784" y1={y(price)} y2={y(price)} className={i===1?"se-level-stop":"se-level-target"} strokeDasharray="5 6" />
        <rect x="783" y={y(price)-9} width="73" height="18" rx="3" className={i===1?"se-level-stop-bg":"se-level-bg"} />
        <text x="789" y={y(price)+3} className="se-level-label">{captions[i]}</text>
      </g>:null)}
      <text x="28" y="323" className="se-chart-text">{data[0].time.slice(0,10)}</text>
      <text x="662" y="323" className="se-chart-text">{data[data.length-1].time.slice(0,10)}</text>
    </svg>
    <div className="se-chart-footer"><span><i className="se-legend-up"/>Positive candle</span><span><i className="se-legend-down"/>Negative candle</span><span>Volumes below price · indicative levels, not live quotes</span></div>
  </div>;
}
