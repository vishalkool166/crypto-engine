import { useLayoutEffect, useRef, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import gsap from "gsap";

const systems = [
  { label: "Trend continuation", name: "Follow", caption: "Structure and momentum agree.", line: "M 76 246 C 145 255,174 237,226 218 S 311 221,367 169 S 477 167,546 83" },
  { label: "Breakout + retest", name: "Break", caption: "A range resolves; confirmation follows.", line: "M 76 241 L 175 241 Q 202 239 224 225 L 267 225 L 302 220 L 334 146 L 374 167 L 417 166 L 460 95 L 546 95" },
  { label: "Range mean reversion", name: "Return", caption: "Price repeatedly tests its boundaries.", line: "M 76 191 C 120 124,149 145,182 211 S 255 250,292 185 S 362 124,400 191 S 483 245,546 180" },
  { label: "Momentum reversal", name: "Reconsider", caption: "A failed move changes the thesis.", line: "M 76 100 C 165 103,165 132,226 145 S 285 199,315 240 Q 339 272 372 220 S 480 158,546 188" },
] as const;
/** Visual explanation, not exchange candles. Buttons select one independent strategy's reading. */
export function SignalField() {
  const [active,setActive] = useState(0);
  const path = useRef<SVGPathElement>(null);
  useLayoutEffect(() => {
    if (!path.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const length = path.current.getTotalLength();
    const tween = gsap.fromTo(path.current,{strokeDasharray:length,strokeDashoffset:length}, {strokeDashoffset:0,duration:1.35,ease:"power3.inOut"});
    return () => { tween.kill(); };
  },[active]);
  return <div className="studio-figure" aria-label="Interactive illustration of four independent trading strategies">
    <div className="studio-figure-head"><span><i className="figure-index"/>The interpretation desk</span><span>AN INTERACTIVE STUDY / NOT LIVE MARKET DATA</span></div>
    <div className="studio-figure-body">
      <div className="studio-figure-plot">
        <svg viewBox="0 0 620 330" role="img" aria-label={`Illustrative pattern: ${systems[active].label}`}>
          <defs><pattern id="studioGrid" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M 34 0 L 0 0 0 34" stroke="#dcd9d2" fill="none" strokeWidth=".8"/></pattern></defs>
          <rect x="30" y="34" width="560" height="264" fill="url(#studioGrid)"/>
          <path d="M76 287 H556" stroke="#96968e" strokeWidth="1" strokeDasharray="2 5"/>
          <path d="M76 55 V288" stroke="#96968e" strokeWidth="1" strokeDasharray="2 5"/>
          <path d={systems[active].line} fill="none" stroke="#d0ccc2" strokeWidth="13" strokeLinecap="round" strokeLinejoin="round" opacity=".38"/>
          <path key={active} ref={path} d={systems[active].line} fill="none" stroke="#856a57" strokeWidth="2.7" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="76" cy="246" r="4" fill="#856a57" opacity=".6"/>
          <text x="76" y="315" fontSize="10" fill="#8b8a83" letterSpacing="2">OBSERVE</text>
          <text x="557" y="315" fontSize="10" textAnchor="end" fill="#8b8a83" letterSpacing="2">INTERPRET</text>
        </svg>
        <div className="studio-figure-caption"><span>FIG. {String(active+1).padStart(2,"0")}</span><div><strong>{systems[active].name}.</strong><p>{systems[active].caption}</p></div></div>
      </div>
      <div className="studio-figure-side"><div className="studio-figure-side-top"><span>FOUR INDEPENDENT READINGS</span><span>01 — 04</span></div>
        <div className="studio-figure-options" role="group" aria-label="Select a strategy to visualize">
          {systems.map((s,i)=><button type="button" key={s.label} aria-pressed={active===i} className={active===i?"selected":""} onClick={()=>setActive(i)}>
            <span>{String(i+1).padStart(2,"0")}</span><strong>{s.label}</strong><ArrowUpRight size={16}/>
          </button>)}
        </div>
        <div className="studio-figure-note">Each strategy forms its own hypothesis. The risk governor makes the final eligibility decision.</div>
      </div>
    </div>
  </div>;
}
