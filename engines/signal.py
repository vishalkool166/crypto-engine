import logging
import math
import pandas as pd
from config import cfg
from datetime import datetime, timezone

log = logging.getLogger(__name__)

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
        "action":      "QUALIFIED SIGNAL — Moderate Confidence",
        "desc":        "Grade B — paper mode only with quality filter.",
        "signal_type": "FULL"
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

GRADE_MIN_RR = {
    "A+": 2.0,
    "A":  1.8,
    "B":  1.5,
}

GRADE_ATR_MULT = {
    "A+": 3.0,
    "A":  2.5,
    "B":  2.0,
}


def _safe_float(val, fallback: float = 0.0) -> float:
    try:
        result = float(val)
        return result if math.isfinite(result) else fallback
    except (TypeError, ValueError):
        return fallback


def _safe_div(a, b, fallback: float = 0.0) -> float:
    try:
        if b is None or b == 0 or math.isnan(float(b)):
            return fallback
        result = float(a) / float(b)
        return result if math.isfinite(result) else fallback
    except (TypeError, ValueError):
        return fallback


def get_tier(score, hard_blocked: bool) -> dict:
    try:
        score = float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        score = 0.0

    if hard_blocked:
        return {**TIERS["F"], "label": "F"}
    for label, t in TIERS.items():
        if score >= t["min"]:
            return {**t, "label": label}
    return {**TIERS["F"], "label": "F"}


def get_session(vol_ratio: float = 1.0, current_time=None) -> dict:
    now        = current_time if current_time else datetime.now(timezone.utc)
    hour       = now.hour + now.minute / 60
    weekday    = now.weekday()
    is_weekend = weekday >= 5

    london = 8  <= hour < 16
    ny     = 13 <= hour < 21
    asia   = 0  <= hour < 8

    def _downgrade(session: dict) -> dict:
        quality_map = {
            "BEST":    ("GOOD",    7),
            "GOOD":    ("CAUTION", 2),
            "CAUTION": ("CAUTION", 2)
        }
        q = session["quality"]
        if q in quality_map:
            new_q, new_score = quality_map[q]
            session = {**session, "quality": new_q, "score": new_score}
            if new_q == "CAUTION":
                session["tradeable"] = False
        return session

    if london and ny:
        s = {
            "name":      "London/NY Overlap",
            "quality":   "BEST",
            "score":     9,
            "tradeable": True,
            "desc":      "Highest volume. Best signal quality."
        }
    elif ny:
        s = {
            "name":      "New York Session",
            "quality":   "GOOD",
            "score":     7,
            "tradeable": True,
            "desc":      "High volume. Good for entries."
        }
    elif london:
        s = {
            "name":      "London Session",
            "quality":   "GOOD",
            "score":     7,
            "tradeable": True,
            "desc":      "High volume. Trend initiation common."
        }
    elif asia:
        s = {
            "name":      "Asian Session",
            "quality":   "CAUTION",
            "score":     2,
            "tradeable": False,
            "desc":      "Low volume. Liquidity grabs frequently fake."
        }
    else:
        s = {
            "name":      "Off Hours",
            "quality":   "CAUTION",
            "score":     2,
            "tradeable": False,
            "desc":      "Low volume. Wait for London open."
        }

    if is_weekend:
        s = _downgrade(s)
        s["desc"] = s["desc"] + " — weekend, reduced volume."

    if vol_ratio < 0.6:
        s = _downgrade(s)
        s["desc"] = s["desc"] + " — volume below 60% of average, quality downgraded."

    return s


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


def should_trade_b_grade(wconf: dict, no_trade: dict, session: dict) -> tuple[bool, str]:
    if not cfg.PAPER_TRADING:
        return False, "B grades not allowed in live mode"

    market_score = wconf.get("market_score", 0)
    if market_score < cfg.B_GRADE_MARKET_SCORE_MIN:
        return False, f"Market score {market_score} below minimum {cfg.B_GRADE_MARKET_SCORE_MIN}"

    session_name     = session.get("name", "")
    allowed_sessions = ["London/NY Overlap", "New York Session", "London Session"]
    if session_name not in allowed_sessions:
        return False, f"Session {session_name} not suitable for B grade"

    btc_score = wconf.get("btc_score", 0)
    if btc_score < cfg.B_GRADE_BTC_SCORE_MIN:
        return False, f"BTC score {btc_score} too low — BTC conflicting"

    entry_score = wconf.get("entry_score", 0)
    if entry_score < cfg.B_GRADE_ENTRY_SCORE_MIN:
        return False, f"Entry score {entry_score} below minimum {cfg.B_GRADE_ENTRY_SCORE_MIN}"

    hard_blocks  = no_trade.get("hard_blocks", [])
    entry_blocks = no_trade.get("entry_blocks", [])

    non_session_hard = [
        b for b in hard_blocks
        if "session" not in b.get("reason", "").lower()
    ]
    if len(non_session_hard) > 0:
        return False, f"Hard block: {non_session_hard[0].get('reason', 'unknown')}"

    if len(entry_blocks) > 1:
        return False, f"Too many entry blocks: {len(entry_blocks)}"

    return True, "B grade quality filter passed"


def get_min_rr(grade: str) -> float:
    return GRADE_MIN_RR.get(grade, 1.5)


def get_atr_mult(grade: str, adx: float) -> float:
    base = GRADE_ATR_MULT.get(grade, 2.0)
    if adx >= 40:
        return base * 1.2
    if adx >= 25:
        return base
    return base * 0.8


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
            "desc":        "15m data unavailable — using zone entry"
        }

    recent = df_15m.tail(10)
    last   = recent.iloc[-1]
    prev   = recent.iloc[-2]
    prev2  = recent.iloc[-3] if len(recent) >= 3 else None
    price  = _safe_float(last["close"])

    if price <= 0:
        return {
            "confirmed":   False,
            "score":       5,
            "pattern":     "Invalid price",
            "entry_price": None,
            "desc":        "Invalid 15m price data"
        }

    try:
        import ta
        ema20_series = ta.trend.ema_indicator(df_15m["close"], window=20)
        ema20_val    = _safe_float(ema20_series.iloc[-1])
        ema20        = ema20_val if ema20_val > 0 else None
    except Exception as e:
        log.warning(f"15m EMA calculation failed: {e}")
        ema20 = None

    try:
        vol_series = df_15m["volume"].rolling(10).mean()
        vol_ma_raw = _safe_float(vol_series.iloc[-1])
        vol_ma     = vol_ma_raw if vol_ma_raw > 0 else 1.0
    except Exception:
        vol_ma = 1.0

    cur_vol = _safe_float(last["volume"])
    vol_ok  = cur_vol > vol_ma * 1.1

    last_open  = _safe_float(last["open"])
    last_close = _safe_float(last["close"])
    last_high  = _safe_float(last["high"])
    last_low   = _safe_float(last["low"])
    last_body  = abs(last_close - last_open)
    last_range = last_high - last_low

    prev_open  = _safe_float(prev["open"])
    prev_close = _safe_float(prev["close"])
    prev_high  = _safe_float(prev["high"])
    prev_low   = _safe_float(prev["low"])

    pattern        = "None"
    pattern_score  = 0
    follow_through = True

    if direction == "LONG":
        if (last_range > 0 and
                prev_close < prev_open and last_close > last_open and
                last_close > prev_open and last_open < prev_close and
                last_body > last_range * 0.6):
            pattern, pattern_score = "Bullish Engulfing", 9
            if prev2 is not None:
                follow_through = _safe_float(prev2["close"]) >= last_open

        elif (last_range > 0 and
                (min(last_open, last_close) - last_low) / last_range > 0.45 and
                last_close > (last_high + last_low) / 2):
            pattern, pattern_score = "Hammer / Pin Bar", 7
            if prev2 is not None:
                follow_through = _safe_float(prev2["close"]) >= last_low

        elif (last_range > 0 and
                last_close > last_open and last_close > prev_high and
                last_body > last_range * 0.5):
            pattern, pattern_score = "Bullish Break", 6

        elif (last_high > prev_high and last_low > prev_low and
                last_close > last_open):
            pattern, pattern_score = "Higher High/Low", 5

    else:
        if (last_range > 0 and
                prev_close > prev_open and last_close < last_open and
                last_close < prev_open and last_open > prev_close and
                last_body > last_range * 0.6):
            pattern, pattern_score = "Bearish Engulfing", 9
            if prev2 is not None:
                follow_through = _safe_float(prev2["close"]) <= last_open

        elif (last_range > 0 and
                (last_high - max(last_open, last_close)) / last_range > 0.45 and
                last_close < (last_high + last_low) / 2):
            pattern, pattern_score = "Shooting Star", 7
            if prev2 is not None:
                follow_through = _safe_float(prev2["close"]) <= last_high

        elif (last_range > 0 and
                last_close < last_open and last_close < prev_low and
                last_body > last_range * 0.5):
            pattern, pattern_score = "Bearish Break", 6

        elif (last_high < prev_high and last_low < prev_low and
                last_close < last_open):
            pattern, pattern_score = "Lower High/Low", 5

    if not follow_through and pattern_score >= 7:
        pattern_score = max(0, pattern_score - 3)

    ema_ok = False
    if ema20 and ema20 > 0:
        if direction == "LONG"  and price > ema20: ema_ok = True
        if direction == "SHORT" and price < ema20: ema_ok = True

    last5       = recent.tail(5)
    closes      = [_safe_float(c["close"]) for _, c in last5.iterrows()]
    struct_bull = closes[-1] > closes[0] if closes else False
    struct_bear = closes[-1] < closes[0] if closes else False
    struct_ok   = (
        (direction == "LONG"  and struct_bull) or
        (direction == "SHORT" and struct_bear)
    )

    micro_sweep      = False
    micro_sweep_desc = ""

    try:
        swing_window = df_15m.tail(20)
        highs        = swing_window["high"].values[-5:]
        lows         = swing_window["low"].values[-5:]
        atr_15m      = _safe_float(highs.max() - lows.min()) / 5
        if atr_15m <= 0:
            atr_15m = price * 0.001

        if direction == "LONG":
            recent_low = _safe_float(swing_window["low"].iloc[:-1].min())
            if (last_low < recent_low and last_close > recent_low and
                    (recent_low - last_low) < atr_15m * 0.5):
                micro_sweep      = True
                micro_sweep_desc = f"Micro sweep below {recent_low:.4f}"
        else:
            recent_high = _safe_float(swing_window["high"].iloc[:-1].max())
            if (last_high > recent_high and last_close < recent_high and
                    (last_high - recent_high) < atr_15m * 0.5):
                micro_sweep      = True
                micro_sweep_desc = f"Micro sweep above {recent_high:.4f}"
    except Exception as e:
        log.debug(f"Micro sweep detection failed: {e}")

    micro_disp = False
    if len(recent) >= 3:
        try:
            p2      = recent.iloc[-3]
            p2_body = abs(_safe_float(p2["close"]) - _safe_float(p2["open"]))
            p2_rng  = _safe_float(p2["high"]) - _safe_float(p2["low"])
            if p2_rng > 0:
                if direction == "LONG" and _safe_float(p2["close"]) > _safe_float(p2["open"]):
                    if p2_body / p2_rng > 0.6: micro_disp = True
                elif direction == "SHORT" and _safe_float(p2["close"]) < _safe_float(p2["open"]):
                    if p2_body / p2_rng > 0.6: micro_disp = True
        except Exception as e:
            log.debug(f"Micro displacement detection failed: {e}")

    score = pattern_score
    if vol_ok:      score += 1
    if ema_ok:      score += 1
    if struct_ok:   score += 1
    if micro_sweep: score += 2
    if micro_disp:  score += 1
    score = min(score, 10)

    confirmed = (
        pattern_score >= 5 and
        follow_through and
        (ema_ok or struct_ok)
    )

    if micro_sweep and micro_disp and vol_ok:
        confirmed = True
        if pattern == "None":
            pattern       = "Micro Sweep + Displacement"
            pattern_score = max(pattern_score, 7)

    desc_parts = [f"15m: {pattern}"]
    if not follow_through: desc_parts.append("no follow-through")
    if micro_sweep:        desc_parts.append(micro_sweep_desc)
    if micro_disp:         desc_parts.append("micro displacement")
    desc_parts.append(f"EMA:{'✅' if ema_ok else '❌'}")
    desc_parts.append(f"Vol:{'✅' if vol_ok else '❌'}")

    return {
        "confirmed":      confirmed,
        "score":          score,
        "pattern":        pattern,
        "entry_price":    price,
        "ema20":          ema20,
        "ema_ok":         ema_ok,
        "vol_ok":         vol_ok,
        "struct_ok":      struct_ok,
        "micro_sweep":    micro_sweep,
        "micro_disp":     micro_disp,
        "follow_through": follow_through,
        "desc":           " · ".join(desc_parts)
    }


def _determine_direction(d1d: dict, d4h: dict) -> str:
    d1_cls = d1d.get("trend", {}).get("cls", "neutral")
    d4_cls = d4h.get("trend", {}).get("cls", "neutral")

    if d1_cls == "bull" and d4_cls == "bull": return "LONG"
    if d1_cls == "bear" and d4_cls == "bear": return "SHORT"
    if d1_cls == "bull": return "LONG"
    if d1_cls == "bear": return "SHORT"
    return "WATCH"


def _coin_volatility_profile(
    d4h:   dict,
    d1d:   dict,
    price: float
) -> dict:
    atr_4h  = _safe_float(d4h.get("atr") or d1d.get("atr") or price * 0.015)
    atr_pct = _safe_div(atr_4h, price) * 100
    adx     = _safe_float(d4h.get("adx") or d1d.get("adx") or 20)
    bb      = d4h.get("bb") or d1d.get("bb") or {}
    bb_w    = _safe_float(bb.get("width", 5))

    swings     = d1d.get("swings", {})
    highs      = swings.get("highs", [])
    lows       = swings.get("lows",  [])
    swing_ranges = []

    for i in range(min(len(highs), len(lows), 5)):
        h = _safe_float(highs[i]["price"]) if i < len(highs) else 0
        l = _safe_float(lows[i]["price"])  if i < len(lows)  else 0
        if h > 0 and l > 0 and h > l:
            swing_ranges.append(h - l)

    avg_swing     = sum(swing_ranges) / len(swing_ranges) if swing_ranges else atr_4h * 4
    avg_swing_pct = _safe_div(avg_swing, price) * 100

    if atr_pct > 4.0 or bb_w > 10:
        volatility_class = "high"
    elif atr_pct < 1.0 or bb_w < 4:
        volatility_class = "low"
    else:
        volatility_class = "normal"

    return {
        "atr_4h":           atr_4h,
        "atr_pct":          atr_pct,
        "adx":              adx,
        "bb_width":         bb_w,
        "avg_swing":        avg_swing,
        "avg_swing_pct":    avg_swing_pct,
        "volatility_class": volatility_class
    }


def _calculate_sl(
    is_long:     bool,
    entry:       float,
    sweep:       dict,
    retest:      dict,
    d4h:         dict,
    d1d:         dict,
    swings:      dict,
    key_levels:  dict,
    grade:       str,
    vol_profile: dict
) -> tuple[float, str, bool]:

    atr_4h = vol_profile["atr_4h"]
    adx    = vol_profile["adx"]
    if atr_4h <= 0:
        atr_4h = entry * 0.015

    atr_1d = float(d1d.get("atr") or atr_4h)
    if atr_1d <= 0:
        atr_1d = atr_4h

    atr_mult    = get_atr_mult(grade, adx)
    max_sl_dist = atr_4h * atr_mult

    def _buf(level_type: str) -> float:
        if level_type in ("sweep", "swing", "pdl", "pdh", "pwl", "pwh"):
            return atr_1d * 0.3
        return atr_4h * 0.3

    sl        = None
    sl_method = ""

    if is_long:
        sweep_low = _safe_float(sweep.get("sweep_low") or 0)
        if sweep_low > 0 and sweep_low < entry:
            candidate = sweep_low - _buf("sweep")
            if abs(entry - candidate) <= max_sl_dist:
                sl        = candidate
                sl_method = "Below sweep low"

        if sl is None:
            ob_data    = d4h.get("order_blocks", {})
            nearest_ob = ob_data.get("nearest_bull")
            if nearest_ob and not nearest_ob.get("mitigated"):
                ob_bottom = _safe_float(nearest_ob.get("bottom", 0))
                if ob_bottom > 0 and ob_bottom < entry:
                    candidate = ob_bottom - _buf("ob")
                    if abs(entry - candidate) <= max_sl_dist:
                        sl        = candidate
                        sl_method = "Below OB bottom"

        if sl is None:
            retest_zone = retest.get("zone")
            if retest_zone:
                rb = _safe_float(retest_zone.get("bottom", 0))
                if rb > 0 and rb < entry:
                    candidate = rb - _buf("retest")
                    if abs(entry - candidate) <= max_sl_dist:
                        sl        = candidate
                        sl_method = "Below retest zone"

        if sl is None:
            if swings.get("last_low"):
                swing_low = _safe_float(swings["last_low"]["price"])
                if swing_low > 0 and swing_low < entry:
                    candidate = swing_low - _buf("swing")
                    if abs(entry - candidate) <= max_sl_dist:
                        sl        = candidate
                        sl_method = "Below swing low"

        if sl is None:
            pdl = _safe_float(key_levels.get("pdl", 0))
            if pdl > 0 and pdl < entry:
                candidate = pdl - _buf("pdl")
                if abs(entry - candidate) <= max_sl_dist:
                    sl        = candidate
                    sl_method = "Below PDL"

    else:
        sweep_high = _safe_float(sweep.get("sweep_high") or 0)
        if sweep_high > 0 and sweep_high > entry:
            candidate = sweep_high + _buf("sweep")
            if abs(candidate - entry) <= max_sl_dist:
                sl        = candidate
                sl_method = "Above sweep high"

        if sl is None:
            ob_data    = d4h.get("order_blocks", {})
            nearest_ob = ob_data.get("nearest_bear")
            if nearest_ob and not nearest_ob.get("mitigated"):
                ob_top = _safe_float(nearest_ob.get("top", 0))
                if ob_top > 0 and ob_top > entry:
                    candidate = ob_top + _buf("ob")
                    if abs(candidate - entry) <= max_sl_dist:
                        sl        = candidate
                        sl_method = "Above OB top"

        if sl is None:
            retest_zone = retest.get("zone")
            if retest_zone:
                rt = _safe_float(retest_zone.get("top", 0))
                if rt > 0 and rt > entry:
                    candidate = rt + _buf("retest")
                    if abs(candidate - entry) <= max_sl_dist:
                        sl        = candidate
                        sl_method = "Above retest zone"

        if sl is None:
            if swings.get("last_high"):
                swing_high = _safe_float(swings["last_high"]["price"])
                if swing_high > 0 and swing_high > entry:
                    candidate = swing_high + _buf("swing")
                    if abs(candidate - entry) <= max_sl_dist:
                        sl        = candidate
                        sl_method = "Above swing high"

        if sl is None:
            pdh = _safe_float(key_levels.get("pdh", 0))
            if pdh > 0 and pdh > entry:
                candidate = pdh + _buf("pdh")
                if abs(candidate - entry) <= max_sl_dist:
                    sl        = candidate
                    sl_method = "Above PDH"

    if sl is None:
        log.warning(
            f"No structural SL found within ATR limit "
            f"(max_sl_dist={max_sl_dist:.4f} atr={atr_4h:.4f} mult={atr_mult}) "
            f"— entry stale or structure too far"
        )
        return 0.0, "SL_REJECTED — no structural level within ATR range (entry stale)", True

    if is_long and sl >= entry:
        return 0.0, "SL_REJECTED — SL above entry for LONG", True
    if not is_long and sl <= entry:
        return 0.0, "SL_REJECTED — SL below entry for SHORT", True

    min_sl_dist = atr_4h * 0.3
    sl_dist     = abs(entry - sl)

    if sl_dist < min_sl_dist:
        sl        = entry - min_sl_dist if is_long else entry + min_sl_dist
        sl_method += " (floored — too tight)"

    return sl, sl_method, False


def _calculate_tp(
    is_long:     bool,
    entry:       float,
    sl:          float,
    grade:       str,
    swings:      dict,
    key_levels:  dict,
    d1d:         dict,
    d1h:         dict,
    sweep:       dict,
    vol_profile: dict
) -> tuple[float, float, str]:

    sl_dist   = abs(entry - sl)
    if sl_dist <= 0:
        sl_dist = entry * 0.01

    min_rr    = get_min_rr(grade)
    bb_width  = vol_profile["bb_width"]
    avg_swing = vol_profile["avg_swing"]

    tp_extension = (
        1.3 if bb_width > 8 else
        1.0 if bb_width > 4 else
        0.8
    )

    if is_long:
        candidates = []

        highs = swings.get("highs", [])
        if len(highs) >= 2:
            last_high = _safe_float(highs[-1]["price"])
            prev_high = _safe_float(highs[-2]["price"])
            if prev_high > 0 and abs(last_high - prev_high) / prev_high < 0.003:
                equal_high = max(last_high, prev_high)
                if equal_high > entry:
                    candidates.append((equal_high, "Equal highs liquidity"))

        if swings.get("last_high"):
            sh = _safe_float(swings["last_high"]["price"])
            if sh > entry:
                candidates.append((sh, "Swing high"))

        if d1h:
            d1h_swings = d1h.get("swings", {})
            if d1h_swings.get("last_high"):
                h1h = _safe_float(d1h_swings["last_high"]["price"])
                if h1h > entry:
                    candidates.append((h1h, "1H Swing high"))

        pdh = _safe_float(key_levels.get("pdh", 0))
        if pdh > entry:
            candidates.append((pdh, "PDH"))

        pwh = _safe_float(key_levels.get("pwh", 0))
        if pwh > entry:
            candidates.append((pwh, "PWH"))

        vah = _safe_float(d1d.get("vah") or 0)
        if vah > entry:
            candidates.append((vah, "VAH"))

        poc = _safe_float(d1d.get("poc") or 0)
        if poc > entry:
            candidates.append((poc, "POC"))

        sweep_items = sweep.get("items", [])
        for item in sweep_items:
            lvl = _safe_float(item.get("level", 0))
            if item.get("type") == "bear" and lvl > entry:
                candidates.append((lvl, "Sweep level above"))

        swing_target = entry + (avg_swing * 0.618 * tp_extension)
        candidates.append((swing_target, "Swing range projection"))

        valid_candidates = [
            (lvl, lbl) for lvl, lbl in candidates
            if _safe_div(abs(lvl - entry), sl_dist) >= min_rr
        ]

        if valid_candidates:
            valid_candidates.sort(key=lambda x: x[0])
            tp, tp_label = valid_candidates[0]
            actual_rr    = _safe_div(abs(tp - entry), sl_dist)
        else:
            tp        = entry + sl_dist * min_rr
            tp_label  = f"{min_rr}x R:R floor — no structural level found"
            actual_rr = min_rr

    else:
        candidates = []

        lows = swings.get("lows", [])
        if len(lows) >= 2:
            last_low = _safe_float(lows[-1]["price"])
            prev_low = _safe_float(lows[-2]["price"])
            if prev_low > 0 and abs(last_low - prev_low) / prev_low < 0.003:
                equal_low = min(last_low, prev_low)
                if equal_low < entry:
                    candidates.append((equal_low, "Equal lows liquidity"))

        if swings.get("last_low"):
            sl_swing = _safe_float(swings["last_low"]["price"])
            if sl_swing < entry:
                candidates.append((sl_swing, "Swing low"))

        if d1h:
            d1h_swings = d1h.get("swings", {})
            if d1h_swings.get("last_low"):
                l1h = _safe_float(d1h_swings["last_low"]["price"])
                if l1h < entry:
                    candidates.append((l1h, "1H Swing low"))

        pdl = _safe_float(key_levels.get("pdl", 0))
        if pdl > 0 and pdl < entry:
            candidates.append((pdl, "PDL"))

        pwl = _safe_float(key_levels.get("pwl", 0))
        if pwl > 0 and pwl < entry:
            candidates.append((pwl, "PWL"))

        val = _safe_float(d1d.get("val") or 0)
        if val > 0 and val < entry:
            candidates.append((val, "VAL"))

        poc = _safe_float(d1d.get("poc") or 0)
        if poc > 0 and poc < entry:
            candidates.append((poc, "POC"))

        sweep_items = sweep.get("items", [])
        for item in sweep_items:
            lvl = _safe_float(item.get("level", 0))
            if item.get("type") == "bull" and lvl > 0 and lvl < entry:
                candidates.append((lvl, "Sweep level below"))

        swing_target = entry - (avg_swing * 0.618 * tp_extension)
        if swing_target > 0:
            candidates.append((swing_target, "Swing range projection"))

        valid_candidates = [
            (lvl, lbl) for lvl, lbl in candidates
            if _safe_div(abs(entry - lvl), sl_dist) >= min_rr
        ]

        if valid_candidates:
            valid_candidates.sort(key=lambda x: x[0], reverse=True)
            tp, tp_label = valid_candidates[0]
            actual_rr    = _safe_div(abs(entry - tp), sl_dist)
        else:
            tp        = entry - sl_dist * min_rr
            tp_label  = f"{min_rr}x R:R floor — no structural level found"
            actual_rr = min_rr

    return tp, round(actual_rr, 2), tp_label


def run_no_trade_engine(
    regime, d1d, d4h,
    market, session,
    sweep, displacement,
    retest, btc_data,
    btc_instability,
    oi_matrix, news_filter,
    base_score: float,
    coin:       str  = "",
    d1w:        dict = None,
    wconf:      dict = None,
    staleness:  dict = None
) -> dict:

    market_blocks    = []
    entry_blocks     = []
    portfolio_blocks = []
    score_penalty    = 0

    d1_cls = d1d.get("trend", {}).get("cls", "neutral")

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

    if staleness and staleness.get("expired"):
        soft(
            "⚠️", "Setup aging — both sweep and displacement old",
            " · ".join(staleness.get("reasons", ["Setup aging"])),
            penalty=12
        )

    if regime.get("type") == "chop":
        hard_market("🚫", "Market is CHOPPY", "ADX too weak on both TFs.")

    if d1w:
        wk_cls = d1w.get("trend", {}).get("cls", "neutral")
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

    fund = _safe_float(market.get("funding", 0)) * 100
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

    if (len(btc_instability.get("warnings", [])) >= 2 and coin != "BTC"):
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

    if wconf and not wconf.get("non_neg_passed", True):
        failed = wconf.get("non_neg_failed", [])
        if failed:
            soft(
                "⚠️", f"Key factors weak: {', '.join(failed)}",
                "Non-negotiable factors below threshold — score reduced",
                penalty=10
            )

    if coin:
        corr = check_correlation(coin)
        if corr["blocked"]:
            hard_portfolio("🚫", "Correlation block", corr["reason"])

    rsi = d1d.get("rsi")
    if rsi is not None:
        if rsi < 25 and d1_cls == "bear":
            soft("⚠️", f"RSI {rsi:.1f} — deeply oversold",
                 "Bounce risk elevated.", penalty=6)
        elif rsi < 30 and d1_cls == "bear":
            soft("⚠️", f"RSI {rsi:.1f} — approaching oversold",
                 "Bounce risk present.", penalty=3)
        if rsi > 75 and d1_cls == "bull":
            soft("⚠️", f"RSI {rsi:.1f} — deeply overbought",
                 "Exhaustion risk elevated.", penalty=6)
        elif rsi > 70 and d1_cls == "bull":
            soft("⚠️", f"RSI {rsi:.1f} — approaching overbought",
                 "Exhaustion risk present.", penalty=3)

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

    if staleness and staleness.get("degraded"):
        soft("⚠️", "Setup degraded",
             " · ".join(staleness.get("reasons", ["Setup aging"])), 3)

    market_hard_blocked = len(market_blocks) > 0 and any(
        b.get("severity") == "HARD" for b in market_blocks
    )
    entry_hard_blocked  = len(entry_blocks) > 0
    portfolio_blocked   = len(portfolio_blocks) > 0

    adj_score    = max(0, base_score - score_penalty)
    market_score = wconf.get("market_score", 0) if wconf else 0

    if market_score >= 70 and not market_hard_blocked:
        adj_score = max(adj_score, 38)

    if staleness and staleness.get("score_mult", 1.0) < 1.0:
        adj_score = round(adj_score * staleness["score_mult"])

    final_tier = get_tier(adj_score, market_hard_blocked)

    if portfolio_blocked and not market_hard_blocked and not entry_hard_blocked:
        final_tier = {
            **final_tier,
            "signal_type":      "PORTFOLIO_BLOCK",
            "portfolio_reason": portfolio_blocks[0]["reason"]
        }

    all_reasons = market_blocks + entry_blocks + portfolio_blocks
    hard_blocks = [r for r in all_reasons if r.get("severity") == "HARD"]
    soft_blocks = [r for r in market_blocks if r.get("severity") == "SOFT"]

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
    capital:      float = None,
    leverage:     int   = None,
    df_15m:       pd.DataFrame = None,
    sweep:        dict = None,
    displacement: dict = None,
    retest:       dict = None,
    btc_data:     dict = None,
    btc_inst:     dict = None,
    oi_matrix:    dict = None,
    regime:       dict = None,
    session:      dict = None,
    d1w:          dict = None,
    d1h:          dict = None,
    staleness:    dict = None
) -> dict:

    price = _safe_float(market.get("price", 0))

    if price <= 0:
        log.error("Invalid price in generate_signal")
        return {
            "grade":       "F",
            "score":       0,
            "direction":   "NO TRADE",
            "dir_class":   "notrade",
            "signal_type": "HARD_BLOCK",
            "reason":      "Invalid price",
            "entry":       None,
            "sl":          None,
            "tp1":         None,
            "tp2":         None,
        }

    tier  = no_trade["final_tier"]
    score = no_trade["adj_score"]

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
            "entry":            price,
            "sl":               None,
            "tp1":              None,
            "tp2":              None,
        }
        result["explanation"] = _attach_explanation(
            result, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime, session,
            no_trade, wconf
        )
        return result

    if non_trade_type in ("HARD_BLOCK", "WATCH"):
        direction_map = {
            "HARD_BLOCK": ("NO TRADE", "notrade", "F"),
            "WATCH":      ("WATCH",    "watch",   "C"),
        }
        direction, dir_class, grade = direction_map[non_trade_type]

        if non_trade_type == "WATCH":
            intended = _determine_direction(d1d, d4h)
            if intended in ("LONG", "SHORT"):
                direction = intended
                dir_class = "long" if intended == "LONG" else "short"

        reason = (
            no_trade["market_blocks"][0]["reason"]
            if non_trade_type == "HARD_BLOCK" and no_trade.get("market_blocks")
            else no_trade["entry_blocks"][0]["reason"]
            if non_trade_type == "HARD_BLOCK" and no_trade.get("entry_blocks")
            else "Setup building — not ready"
        )
        result = {
            **base,
            "direction":   direction,
            "dir_class":   dir_class,
            "grade":       grade,
            "signal_type": non_trade_type,
            "reason":      reason,
            "entry":       None,
            "sl":          None,
            "tp1":         None,
            "tp2":         None,
        }
        result["explanation"] = _attach_explanation(
            result, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime, session,
            no_trade, wconf
        )
        return result

    grade_label = tier["label"]

    if non_trade_type == "FULL" and grade_label == "B":
        b_ok, b_reason = should_trade_b_grade(wconf, no_trade, session or {})
        if not b_ok:
            intended = _determine_direction(d1d, d4h)
            result = {
                **base,
                "direction":   intended if intended in ("LONG", "SHORT") else "WATCH",
                "dir_class":   "long" if intended == "LONG" else "short" if intended == "SHORT" else "watch",
                "grade":       "B",
                "signal_type": "SKIP",
                "reason":      f"Grade B filtered: {b_reason}",
                "entry":       None,
                "sl":          None,
                "tp1":         None,
                "tp2":         None,
            }
            result["explanation"] = _attach_explanation(
                result, sweep, displacement, retest,
                d1d, d4h, btc_data, btc_inst,
                oi_matrix, market, regime, session,
                no_trade, wconf
            )
            return result

    d1_cls = d1d.get("trend", {}).get("cls", "neutral")
    d4_cls = d4h.get("trend", {}).get("cls", "neutral")

    if not (d1_cls == "bull" and d4_cls == "bull") and \
       not (d1_cls == "bear" and d4_cls == "bear"):
        result = {
            **base,
            "direction":   _determine_direction(d1d, d4h),
            "dir_class":   "watch",
            "tier":        get_tier(38, False),
            "grade":       "C",
            "signal_type": "WATCH",
            "reason":      "1D and 4H not aligned",
            "entry":       None,
            "sl":          None,
            "tp1":         None,
            "tp2":         None,
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
    swings    = d1d.get("swings", {})

    vol_profile = _coin_volatility_profile(d4h, d1d, price)

    limit_entry  = retest.get("limit_entry") if retest else None
    limit_method = retest.get("limit_method", "") if retest else ""

    entry_15m = check_15m_entry(
        df_15m    = df_15m,
        direction = direction,
        atr_4h    = vol_profile["atr_4h"]
    )

    if limit_entry and limit_entry > 0:
        entry        = _safe_float(limit_entry)
        entry_source = f"Limit order at zone — {limit_method}"
    elif entry_15m["confirmed"] and entry_15m["entry_price"]:
        entry        = _safe_float(entry_15m["entry_price"])
        entry_source = f"15m confirmed — {entry_15m['pattern']}"
    else:
        entry        = price
        entry_source = "Market price — no zone or 15m entry"

    if entry <= 0:
        entry        = price
        entry_source = "Market price fallback"

    score_15m = score
    if not entry_15m["confirmed"] and not limit_entry:
        score_15m   = max(0, score - 2)
        tier        = get_tier(score_15m, no_trade.get("market_blocked", False))
        grade_label = tier["label"]

    sl, sl_method, sl_rejected = _calculate_sl(
        is_long     = is_long,
        entry       = entry,
        sweep       = sweep or {},
        retest      = retest or {},
        d4h         = d4h,
        d1d         = d1d,
        swings      = swings,
        key_levels  = key_levels,
        grade       = grade_label,
        vol_profile = vol_profile
    )

    if sl_rejected:
        intended = _determine_direction(d1d, d4h)
        log.warning(f"Signal rejected — SL: {sl_method}")
        result = {
            **base,
            "direction":   intended if intended in ("LONG", "SHORT") else "WATCH",
            "dir_class":   "long" if intended == "LONG" else "short" if intended == "SHORT" else "watch",
            "grade":       grade_label,
            "signal_type": "SKIP",
            "reason":      sl_method,
            "sl_rejected": True,
            "entry":       None,
            "sl":          None,
            "tp1":         None,
            "tp2":         None,
        }
        result["explanation"] = _attach_explanation(
            result, sweep, displacement, retest,
            d1d, d4h, btc_data, btc_inst,
            oi_matrix, market, regime, session,
            no_trade, wconf
        )
        return result

    sl_dist = abs(entry - sl)
    sl_pct  = _safe_div(sl_dist, entry, fallback=0.5) * 100

    if sl_pct <= 0:
        log.warning("sl_pct is zero — forcing minimum")
        sl_pct = _safe_div(vol_profile["atr_4h"], entry) * 100 * 0.3

    tp1, actual_rr, tp_label = _calculate_tp(
        is_long     = is_long,
        entry       = entry,
        sl          = sl,
        grade       = grade_label,
        swings      = swings,
        key_levels  = key_levels,
        d1d         = d1d,
        d1h         = d1h,
        sweep       = sweep or {},
        vol_profile = vol_profile
    )

    result = {
        **base,
        "direction":      direction,
        "dir_class":      "long" if is_long else "short",
        "grade":          grade_label,
        "score":          score_15m,
        "signal_type":    tier["signal_type"],
        "entry":          entry,
        "entry_source":   entry_source,
        "sl":             sl,
        "tp1":            tp1,
        "tp2":            None,
        "sl_pct":         sl_pct,
        "sl_method":      sl_method,
        "tp_label":       tp_label,
        "tp_structural":  "floor" not in tp_label,
        "sl_rejected":    False,
        "risk_pct":       0,
        "risk_amt":       0,
        "pos_size":       0,
        "stake":          0,
        "leverage":       10,
        "margin":         0,
        "eff_lev":        10,
        "atr_used":       vol_profile["atr_4h"],
        "atr_pct":        vol_profile["atr_pct"],
        "adx_used":       vol_profile["adx"],
        "bb_width":       vol_profile["bb_width"],
        "avg_swing":      vol_profile["avg_swing"],
        "vol_class":      vol_profile["volatility_class"],
        "min_rr":         get_min_rr(grade_label),
        "actual_rr":      actual_rr,
        "funding":        market.get("funding", 0),
        "sweep_score":    _safe_float(sweep.get("score", 0) if sweep else 0),
        "disp_score":     _safe_float(displacement.get("score", 0) if displacement else 0),
        "entry_15m":      entry_15m,
        "limit_entry":    limit_entry,
        "limit_method":   limit_method,
        "staleness":      staleness,
        "reason":         entry_source
    }

    result["explanation"] = _attach_explanation(
        result, sweep, displacement, retest,
        d1d, d4h, btc_data, btc_inst,
        oi_matrix, market, regime, session,
        no_trade, wconf
    )

    log.info(
        "Signal generated | grade=%s dir=%s score=%s entry=%s "
        "entry_source=%s sl=%s tp1=%s rr=%s sl_method=%s tp_label=%s "
        "vol_class=%s atr_pct=%.2f adx=%.1f",
        result.get("grade"),
        result.get("direction"),
        result.get("score"),
        result.get("entry"),
        result.get("entry_source"),
        result.get("sl"),
        result.get("tp1"),
        result.get("actual_rr"),
        result.get("sl_method"),
        result.get("tp_label"),
        result.get("vol_class"),
        result.get("atr_pct", 0),
        result.get("adx_used", 0),
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
        log.exception("Explanation build error")
        return {}