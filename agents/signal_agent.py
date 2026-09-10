import logging
import time

log = logging.getLogger(__name__)


async def run(
    coin:    str,
    df_4h:   object,
    df_1h:   object,
    balance: float,
) -> dict:
    start = time.time()
    log.info("Signal agent started: %s", coin)

    try:
        from engines.core.indicators import get_indicators
        from engines.regime.detector import detect as detect_regime
        from engines.trend.direction import detect as detect_trend
        from engines.scoring.scorer import score as calc_score, get_session
        from engines.risk.calculator import calculate as calc_risk
        from engines.sizing.adaptive import calculate as calc_sizing

        if df_4h is None or len(df_4h) < 50:
            return _no_signal(coin, "insufficient_4h_data", start)

        d4h = get_indicators(df_4h, timeframe="4h")

        d1h = {}
        if df_1h is not None and len(df_1h) >= 50:
            d1h = get_indicators(df_1h, timeframe="1h")

        session = get_session()
        trace   = []

        regime = detect_regime(d4h)
        trace.append({
            "node":      "regime",
            "passed":    not regime.is_volatile,
            "label":     regime.label,
            "adx":       regime.adx,
            "size_mult": regime.size_mult,
        })

        if regime.is_volatile:
            return _no_signal(coin, "volatile_regime", start, trace)

        trend = detect_trend(d4h, coin)
        trace.append({
            "node":      "trend",
            "passed":    trend.passed,
            "direction": trend.direction,
            "adx":       trend.adx,
            "reason":    trend.reason,
        })

        if not trend.passed:
            return _no_signal(coin, trend.reason, start, trace)

        direction = trend.direction

        adx       = float(d4h.get("adx")       or 0)
        vol_ratio = float(d4h.get("vol_ratio") or 1.0)
        rsi       = float(d1h.get("rsi") or d4h.get("rsi") or 50)

        score_result = calc_score(adx, rsi, vol_ratio, direction, regime.label)
        trace.append({
            "node":    "grade",
            "passed":  score_result.grade != "F",
            "grade":   score_result.grade,
            "score":   score_result.total,
            "adx_pts": score_result.adx_pts,
            "rsi_pts": score_result.rsi_pts,
            "vol_pts": score_result.vol_pts,
            "reason":  "grade_f" if score_result.grade == "F" else "",
        })

        if score_result.grade == "F":
            return _no_signal(coin, "grade_f", start, trace)

        price       = float(d4h.get("price")      or 0)
        atr         = float(d4h.get("atr")        or 0)
        swing_high  = float(d4h.get("swing_high") or 0)
        swing_low   = float(d4h.get("swing_low")  or 0)

        if not price or not atr:
            return _no_signal(coin, "missing_price_or_atr", start, trace)

        swing_level = swing_low if direction == "LONG" else swing_high
        if not swing_level:
            return _no_signal(coin, "missing_swing_level", start, trace)

        risk = calc_risk(
            direction   = direction,
            entry       = price,
            swing_level = swing_level,
            atr         = atr,
        )

        trace.append({
            "node":   "risk",
            "passed": risk.valid,
            "entry":  risk.entry,
            "sl":     risk.sl,
            "tp1":    risk.tp1,
            "sl_pct": risk.sl_pct,
            "rr1":    risk.rr1,
            "reason": risk.reason,
        })

        if not risk.valid:
            return _no_signal(coin, risk.reason, start, trace)

        sizing = calc_sizing(
            balance     = balance,
            sl_pct      = risk.sl_pct,
            sl_dist     = risk.sl_dist,
            grade       = score_result.grade,
            direction   = direction,
            regime_mult = regime.size_mult,
            session     = session,
        )

        trace.append({
            "node":     "sizing",
            "passed":   not sizing.skip,
            "stake":    sizing.stake,
            "leverage": sizing.leverage,
            "risk_pct": sizing.risk_pct,
            "risk_amt": sizing.risk_amt,
            "reason":   sizing.reason,
        })

        if sizing.skip:
            return _no_signal(coin, sizing.reason, start, trace)

        elapsed = round((time.time() - start) * 1000, 1)

        result = {
            "signal":    True,
            "coin":      coin,
            "direction": direction,
            "grade":     score_result.grade,
            "score":     score_result.total,
            "entry":     risk.entry,
            "sl":        risk.sl,
            "tp1":       risk.tp1,
            "tp2":       risk.tp2,
            "sl_pct":    risk.sl_pct,
            "sl_dist":   risk.sl_dist,
            "rr1":       risk.rr1,
            "rr2":       risk.rr2,
            "risk_amt":  sizing.risk_amt,
            "pos_size":  sizing.position_size,
            "stake":     sizing.stake,
            "leverage":  sizing.leverage,
            "risk_pct":  sizing.risk_pct,
            "regime":    regime.label,
            "session":   session,
            "adx":       adx,
            "rsi":       rsi,
            "agent_ms":  elapsed,
            "agent_steps": len(trace),
            "trace": {
                "steps":     trace,
                "direction": direction,
                "grade":     score_result.grade,
                "score":     score_result.total,
            },
        }

        log.info(
            "Signal agent complete: %s signal:True grade:%s score:%.1f elapsed:%sms",
            coin, score_result.grade, score_result.total, elapsed,
        )

        return result

    except Exception as e:
        elapsed = round((time.time() - start) * 1000, 1)
        log.error("Signal agent error %s: %s", coin, e, exc_info=True)
        return _no_signal(coin, str(e), start)


def _no_signal(coin: str, reason: str, start: float, trace: list = None) -> dict:
    elapsed = round((time.time() - start) * 1000, 1)
    
    adx_from_trace = 0.0
    if trace:
        for step in trace:
            if step.get('adx'):
                adx_from_trace = float(step['adx'])
                break
    
    return {
        "signal":      False,
        "coin":        coin,
        "direction":   "NEUTRAL",
        "grade":       "F",
        "score":       0,
        "reason":      reason,
        "adx":         adx_from_trace,
        "agent_ms":    elapsed,
        "agent_steps": len(trace) if trace else 0,
        "trace": {
            "steps":     trace or [],
            "direction": "NEUTRAL",
            "grade":     "F",
            "score":     0,
        },
    }