import pandas as pd
from config import cfg
from datetime import datetime, timezone

TIERS = {
    "A+": {
        "min":         85,
        "cls":         "aplus",
        "action":      "FULL SIGNAL — Institutional Quality",
        "risk_pct":    0.10,
        "lev_mult":    1.0,
        "tps":         ["TP1", "TP2"],
        "desc":        "All confluence aligned. Full position.",
        "color":       "green",
        "signal_type": "FULL"
    },
    "A": {
        "min":         68,
        "cls":         "a",
        "action":      "FULL SIGNAL — High Confidence",
        "risk_pct":    0.10,
        "lev_mult":    1.0,
        "tps":         ["TP1", "TP2"],
        "desc":        "Strong confluence. Full position.",
        "color":       "blue",
        "signal_type": "FULL"
    },
    "B": {
        "min":         52,
        "cls":         "b",
        "action":      "SKIP — Below minimum grade",
        "risk_pct":    0.0,
        "lev_mult":    0.0,
        "tps":         [],
        "desc":        "Grade B skipped.",
        "color":       "orange",
        "signal_type": "SKIP"
    },
    "C": {
        "min":         38,
        "cls":         "c",
        "action":      "WATCH MODE — Set Alerts",
        "risk_pct":    0.0,
        "lev_mult":    0.0,
        "tps":         [],
        "desc":        "Setup building. No entry.",
        "color":       "yellow",
        "signal_type": "WATCH"
    },
    "F": {
        "min":         0,
        "cls":         "f",
        "action":      "STAY OUT — Hard Block",
        "risk_pct":    0.0,
        "lev_mult":    0.0,
        "tps":         [],
        "desc":        "Market untradeable.",
        "color":       "red",
        "signal_type": "HARD_BLOCK"
    }
}


def get_tier(score: float, hard_blocked: bool) -> dict:
    if hard_blocked:
        return {**TIERS["F"], "label": "F"}
    for label, t in TIERS.items():
        if score >= t["min"]:
            return {**t, "label": label}
    return {**TIERS["F"], "label": "F"}


def get_session() -> dict:
    # All session timing derives from UTC — audit requirement
    now  = datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60

    london = 8  <= hour < 16
    ny     = 13 <= hour < 21
    asia   = 0  <= hour < 8

    if london and ny:
        return {
            "name":    "London/NY Overlap",
            "quality": "BEST",
            "score":   9,
            "desc":    "Highest volume. Best signal quality."
        }
    if ny:
        return {
            "name":    "New York Session",
            "quality": "GOOD",
            "score":   7,
            "desc":    "High volume. Good for entries."
        }
    if london:
        return {
            "name":    "London Session",
            "quality": "GOOD",
            "score":   7,
            "desc":    "High volume. Trend initiation common."
        }
    if asia:
        return {
            "name":    "Asian Session",
            "quality": "CAUTION",
            "score":   2,
            "desc":    "Low volume. Liquidity grabs common."
        }
    return {
        "name":    "Off Hours",
        "quality": "CAUTION",
        "score":   2,
        "desc":    "Low volume. Wait for London open."
    }


# ═══════════════════════════════════════════════════════
# 15M ENTRY CONFIRMATION
# ═══════════════════════════════════════════════════════
def check_15m_entry(
    df_15m:    pd.DataFrame,
    direction: str,
    atr_4h:    float
) -> dict:

    if df_15m is None or len(df_15m) < 20:
        return {
            "confirmed":   False,
            "score":       5,
            "pattern":     "No 15m data",
            "entry_price": None,
            "desc":        "15m data unavailable — using 4H entry"
        }

    recent = df_15m.tail(10)
    last   = recent.iloc[-1]
    prev   = recent.iloc[-2]
    price  = float(last["close"])

    try:
        import ta
        ema20_series = ta.trend.ema_indicator(
            df_15m["close"], window=20
        )
        ema20 = float(ema20_series.iloc[-1])
    except Exception:
        ema20 = None

    vol_ma  = float(
        df_15m["volume"].rolling(10).mean().iloc[-1]
    ) or 1
    cur_vol = float(last["volume"])
    vol_ok  = cur_vol > vol_ma * 1.1

    last_open  = float(last["open"])
    last_close = float(last["close"])
    last_high  = float(last["high"])
    last_low   = float(last["low"])
    last_body  = abs(last_close - last_open)
    last_range = last_high - last_low

    prev_open  = float(prev["open"])
    prev_close = float(prev["close"])
    prev_high  = float(prev["high"])
    prev_low   = float(prev["low"])

    pattern       = "None"
    pattern_score = 0

    if direction == "LONG":
        if (
            prev_close < prev_open and
            last_close > last_open and
            last_close > prev_open and
            last_open  < prev_close and
            last_body  > last_range * 0.6
        ):
            pattern       = "Bullish Engulfing"
            pattern_score = 9
        elif (
            last_range > 0 and
            (min(last_open, last_close) - last_low) /
            last_range > 0.45 and
            last_close > (last_high + last_low) / 2
        ):
            pattern       = "Hammer / Pin Bar"
            pattern_score = 7
        elif (
            last_close > last_open and
            last_close > prev_high and
            last_body > last_range * 0.5
        ):
            pattern       = "Bullish Break"
            pattern_score = 6
        elif (
            last_high > prev_high and
            last_low  > prev_low and
            last_close > last_open
        ):
            pattern       = "Higher High/Low"
            pattern_score = 5

    else:
        if (
            prev_close > prev_open and
            last_close < last_open and
            last_close < prev_open and
            last_open  > prev_close and
            last_body  > last_range * 0.6
        ):
            pattern       = "Bearish Engulfing"
            pattern_score = 9
        elif (
            last_range > 0 and
            (last_high - max(last_open, last_close)) /
            last_range > 0.45 and
            last_close < (last_high + last_low) / 2
        ):
            pattern       = "Shooting Star"
            pattern_score = 7
        elif (
            last_close < last_open and
            last_close < prev_low and
            last_body > last_range * 0.5
        ):
            pattern       = "Bearish Break"
            pattern_score = 6
        elif (
            last_high < prev_high and
            last_low  < prev_low and
            last_close < last_open
        ):
            pattern       = "Lower High/Low"
            pattern_score = 5

    ema_ok = False
    if ema20:
        if direction == "LONG"  and price > ema20: ema_ok = True
        elif direction == "SHORT" and price < ema20: ema_ok = True

    last5       = recent.tail(5)
    closes      = [float(c["close"]) for _, c in last5.iterrows()]
    struct_bull = closes[-1] > closes[0]
    struct_bear = closes[-1] < closes[0]

    struct_ok = (
        (direction == "LONG"  and struct_bull) or
        (direction == "SHORT" and struct_bear)
    )

    score = pattern_score
    if vol_ok:    score += 1
    if ema_ok:    score += 1
    if struct_ok: score += 1
    score = min(score, 10)

    confirmed   = pattern_score >= 5 and (ema_ok or struct_ok)
    entry_price = price

    return {
        "confirmed":   confirmed,
        "score":       score,
        "pattern":     pattern,
        "entry_price": entry_price,
        "ema20":       ema20,
        "ema_ok":      ema_ok,
        "vol_ok":      vol_ok,
        "struct_ok":   struct_ok,
        "desc": (
            f"15m: {pattern} · "
            f"EMA:{'✅' if ema_ok else '❌'} · "
            f"Vol:{'✅' if vol_ok else '❌'} · "
            f"Struct:{'✅' if struct_ok else '❌'}"
        )
    }


# ═══════════════════════════════════════════════════════
# NO TRADE ENGINE
# Hard blocks: choppy, weekly conflict, ADX, extreme
# funding, news, failed retest, BTC unstable,
# minimum sweep/displacement condition.
# RSI is soft penalty only — never a hard block.
# ═══════════════════════════════════════════════════════
def run_no_trade_engine(
    regime, d1d, d4h,
    market, session,
    sweep, displacement,
    retest, btc_data,
    btc_instability,
    oi_matrix, news_filter,
    base_score: float
) -> dict:

    reasons       = []
    score_penalty = 0

    def hard(icon, reason, detail):
        reasons.append({
            "severity": "HARD",
            "icon":     icon,
            "reason":   reason,
            "detail":   detail
        })

    def soft(icon, reason, detail, penalty=4):
        nonlocal score_penalty
        reasons.append({
            "severity": "SOFT",
            "icon":     "⚠️",
            "reason":   reason,
            "detail":   detail,
            "penalty":  penalty
        })
        score_penalty += penalty

    d1_cls = d1d["trend"]["cls"]

    # ── HARD BLOCKS ──

    if regime["type"] == "chop":
        hard("🚫", "Market is CHOPPY", "ADX too weak on both TFs.")

    wk_bear = d1d.get("wk_trend_cls") == "bear"
    wk_bull = d1d.get("wk_trend_cls") == "bull"
    if (wk_bear and d1_cls == "bull") or (wk_bull and d1_cls == "bear"):
        hard("🚫", "Weekly gate BLOCKED", "Weekly and daily directly conflict.")

    adx = d1d.get("adx")
    if adx is not None and adx < 18:
        hard("🚫", f"ADX {adx:.1f} — no trend", "ADX below 18. Ranging market.")

    fund = market["funding"] * 100
    if abs(fund) > 0.08:
        hard("🚫", f"Extreme funding {fund:.4f}%", "Squeeze risk extremely high.")

    if news_filter and news_filter.get("blocked"):
        active_events = ", ".join(
            a["name"] for a in news_filter.get("alerts", [])
            if a.get("active")
        )
        hard("🚫", "High-impact macro event ACTIVE",
             active_events or "Check Finnhub calendar")

    if retest.get("failed"):
        hard("🚫", "Retest zone FAILED",
             "Zone invalidated — wait for new setup to form.")

    if (
        len(btc_instability.get("warnings", [])) >= 2 and
        d1d.get("coin") != "BTC"
    ):
        hard("🚫", "BTC unstable",
             " · ".join(btc_instability["warnings"][:2]))

    if cfg.REQUIRE_SWEEP_OR_DISPLACEMENT:
        sweep_ok = sweep.get("score", 0) >= 6
        disp_ok  = displacement.get("score", 0) >= 6
        if not sweep_ok and not disp_ok:
            hard("🚫", "Minimum condition not met",
                 "Neither sweep nor displacement confirmed.")

    # ── SOFT BLOCKS ──
    # RSI is soft penalty only — audit requirement.
    # Raw RSI values reduce confidence, never block trades.

    rsi = d1d.get("rsi")
    if rsi is not None:
        if rsi < 25 and d1_cls == "bear":
            soft("⚠️",
                 f"RSI {rsi:.1f} — deeply oversold",
                 "Bounce risk elevated. Confidence reduced.",
                 penalty=6)
        elif rsi < 30 and d1_cls == "bear":
            soft("⚠️",
                 f"RSI {rsi:.1f} — approaching oversold",
                 "Bounce risk present. Reduce confidence.",
                 penalty=3)
        if rsi > 75 and d1_cls == "bull":
            soft("⚠️",
                 f"RSI {rsi:.1f} — deeply overbought",
                 "Exhaustion risk elevated. Confidence reduced.",
                 penalty=6)
        elif rsi > 70 and d1_cls == "bull":
            soft("⚠️",
                 f"RSI {rsi:.1f} — approaching overbought",
                 "Exhaustion risk present. Reduce confidence.",
                 penalty=3)

    if news_filter and news_filter.get("warning"):
        upcoming = ", ".join(
            f"{a['name']} in {a['diff_min']}min"
            for a in news_filter.get("alerts", [])
            if a.get("warning")
        )
        soft("⚠️", "High-impact event approaching", upcoming, 3)

    if session["score"] <= 2:
        soft("⚠️", f"{session['name']} — low volume",
             "Wait for London/NY session.", 3)

    if not sweep.get("detected"):
        soft("⚠️", "No liquidity sweep",
             "Smart money has not hunted stops yet.", 4)

    if retest.get("status") == "none":
        soft("⚠️", "No retest zone active",
             "Wait for price to return to FVG or EMA.", 3)

    if oi_matrix.get("crowding_warning"):
        soft("⚠️", "Crowded positioning",
             oi_matrix["crowding_warning"], 3)

    struct_4h = d4h.get("structure", {}).get("struct_bias", "neutral")
    if (
        (d1_cls == "bull" and struct_4h == "bear") or
        (d1_cls == "bear" and struct_4h == "bull")
    ):
        soft("⚠️", "4H structure conflicts daily",
             "Wait for 4H structure to align.", 3)

    hard_blocks  = [r for r in reasons if r["severity"] == "HARD"]
    soft_blocks  = [r for r in reasons if r["severity"] == "SOFT"]
    adj_score    = max(0, base_score - score_penalty)
    hard_blocked = len(hard_blocks) > 0
    final_tier   = get_tier(adj_score, hard_blocked)

    return {
        "reasons":       reasons,
        "hard_blocks":   hard_blocks,
        "soft_blocks":   soft_blocks,
        "score_penalty": score_penalty,
        "adj_score":     adj_score,
        "blocked":       hard_blocked,
        "final_tier":    final_tier
    }


# ═══════════════════════════════════════════════════════
# GENERATE SIGNAL
# Attaches explanation bundle to every signal.
# ═══════════════════════════════════════════════════════
def generate_signal(
    d1d, d4h,
    wconf, no_trade,
    market, key_levels,
    capital:  float,
    leverage: int,
    df_15m:   pd.DataFrame = None,
    # Explanation inputs — passed from scanner
    sweep:        dict = None,
    displacement: dict = None,
    retest:       dict = None,
    btc_data:     dict = None,
    btc_inst:     dict = None,
    oi_matrix:    dict = None,
    regime:       dict = None,
    session:      dict = None
) -> dict:

    tier  = no_trade["final_tier"]
    score = no_trade["adj_score"]
    price = market["price"]

    if tier["signal_type"] == "HARD_BLOCK":
        base = {
            "direction":   "NO TRADE",
            "dir_class":   "notrade",
            "tier":        tier,
            "grade":       "F",
            "score":       score,
            "signal_type": "HARD_BLOCK",
            "reason": (
                no_trade["hard_blocks"][0]["reason"]
                if no_trade["hard_blocks"]
                else "Hard block active"
            )
        }
        base["explanation"] = _attach_explanation(
            base, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime,
            session, no_trade, wconf
        )
        return base

    if tier["signal_type"] == "SKIP":
        base = {
            "direction":   "SKIP",
            "dir_class":   "skip",
            "tier":        tier,
            "grade":       "B",
            "score":       score,
            "signal_type": "SKIP",
            "reason":      "Grade B — skipped"
        }
        base["explanation"] = _attach_explanation(
            base, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime,
            session, no_trade, wconf
        )
        return base

    if tier["signal_type"] == "WATCH":
        base = {
            "direction":   "WATCH",
            "dir_class":   "watch",
            "tier":        tier,
            "grade":       "C",
            "score":       score,
            "signal_type": "WATCH",
            "reason":      "Setup building — not ready"
        }
        base["explanation"] = _attach_explanation(
            base, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime,
            session, no_trade, wconf
        )
        return base

    d1_cls = d1d["trend"]["cls"]
    d4_cls = d4h["trend"]["cls"]

    if d1_cls == "bull" and d4_cls == "bull":
        direction = "LONG"
    elif d1_cls == "bear" and d4_cls == "bear":
        direction = "SHORT"
    else:
        base = {
            "direction":   "WATCH",
            "dir_class":   "watch",
            "tier":        get_tier(38, False),
            "grade":       "C",
            "score":       score,
            "signal_type": "WATCH",
            "reason":      "1D and 4H not aligned"
        }
        base["explanation"] = _attach_explanation(
            base, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime,
            session, no_trade, wconf
        )
        return base

    is_long = direction == "LONG"
    atr     = d1d.get("atr") or price * 0.015
    swings  = d1d.get("swings", {})

    entry_15m = check_15m_entry(
        df_15m    = df_15m,
        direction = direction,
        atr_4h    = d4h.get("atr", atr)
    )

    # 15m penalty — 5 points if not confirmed
    score_15m = score
    if not entry_15m["confirmed"]:
        score_15m = max(0, score - 5)
        tier = get_tier(
            score_15m,
            len(no_trade["hard_blocks"]) > 0
        )

    entry = (
        entry_15m["entry_price"]
        if entry_15m["confirmed"] and entry_15m["entry_price"]
        else price
    )

    # SL placement — minimum 1% distance
    if is_long:
        candidates = [
            entry - atr * 1.5,
            swings["last_low"]["price"] * 0.998
            if swings.get("last_low") else 0,
            key_levels.get("pdl", 0) * 0.998
        ]
        candidates = [c for c in candidates if 0 < c < entry]
        sl = max(candidates) if candidates else entry * 0.985
        if (entry - sl) / entry < 0.01:
            sl = entry * 0.99
    else:
        candidates = [
            entry + atr * 1.5,
            swings["last_high"]["price"] * 1.002
            if swings.get("last_high") else float("inf"),
            key_levels.get("pdh", float("inf")) * 1.002
        ]
        candidates = [c for c in candidates if c > entry]
        sl = min(candidates) if candidates else entry * 1.015
        if (sl - entry) / entry < 0.01:
            sl = entry * 1.01

    sl_dist = abs(entry - sl)
    sl_pct  = sl_dist / entry * 100

    tp1 = entry + sl_dist * 1.5 if is_long else entry - sl_dist * 1.5
    tp2 = entry + sl_dist * 2.5 if is_long else entry - sl_dist * 2.5

    risk_amt = capital * cfg.RISK_PCT_PER_TRADE
    pos_size = risk_amt / (sl_pct / 100)
    margin   = pos_size / leverage

    be_level  = entry + (sl_dist * 0.5 if is_long else -sl_dist * 0.5)
    trail_sl1 = tp1 - (sl_dist * 0.3 if is_long else -sl_dist * 0.3)

    result = {
        "direction":    direction,
        "dir_class":    "long" if is_long else "short",
        "tier":         tier,
        "grade":        tier["label"],
        "score":        score_15m,
        "signal_type":  tier["signal_type"],
        "entry":        entry,
        "sl":           sl,
        "tp1":          tp1,
        "tp2":          tp2,
        "sl_pct":       sl_pct,
        "sl_method":    "ATR 1.5x",
        "risk_pct":     cfg.RISK_PCT_PER_TRADE * 100,
        "risk_amt":     risk_amt,
        "pos_size":     pos_size,
        "margin":       margin,
        "eff_lev":      leverage,
        "atr_used":     atr,
        "active_tps":   tier["tps"],
        "be_level":     be_level,
        "trail_sl1":    trail_sl1,
        "funding":      market.get("funding", 0),
        "sweep_score":  0,
        "disp_score":   0,
        "entry_15m":    entry_15m,
        "reason": (
            f"15m: {entry_15m['pattern']}"
            if entry_15m["confirmed"]
            else "15m not confirmed — score reduced"
        )
    }

    result["explanation"] = _attach_explanation(
        result, sweep, displacement, retest,
        d1d, d4h, btc_data, btc_inst,
        oi_matrix, market, regime,
        session, no_trade, wconf
    )

    return result


# ═══════════════════════════════════════════════════════
# ATTACH EXPLANATION
# Internal helper — calls thesis.py build_explanation().
# Gracefully returns empty dict if inputs missing.
# ═══════════════════════════════════════════════════════
def _attach_explanation(
    signal, sweep, displacement, retest,
    d1d, d4h, btc_data, btc_inst,
    oi_matrix, market, regime,
    session, no_trade, wconf
) -> dict:

    # Guard — explanation inputs are optional
    # scanner passes them, backtest does not
    if not sweep or not no_trade or not wconf:
        return {}

    try:
        from engines.thesis import build_explanation
        return build_explanation(
            signal       = signal,
            sweep        = sweep,
            displacement = displacement or {},
            retest       = retest or {},
            d1d          = d1d,
            d4h          = d4h,
            btc_data     = btc_data,
            btc_inst     = btc_inst or {},
            oi_matrix    = oi_matrix or {},
            market       = market,
            regime       = regime or {},
            session      = session or {},
            no_trade     = no_trade,
            wconf        = wconf
        )
    except Exception:
        return {}