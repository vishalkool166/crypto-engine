import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def _session_name() -> str:
    hour = datetime.now(timezone.utc).hour
    if 8 <= hour < 13:
        return "London"
    if 13 <= hour < 17:
        return "London/NY Overlap"
    if 17 <= hour < 21:
        return "New York"
    if 0 <= hour < 8:
        return "Asia"
    return "Off Hours"


def build(
    coin:      str,
    direction: str,
    grade:     str,
    context:   dict,
    sweep:     dict,
    zone:      dict,
    trigger:   dict,
    risk:      dict,
    sizing:    dict,
) -> str:

    s        = sweep.get("sweep", {})
    is_long  = direction == "LONG"
    dir_str  = "LONG" if is_long else "SHORT"
    session  = _session_name()

    entry    = trigger.get("entry_price", 0)
    sl       = risk.get("sl", 0)
    tp1      = risk.get("tp1", 0)
    tp2      = risk.get("tp2")
    sl_pct   = risk.get("sl_pct", 0)
    rr1      = risk.get("rr1", 0)
    rr2      = risk.get("rr2")
    tp1_lbl  = risk.get("tp1_label", "")
    tp2_lbl  = risk.get("tp2_label", "")
    sl_rsn   = risk.get("sl_reason", "")

    sweep_lbl   = s.get("level_label", "key level")
    sweep_lvl   = s.get("level", 0)
    sweep_age   = s.get("age_hours", 0)
    sweep_wick  = s.get("wick_atr", 0)
    sweep_vol   = s.get("vol_ratio", 0)

    zone_type   = zone.get("type", "zone")
    zone_top    = zone.get("top", 0)
    zone_bottom = zone.get("bottom", 0)
    zone_touch  = zone.get("touch_count", 0)

    pattern     = trigger.get("pattern", "")
    vol_mult    = trigger.get("vol_mult", 1.0)

    risk_amt    = sizing.get("risk_amt", 0)
    risk_pct    = sizing.get("risk_pct", 0)
    pos_size    = sizing.get("position_size", 0)
    leverage    = sizing.get("leverage", 0)
    stake       = sizing.get("stake", 0)
    wr          = sizing.get("win_rate")
    dd          = sizing.get("drawdown_pct", 0)

    sweep_dir   = "lows" if is_long else "highs"
    hunt_dir    = "below" if is_long else "above"
    reject_dir  = "above" if is_long else "below"
    touch_str   = "pristine" if zone_touch == 0 else f"tested {zone_touch}x"
    vol_str     = "confirmed" if vol_mult >= 1.0 else "below average"

    lines = [
        f"{coin}USDT  {dir_str}  Grade {grade}",
        f"{'─' * 38}",
        f"Session  {session}",
        f"",
        f"Context",
        f"  4H trend {'bullish' if is_long else 'bearish'} — "
        f"price {'above' if is_long else 'below'} EMA20",
        f"",
        f"Sweep",
        f"  {sweep_lbl} at {sweep_lvl:.4f} swept {sweep_age:.1f}h ago",
        f"  Wick {hunt_dir} level  {sweep_wick:.1f}x ATR",
        f"  Volume  {sweep_vol:.1f}x average",
        f"  Smart money hunted {sweep_dir} — reversed {reject_dir}",
        f"",
        f"Zone",
        f"  {zone_type}  {zone_bottom:.4f} – {zone_top:.4f}",
        f"  Condition  {touch_str}",
        f"",
        f"Trigger",
        f"  15M {pattern.replace('_', ' ').title()} at {entry:.4f}",
        f"  Volume  {vol_str}  ({vol_mult:.1f}x MA)",
        f"",
        f"Levels",
        f"  Entry   {entry:.4f}",
        f"  SL      {sl:.4f}  ({sl_pct:.2f}%)  —  {sl_rsn}",
        f"  TP1     {tp1:.4f}  ({rr1:.1f}R)  —  {tp1_lbl}",
    ]

    if tp2:
        lines.append(f"  TP2     {tp2:.4f}  ({rr2:.1f}R)  —  {tp2_lbl}")
    else:
        tp2_min_rr = SE["tp2_min_rr"]
        lines.append(f"  TP2     none — no structure at {tp2_min_rr}R+")
    lines += [
        f"",
        f"Sizing",
        f"  Risk    ${risk_amt:.2f}  ({risk_pct:.2f}%)",
        f"  Stake   ${stake:.2f}  x{leverage}  =  ${pos_size:.2f}",
    ]

    if wr is not None:
        lines.append(f"  WR      {wr:.1f}%  DD  {dd:.1f}%")

    lines += [
        f"",
        f"Time stop  8h from entry",
        f"",
        f"Thesis",
        f"  Smart money swept {sweep_dir} at {sweep_lvl:.4f},",
        f"  collected liquidity, displaced {'up' if is_long else 'down'}.",
        f"  Entering on retest of origin zone.",
        f"  Invalid if 15M closes {'below' if is_long else 'above'} {sl:.4f}.",
    ]

    return "\n".join(lines)