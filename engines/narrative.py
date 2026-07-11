import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def _session_name() -> str:
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return "London"
    if 13 <= hour < 17: return "London/NY Overlap"
    if 17 <= hour < 21: return "New York"
    if 0  <= hour < 8:  return "Asia"
    return "Off Hours"


def _get_live_risk(coin: str, direction: str) -> list:
    risks = []

    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if r:
            raw = r.get(f"funding:{coin}USDT")
            if raw:
                funding_pct = float(raw) * 100
                if abs(funding_pct) > 0.05:
                    risks.append(f"Funding  {funding_pct:.4f}%  — squeeze risk elevated")
                elif abs(funding_pct) > 0.03:
                    risks.append(f"Funding  {funding_pct:.4f}%  — monitor")
    except Exception:
        pass

    try:
        from data.cache import cache
        btc = cache.get_raw("btc_4h_data")
        if btc:
            btc_cls = btc.get("trend", {}).get("cls", "neutral")
            btc_adx = float(btc.get("adx") or 0)
            if direction == "LONG" and btc_cls == "bear" and btc_adx > 25:
                risks.append(f"BTC bearish (ADX {btc_adx:.0f}) — headwind for long")
            elif direction == "SHORT" and btc_cls == "bull" and btc_adx > 25:
                risks.append(f"BTC bullish (ADX {btc_adx:.0f}) — headwind for short")
            elif btc_cls == "neutral":
                risks.append("BTC neutral — no directional conflict")
    except Exception:
        pass

    try:
        from data.cache import cache
        btc = cache.get_raw("btc_4h_data")
        if btc:
            btc_adx = float(btc.get("adx") or 0)
            if btc_adx < 20:
                risks.append(f"BTC ADX {btc_adx:.0f} — market ranging, reduced conviction")
    except Exception:
        pass

    return risks


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

    s        = sweep.get("sweep", {}) if isinstance(sweep, dict) and "sweep" in sweep else sweep
    is_long  = direction == "LONG"
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

    sweep_lbl  = s.get("level_label", "key level") if s else "key level"
    sweep_lvl  = s.get("level",       0)            if s else 0
    sweep_age  = s.get("age_hours",   0)            if s else 0
    sweep_wick = s.get("wick_atr",    0)            if s else 0
    sweep_vol  = s.get("vol_ratio",   0)            if s else 0

    zone_type   = zone.get("type",        "zone") if zone else "zone"
    zone_top    = zone.get("top",         0)      if zone else 0
    zone_bottom = zone.get("bottom",      0)      if zone else 0
    zone_touch  = zone.get("touch_count", 0)      if zone else 0

    pattern  = trigger.get("pattern",  "")
    vol_mult = trigger.get("vol_mult", 1.0)

    risk_amt = sizing.get("risk_amt",       0)
    risk_pct = sizing.get("risk_pct",       0)
    pos_size = sizing.get("position_size",  0)
    leverage = sizing.get("leverage",       0)
    stake    = sizing.get("stake",          0)
    wr       = sizing.get("win_rate")
    dd       = sizing.get("drawdown_pct",   0)

    sweep_dir  = "lows"  if is_long else "highs"
    hunt_dir   = "below" if is_long else "above"
    reject_dir = "above" if is_long else "below"
    touch_str  = "pristine" if zone_touch == 0 else f"tested {zone_touch}x"
    vol_str    = "confirmed" if vol_mult >= 1.0 else "below average"

    sweep_age_warning = ""
    if sweep_age >= 6:
        sweep_age_warning = f"  ⚠ Sweep is {sweep_age:.1f}h old — setup aging"
    elif sweep_age >= 4:
        sweep_age_warning = f"  ⚠ Sweep is {sweep_age:.1f}h old — monitor freshness"

    lines = [
        f"{coin}USDT  {direction}  Grade {grade}",
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
    ]

    if sweep_age_warning:
        lines.append(sweep_age_warning)

    lines += [
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
        tp2_min = 2.5
        lines.append(f"  TP2     none — no structure at {tp2_min}R+")

    lines += [
        f"",
        f"Sizing",
        f"  Risk    ${risk_amt:.2f}  ({risk_pct:.2f}%)",
        f"  Stake   ${stake:.2f}  x{leverage}  =  ${pos_size:.2f}",
    ]

    if wr is not None:
        lines.append(f"  WR      {wr:.1f}%  DD  {dd:.1f}%")

    live_risks = _get_live_risk(coin, direction)
    if live_risks:
        lines.append(f"")
        lines.append(f"Risk")
        for r in live_risks:
            lines.append(f"  ⚠ {r}")
    else:
        lines += [
            f"",
            f"Risk     no significant factors",
        ]

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