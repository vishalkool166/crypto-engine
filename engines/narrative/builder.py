import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def build(
    coin:          str,
    direction:     str,
    grade:         str,
    regime_result: object,
    trend_result:  object,
    reversion:     object,
    ict_result:    object,
    risk_result:   object,
    sizing_result: object,
    session:       str,
) -> str:
    is_long   = direction == "LONG"
    entry     = float(risk_result.entry)
    sl        = float(risk_result.sl)
    tp1       = float(risk_result.tp1)
    tp2       = risk_result.tp2
    sl_pct    = float(risk_result.sl_pct)
    rr1       = float(risk_result.rr1)
    rr2       = risk_result.rr2
    tp1_label = risk_result.tp1_label
    tp2_label = risk_result.tp2_label
    sl_reason = risk_result.sl_reason

    regime_label = regime_result.label if regime_result else "unknown"
    adx          = float(regime_result.adx) if regime_result else 0.0
    trend_dir    = trend_result.direction if trend_result else direction
    alignment    = trend_result.alignment if trend_result else "none"
    daily_bias   = trend_result.daily_bias if trend_result else "NEUTRAL"
    weekly_bias  = trend_result.weekly_bias if trend_result else "NEUTRAL"

    rsi_val      = float(reversion.rsi) if reversion else 0.0
    rev_extreme  = bool(reversion.extreme) if reversion else False
    bb_touch     = bool(reversion.bb_touch) if reversion else False

    sweep        = ict_result.sweep if ict_result else None
    zone         = ict_result.zone  if ict_result else None

    sweep_label  = sweep.label     if sweep else "key level"
    sweep_level  = float(sweep.level)     if sweep else 0.0
    sweep_age    = float(sweep.age_hours) if sweep else 0.0
    sweep_wick   = float(sweep.wick_atr)  if sweep else 0.0
    sweep_vol    = float(sweep.vol_ratio) if sweep else 0.0

    zone_type    = zone.type       if zone else "zone"
    zone_top     = float(zone.top)    if zone else 0.0
    zone_bottom  = float(zone.bottom) if zone else 0.0
    zone_touch   = int(zone.touch_count) if zone else 0

    risk_amt     = float(sizing_result.risk_amt)      if sizing_result else 0.0
    risk_pct     = float(sizing_result.risk_pct)      if sizing_result else 0.0
    stake        = float(sizing_result.stake)         if sizing_result else 0.0
    leverage     = int(sizing_result.leverage)        if sizing_result else 0
    pos_size     = float(sizing_result.position_size) if sizing_result else 0.0
    win_rate     = sizing_result.win_rate             if sizing_result else None
    drawdown     = float(sizing_result.drawdown_pct)  if sizing_result else 0.0
    regime_mult  = float(sizing_result.regime_mult)   if sizing_result else 1.0

    sweep_dir    = "lows"  if is_long else "highs"
    hunt_dir     = "below" if is_long else "above"
    reject_dir   = "above" if is_long else "below"
    touch_str    = "pristine" if zone_touch == 0 else f"tested {zone_touch}x"

    sweep_age_note = ""
    if sweep_age >= 6:
        sweep_age_note = f"  ⚠ Sweep is {sweep_age:.1f}h old — setup aging"
    elif sweep_age >= 4:
        sweep_age_note = f"  ⚠ Sweep is {sweep_age:.1f}h old — monitor freshness"

    regime_note = _regime_note(regime_label, adx, regime_mult)
    rev_note    = _reversion_note(rsi_val, rev_extreme, bb_touch, is_long)
    align_note  = _alignment_note(alignment, daily_bias, weekly_bias, direction)
    risk_notes  = _live_risk_notes(coin, direction)

    lines = [
        f"{coin}USDT  {direction}  Grade {grade}",
        f"{'─' * 38}",
        f"Session   {session}",
        f"",
        f"Regime",
        f"  {regime_label.title()} — ADX {adx:.1f}",
        f"  {regime_note}",
        f"",
        f"Trend",
        f"  4H {trend_dir} · Daily {daily_bias} · Weekly {weekly_bias}",
        f"  {align_note}",
        f"",
        f"Entry Timing",
        f"  {rev_note}",
        f"",
        f"Sweep",
        f"  {sweep_label} at {sweep_level:.4f} swept {sweep_age:.1f}h ago",
        f"  Wick {hunt_dir} level  {sweep_wick:.1f}x ATR",
        f"  Volume  {sweep_vol:.1f}x average",
        f"  Smart money hunted {sweep_dir} — reversed {reject_dir}",
    ]

    if sweep_age_note:
        lines.append(sweep_age_note)

    lines += [
        f"",
        f"Zone",
        f"  {zone_type}  {zone_bottom:.4f} – {zone_top:.4f}",
        f"  Condition  {touch_str}",
        f"",
        f"Levels",
        f"  Entry   {entry:.4f}",
        f"  SL      {sl:.4f}  ({sl_pct:.2f}%)  —  {sl_reason}",
        f"  TP1     {tp1:.4f}  ({rr1:.1f}R)  —  {tp1_label}",
    ]

    if tp2:
        lines.append(f"  TP2     {tp2:.4f}  ({rr2:.1f}R)  —  {tp2_label}")
    else:
        lines.append(f"  TP2     none — no structure at {HE_tp2_min_rr():.1f}R+")

    lines += [
        f"",
        f"Sizing",
        f"  Risk    ${risk_amt:.2f}  ({risk_pct:.2f}%)",
        f"  Stake   ${stake:.2f}  x{leverage}  =  ${pos_size:.2f}",
        f"  Regime mult  {regime_mult:.2f}x",
    ]

    if win_rate is not None:
        lines.append(f"  WR      {win_rate:.1f}%  DD  {drawdown:.1f}%")

    if risk_notes:
        lines.append(f"")
        lines.append(f"Risk")
        for note in risk_notes:
            lines.append(f"  ⚠ {note}")
    else:
        lines += [f"", f"Risk     no significant factors"]

    lines += [
        f"",
        f"Thesis",
        f"  Smart money swept {sweep_dir} at {sweep_level:.4f},",
        f"  collected liquidity, displaced {'up' if is_long else 'down'}.",
        f"  {regime_label.title()} regime — {alignment} HTF alignment.",
        f"  RSI pullback confirmed entry window.",
        f"  Entering on retest of {zone_type} origin zone.",
        f"  Invalid if 15M closes {'below' if is_long else 'above'} {sl:.4f}.",
    ]

    return "\n".join(lines)


def HE_tp2_min_rr() -> float:
    return cfg.HYBRID_ENGINE.get("tp2_min_rr", 3.5)


def _regime_note(label: str, adx: float, regime_mult: float) -> str:
    if label == "trending":
        return f"Full size — strong trend ADX {adx:.0f} · mult {regime_mult:.2f}x"
    if label == "ranging":
        return f"Reduced size — ranging market · mult {regime_mult:.2f}x"
    if label == "choppy":
        return f"Minimal size — choppy conditions · mult {regime_mult:.2f}x"
    if label == "volatile":
        return f"Near-zero size — volatile market · mult {regime_mult:.2f}x"
    return f"Standard size · mult {regime_mult:.2f}x"


def _reversion_note(
    rsi:     float,
    extreme: bool,
    bb:      bool,
    is_long: bool,
) -> str:
    parts = []
    if is_long:
        if extreme:
            parts.append(f"RSI extreme pullback {rsi:.1f} — strong entry window")
        else:
            parts.append(f"RSI pullback {rsi:.1f} — entry window open")
    else:
        if extreme:
            parts.append(f"RSI extreme bounce {rsi:.1f} — strong entry window")
        else:
            parts.append(f"RSI bounce {rsi:.1f} — entry window open")
    if bb:
        parts.append("BB band touch confirmed")
    return " · ".join(parts) if parts else f"RSI {rsi:.1f}"


def _alignment_note(
    alignment:   str,
    daily_bias:  str,
    weekly_bias: str,
    direction:   str,
) -> str:
    if alignment == "strong":
        return f"Strong alignment — daily + weekly both {direction}"
    if alignment == "normal":
        return f"Normal alignment — one HTF confirms {direction}"
    if alignment == "opposing":
        return f"Opposing HTF — reduced size applied"
    return f"Weak alignment — daily {daily_bias} weekly {weekly_bias}"


def _live_risk_notes(coin: str, direction: str) -> list:
    notes = []

    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            raw = r.get(f"funding:{coin}USDT")
            if raw:
                funding_pct = float(raw) * 100
                if abs(funding_pct) > 0.05:
                    notes.append(f"Funding {funding_pct:.4f}% — squeeze risk elevated")
                elif abs(funding_pct) > 0.03:
                    notes.append(f"Funding {funding_pct:.4f}% — monitor")
    except Exception:
        pass

    try:
        from data.cache import cache
        btc = cache.get_raw("btc_4h_data")
        if btc:
            btc_cls = btc.get("trend", {}).get("cls", "neutral")
            btc_adx = float(btc.get("adx") or 0)
            if direction == "LONG" and btc_cls == "bear" and btc_adx > 25:
                notes.append(f"BTC bearish ADX {btc_adx:.0f} — headwind for long")
            elif direction == "SHORT" and btc_cls == "bull" and btc_adx > 25:
                notes.append(f"BTC bullish ADX {btc_adx:.0f} — headwind for short")
    except Exception:
        pass

    return notes


from config import cfg