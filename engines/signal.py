import pandas as pd
from config import cfg
from datetime import datetime, timezone

TIERS = {
    "A+": {
        "min":         85,
        "cls":         "aplus",
        "action":      "FULL SIGNAL — Institutional Quality",
        "desc":        "All confluence aligned. Full position.",
        "signal_type": "FULL"
    },
    "A": {
        "min":         68,
        "cls":         "a",
        "action":      "FULL SIGNAL — High Confidence",
        "desc":        "Strong confluence. Full position.",
        "signal_type": "FULL"
    },
    "B": {
        "min":         52,
        "cls":         "b",
        "action":      "SKIP — Below minimum grade",
        "desc":        "Grade B skipped.",
        "signal_type": "SKIP"
    },
    "C": {
        "min":         38,
        "cls":         "c",
        "action":      "WATCH MODE — Set Alerts",
        "desc":        "Setup building. No entry.",
        "signal_type": "WATCH"
    },
    "F": {
        "min":         0,
        "cls":         "f",
        "action":      "STAY OUT — Hard Block",
        "desc":        "Market untradeable.",
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
    now  = datetime.now(timezone.utc)
    hour = now.hour + now.minute / 60

    london = 8  <= hour < 16
    ny     = 13 <= hour < 21
    asia   = 0  <= hour < 8

    if london and ny:
        return {
            "name":      "London/NY Overlap",
            "quality":   "BEST",
            "score":     9,
            "tradeable": True,
            "desc":      "Highest volume. Best signal quality."
        }
    if ny:
        return {
            "name":      "New York Session",
            "quality":   "GOOD",
            "score":     7,
            "tradeable": True,
            "desc":      "High volume. Good for entries."
        }
    if london:
        return {
            "name":      "London Session",
            "quality":   "GOOD",
            "score":     7,
            "tradeable": True,
            "desc":      "High volume. Trend initiation common."
        }
    if asia:
        return {
            "name":      "Asian Session",
            "quality":   "CAUTION",
            "score":     2,
            "tradeable": False,
            "desc":      "Low volume. Liquidity grabs frequently fake."
        }
    return {
        "name":      "Off Hours",
        "quality":   "CAUTION",
        "score":     2,
        "tradeable": False,
        "desc":      "Low volume. Wait for London open."
    }


def check_correlation(coin: str) -> dict:
    if coin == "BTC":
        return {"blocked": False, "reason": ""}
    try:
        from trade.state import state_manager
        if not state_manager.is_idle:
            active = state_manager.current_trade
            if active:
                if active.coin == "BTC":
                    return {
                        "blocked": True,
                        "reason":  "BTC trade active — altcoin entries blocked (correlation risk)"
                    }
                if active.coin == coin:
                    return {
                        "blocked": True,
                        "reason":  f"{coin} already in active trade"
                    }
    except Exception:
        pass
    return {"blocked": False, "reason": ""}


def dynamic_risk_pct(score: float) -> float:
    min_risk = 0.07
    max_risk = 0.13
    base     = 0.10

    if score >= 95:
        return max_risk
    if score >= 85:
        t = (score - 85) / 10
        return round(base + t * (max_risk - base), 3)
    if score >= 68:
        t = (score - 68) / 17
        return round(min_risk + t * (base - min_risk), 3)
    return min_risk


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
        ema20_series = ta.trend.ema_indicator(df_15m["close"], window=20)
        ema20        = float(ema20_series.iloc[-1])
    except Exception:
        ema20 = None

    vol_ma  = float(df_15m["volume"].rolling(10).mean().iloc[-1]) or 1
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
        if (prev_close < prev_open and last_close > last_open and
                last_close > prev_open and last_open < prev_close and
                last_body > last_range * 0.6):
            pattern, pattern_score = "Bullish Engulfing", 9
        elif (last_range > 0 and
                (min(last_open, last_close) - last_low) / last_range > 0.45 and
                last_close > (last_high + last_low) / 2):
            pattern, pattern_score = "Hammer / Pin Bar", 7
        elif (last_close > last_open and last_close > prev_high and
                last_body > last_range * 0.5):
            pattern, pattern_score = "Bullish Break", 6
        elif (last_high > prev_high and last_low > prev_low and
                last_close > last_open):
            pattern, pattern_score = "Higher High/Low", 5
    else:
        if (prev_close > prev_open and last_close < last_open and
                last_close < prev_open and last_open > prev_close and
                last_body > last_range * 0.6):
            pattern, pattern_score = "Bearish Engulfing", 9
        elif (last_range > 0 and
                (last_high - max(last_open, last_close)) / last_range > 0.45 and
                last_close < (last_high + last_low) / 2):
            pattern, pattern_score = "Shooting Star", 7
        elif (last_close < last_open and last_close < prev_low and
                last_body > last_range * 0.5):
            pattern, pattern_score = "Bearish Break", 6
        elif (last_high < prev_high and last_low < prev_low and
                last_close < last_open):
            pattern, pattern_score = "Lower High/Low", 5

    ema_ok = False
    if ema20:
        if direction == "LONG"  and price > ema20: ema_ok = True
        elif direction == "SHORT" and price < ema20: ema_ok = True

    last5       = recent.tail(5)
    closes      = [float(c["close"]) for _, c in last5.iterrows()]
    struct_bull = closes[-1] > closes[0]
    struct_bear = closes[-1] < closes[0]
    struct_ok   = (
        (direction == "LONG"  and struct_bull) or
        (direction == "SHORT" and struct_bear)
    )

    micro_sweep      = False
    micro_sweep_desc = ""

    try:
        swing_window = df_15m.tail(20)
        atr_15m      = float(
            swing_window["high"].values[-5:].max() -
            swing_window["low"].values[-5:].min()
        ) / 5

        if direction == "LONG":
            recent_low = float(swing_window["low"].iloc[:-1].min())
            if (last_low < recent_low and last_close > recent_low and
                    (recent_low - last_low) < atr_15m * 0.5):
                micro_sweep      = True
                micro_sweep_desc = f"Micro sweep below {recent_low:.4f}"
        else:
            recent_high = float(swing_window["high"].iloc[:-1].max())
            if (last_high > recent_high and last_close < recent_high and
                    (last_high - recent_high) < atr_15m * 0.5):
                micro_sweep      = True
                micro_sweep_desc = f"Micro sweep above {recent_high:.4f}"
    except Exception:
        pass

    micro_disp = False
    if len(recent) >= 3:
        prev2      = recent.iloc[-3]
        prev2_body = abs(float(prev2["close"]) - float(prev2["open"]))
        prev2_rng  = float(prev2["high"]) - float(prev2["low"])
        if prev2_rng > 0:
            if direction == "LONG" and float(prev2["close"]) > float(prev2["open"]):
                if prev2_body / prev2_rng > 0.6: micro_disp = True
            elif direction == "SHORT" and float(prev2["close"]) < float(prev2["open"]):
                if prev2_body / prev2_rng > 0.6: micro_disp = True

    score = pattern_score
    if vol_ok:      score += 1
    if ema_ok:      score += 1
    if struct_ok:   score += 1
    if micro_sweep: score += 2
    if micro_disp:  score += 1
    score = min(score, 10)

    confirmed = (
        pattern_score >= 5 and
        (ema_ok or struct_ok) and
        (not micro_sweep or micro_sweep)
    )

    if micro_sweep and micro_disp and vol_ok:
        confirmed = True
        if pattern == "None":
            pattern       = "Micro Sweep + Displacement"
            pattern_score = max(pattern_score, 7)

    desc_parts = [f"15m: {pattern}"]
    if micro_sweep: desc_parts.append(micro_sweep_desc)
    if micro_disp:  desc_parts.append("micro displacement")
    desc_parts.append(f"EMA:{'✅' if ema_ok else '❌'}")
    desc_parts.append(f"Vol:{'✅' if vol_ok else '❌'}")

    return {
        "confirmed":   confirmed,
        "score":       score,
        "pattern":     pattern,
        "entry_price": price,
        "ema20":       ema20,
        "ema_ok":      ema_ok,
        "vol_ok":      vol_ok,
        "struct_ok":   struct_ok,
        "micro_sweep": micro_sweep,
        "micro_disp":  micro_disp,
        "desc":        " · ".join(desc_parts)
    }


def _determine_direction(d1d: dict, d4h: dict) -> str:
    """
    Determines intended trade direction from trend alignment.
    Used when generating signal context even for blocked setups.
    """
    d1_cls = d1d["trend"]["cls"]
    d4_cls = d4h["trend"]["cls"]

    if d1_cls == "bull" and d4_cls == "bull":
        return "LONG"
    if d1_cls == "bear" and d4_cls == "bear":
        return "SHORT"
    if d1_cls == "bull":
        return "LONG"
    if d1_cls == "bear":
        return "SHORT"
    return "WATCH"


def run_no_trade_engine(
    regime, d1d, d4h,
    market, session,
    sweep, displacement,
    retest, btc_data,
    btc_instability,
    oi_matrix, news_filter,
    base_score: float,
    coin: str = "",
    d1w: dict = None,
    wconf: dict = None
) -> dict:

    market_blocks    = []
    entry_blocks     = []
    portfolio_blocks = []
    score_penalty    = 0

    d1_cls = d1d["trend"]["cls"]

    def hard_market(icon, reason, detail):
        market_blocks.append({
            "severity": "HARD",
            "layer":    "market",
            "icon":     icon,
            "reason":   reason,
            "detail":   detail
        })

    def hard_entry(icon, reason, detail, penalty=20):
        nonlocal score_penalty
        entry_blocks.append({
            "severity": "HARD",
            "layer":    "entry",
            "icon":     icon,
            "reason":   reason,
            "detail":   detail,
            "penalty":  penalty
        })
        score_penalty += penalty

    def hard_portfolio(icon, reason, detail):
        portfolio_blocks.append({
            "severity": "HARD",
            "layer":    "portfolio",
            "icon":     icon,
            "reason":   reason,
            "detail":   detail
        })

    def soft(icon, reason, detail, penalty=4):
        nonlocal score_penalty
        market_blocks.append({
            "severity": "SOFT",
            "icon":     "⚠️",
            "reason":   reason,
            "detail":   detail,
            "penalty":  penalty
        })
        score_penalty += penalty

    if regime["type"] == "chop":
        hard_market("🚫", "Market is CHOPPY", "ADX too weak on both TFs.")

    if d1w:
        wk_cls = d1w["trend"]["cls"]
        if (wk_cls == "bear" and d1_cls == "bull") or \
           (wk_cls == "bull" and d1_cls == "bear"):
            hard_market(
                "🚫", "Weekly gate BLOCKED",
                "Weekly and daily directly conflict."
            )

    adx = d1d.get("adx")
    if adx is not None and adx < 18:
        hard_market(
            "🚫", f"ADX {adx:.1f} — no trend",
            "ADX below 18. Ranging market."
        )

    fund = market["funding"] * 100
    if abs(fund) > 0.08:
        hard_market(
            "🚫", f"Extreme funding {fund:.4f}%",
            "Squeeze risk extremely high."
        )

    if news_filter and news_filter.get("blocked"):
        active_events = ", ".join(
            a["name"] for a in news_filter.get("alerts", [])
            if a.get("active")
        )
        hard_market(
            "🚫", "High-impact macro event ACTIVE",
            active_events or "Check Finnhub calendar"
        )

    if retest.get("failed"):
        hard_entry(
            "🚫", "Retest zone FAILED",
            "Zone invalidated — wait for new setup to form.",
            penalty=20
        )

    if (len(btc_instability.get("warnings", [])) >= 2 and
            coin != "BTC"):
        hard_entry(
            "🚫", "BTC unstable",
            " · ".join(btc_instability["warnings"][:2]),
            penalty=15
        )

    if cfg.REQUIRE_SWEEP_OR_DISPLACEMENT:
        sweep_ok = sweep.get("score", 0) >= 6
        disp_ok  = displacement.get("score", 0) >= 6
        if not sweep_ok and not disp_ok:
            hard_entry(
                "🚫", "Minimum condition not met",
                "Neither sweep nor displacement confirmed.",
                penalty=25
            )

    if not session.get("tradeable", True):
        hard_entry(
            "🚫", f"{session['name']} — entries blocked",
            session["desc"],
            penalty=20
        )

    if coin:
        corr = check_correlation(coin)
        if corr["blocked"]:
            hard_portfolio("🚫", "Correlation block", corr["reason"])

    rsi = d1d.get("rsi")
    if rsi is not None:
        if rsi < 25 and d1_cls == "bear":
            soft("⚠️", f"RSI {rsi:.1f} — deeply oversold",
                 "Bounce risk elevated. Confidence reduced.", penalty=6)
        elif rsi < 30 and d1_cls == "bear":
            soft("⚠️", f"RSI {rsi:.1f} — approaching oversold",
                 "Bounce risk present. Reduce confidence.", penalty=3)
        if rsi > 75 and d1_cls == "bull":
            soft("⚠️", f"RSI {rsi:.1f} — deeply overbought",
                 "Exhaustion risk elevated. Confidence reduced.", penalty=6)
        elif rsi > 70 and d1_cls == "bull":
            soft("⚠️", f"RSI {rsi:.1f} — approaching overbought",
                 "Exhaustion risk present. Reduce confidence.", penalty=3)

    if news_filter and news_filter.get("warning"):
        upcoming = ", ".join(
            f"{a['name']} in {a['diff_min']}min"
            for a in news_filter.get("alerts", [])
            if a.get("warning")
        )
        soft("⚠️", "High-impact event approaching", upcoming, 3)

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
    if ((d1_cls == "bull" and struct_4h == "bear") or
            (d1_cls == "bear" and struct_4h == "bull")):
        soft("⚠️", "4H structure conflicts daily",
             "Wait for 4H structure to align.", 3)

    market_hard_blocked = len(market_blocks) > 0 and any(
        b.get("severity") == "HARD" for b in market_blocks
    )
    entry_hard_blocked   = len(entry_blocks) > 0
    portfolio_blocked    = len(portfolio_blocks) > 0

    adj_score  = max(0, base_score - score_penalty)

    market_score = wconf.get("market_score", 0) if wconf else 0
    if market_score >= 70 and not market_hard_blocked:
        adj_score = max(adj_score, 38)

    final_tier = get_tier(adj_score, market_hard_blocked)

    if portfolio_blocked and not market_hard_blocked and not entry_hard_blocked:
        final_tier = {
            **final_tier,
            "signal_type":      "PORTFOLIO_BLOCK",
            "portfolio_reason": portfolio_blocks[0]["reason"]
        }

    all_reasons = market_blocks + entry_blocks + portfolio_blocks

    hard_blocks = [
        r for r in all_reasons
        if r.get("severity") == "HARD"
    ]
    soft_blocks = [
        r for r in market_blocks
        if r.get("severity") == "SOFT"
    ]

    return {
        "reasons":           all_reasons,
        "hard_blocks":       hard_blocks,
        "market_blocks":     [b for b in market_blocks if b.get("severity") == "HARD"],
        "entry_blocks":      entry_blocks,
        "portfolio_blocks":  portfolio_blocks,
        "soft_blocks":       soft_blocks,
        "score_penalty":     score_penalty,
        "adj_score":         adj_score,
        "blocked":           market_hard_blocked or entry_hard_blocked,
        "market_blocked":    market_hard_blocked,
        "entry_blocked":     entry_hard_blocked,
        "portfolio_blocked": portfolio_blocked,
        "final_tier":        final_tier
    }


def generate_signal(
    d1d, d4h,
    wconf, no_trade,
    market, key_levels,
    capital:      float,
    leverage:     int,
    df_15m:       pd.DataFrame = None,
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

    base = {
        "grade": tier["label"],
        "score": score,
        "tier":  tier,
    }

    non_trade_type = tier["signal_type"]

    if non_trade_type == "PORTFOLIO_BLOCK":
        direction = _determine_direction(d1d, d4h)
        result = {
            **base,
            "direction":        direction,
            "dir_class":        "long" if direction == "LONG" else "short" if direction == "SHORT" else "watch",
            "grade":            tier["label"],
            "signal_type":      "PORTFOLIO_BLOCK",
            "portfolio_reason": tier.get("portfolio_reason", "Portfolio blocked"),
            "reason":           tier.get("portfolio_reason", "Portfolio blocked"),
            "entry": price,
            "sl":    None,
            "tp1":   None,
            "tp2":   None,
        }
        result["explanation"] = _attach_explanation(
            result, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime, session,
            no_trade, wconf
        )
        return result

    if non_trade_type in ("HARD_BLOCK", "SKIP", "WATCH"):
        direction_map = {
            "HARD_BLOCK": ("NO TRADE", "notrade", "F"),
            "SKIP":       ("SKIP",     "skip",    "B"),
            "WATCH":      ("WATCH",    "watch",   "C"),
        }
        direction, dir_class, grade = direction_map[non_trade_type]

        if non_trade_type in ("WATCH", "SKIP"):
            intended = _determine_direction(d1d, d4h)
            if intended in ("LONG", "SHORT"):
                direction = intended
                dir_class = "long" if intended == "LONG" else "short"

        reason = (
            no_trade["market_blocks"][0]["reason"]
            if non_trade_type == "HARD_BLOCK" and no_trade.get("market_blocks")
            else no_trade["entry_blocks"][0]["reason"]
            if non_trade_type == "HARD_BLOCK" and no_trade.get("entry_blocks")
            else "Grade B — skipped" if non_trade_type == "SKIP"
            else "Setup building — not ready"
        )
        result = {
            **base,
            "direction":   direction,
            "dir_class":   dir_class,
            "grade":       grade,
            "signal_type": non_trade_type,
            "reason":      reason
        }
        result["explanation"] = _attach_explanation(
            result, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime, session,
            no_trade, wconf
        )
        return result

    d1_cls = d1d["trend"]["cls"]
    d4_cls = d4h["trend"]["cls"]

    if not (d1_cls == "bull" and d4_cls == "bull") and \
       not (d1_cls == "bear" and d4_cls == "bear"):
        result = {
            **base,
            "direction":   _determine_direction(d1d, d4h),
            "dir_class":   "watch",
            "tier":        get_tier(38, False),
            "grade":       "C",
            "signal_type": "WATCH",
            "reason":      "1D and 4H not aligned"
        }
        result["explanation"] = _attach_explanation(
            result, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime, session,
            no_trade, wconf
        )
        return result

    direction = "LONG" if d1_cls == "bull" else "SHORT"
    is_long   = direction == "LONG"
    atr       = d1d.get("atr") or price * 0.015
    swings    = d1d.get("swings", {})

    entry_15m = check_15m_entry(
        df_15m    = df_15m,
        direction = direction,
        atr_4h    = d4h.get("atr", atr)
    )

    score_15m = score
    if not entry_15m["confirmed"]:
        score_15m = max(0, score - 5)
        tier = get_tier(score_15m, no_trade.get("market_blocked", False))

    entry = (
        entry_15m["entry_price"]
        if entry_15m["confirmed"] and entry_15m["entry_price"]
        else price
    )

    if is_long:
        candidates = [
            entry - atr * 1.5,
            swings["last_low"]["price"] * 0.998 if swings.get("last_low") else 0,
            key_levels.get("pdl", 0) * 0.998
        ]
        candidates = [c for c in candidates if 0 < c < entry]
        sl = max(candidates) if candidates else entry * 0.985
        if (entry - sl) / entry < 0.01:
            sl = entry * 0.99
    else:
        candidates = [
            entry + atr * 1.5,
            swings["last_high"]["price"] * 1.002 if swings.get("last_high") else float("inf"),
            key_levels.get("pdh", float("inf")) * 1.002
        ]
        candidates = [c for c in candidates if c > entry]
        sl = min(candidates) if candidates else entry * 1.015
        if (sl - entry) / entry < 0.01:
            sl = entry * 1.01

    sl_dist  = abs(entry - sl)
    sl_pct   = sl_dist / entry * 100
    tp1      = entry + sl_dist * 1.5 if is_long else entry - sl_dist * 1.5
    tp2      = entry + sl_dist * 2.5 if is_long else entry - sl_dist * 2.5

    risk_pct = dynamic_risk_pct(score_15m)
    risk_amt = capital * risk_pct
    pos_size = risk_amt / (sl_pct / 100)
    margin   = pos_size / leverage

    result = {
        **base,
        "direction":   direction,
        "dir_class":   "long" if is_long else "short",
        "grade":       tier["label"],
        "score":       score_15m,
        "signal_type": tier["signal_type"],
        "entry":       entry,
        "sl":          sl,
        "tp1":         tp1,
        "tp2":         tp2,
        "sl_pct":      sl_pct,
        "sl_method":   "ATR 1.5x",
        "risk_pct":    risk_pct * 100,
        "risk_amt":    risk_amt,
        "pos_size":    pos_size,
        "margin":      margin,
        "eff_lev":     leverage,
        "atr_used":    atr,
        "funding":     market.get("funding", 0),
        "sweep_score": 0,
        "disp_score":  0,
        "entry_15m":   entry_15m,
        "reason": (
            f"15m: {entry_15m['pattern']}"
            if entry_15m["confirmed"]
            else "15m not confirmed — score reduced"
        )
    }

    result["explanation"] = _attach_explanation(
        result, sweep, displacement, retest,
        d1d, d4h, btc_data, btc_inst,
        oi_matrix, market, regime, session,
        no_trade, wconf
    )

    return result


def _attach_explanation(
    signal, sweep, displacement, retest,
    d1d, d4h, btc_data, btc_inst,
    oi_matrix, market, regime,
    session, no_trade, wconf
) -> dict:
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