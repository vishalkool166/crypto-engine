import logging
import time
from config import cfg
from engines.indicators import calculate_all
from engines import context, sweep, zone, trigger, risk, sizing, narrative
from engines.scorer import SignalScore, assign_grade, score_session, score_ml, SCORE_WEIGHTS
from engines.decision_trace import DecisionTrace, store_trace
from data.rejection_stats import record_scan

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def _get_regime(d4h: dict) -> str:
    trend = d4h.get("trend", {})
    cls   = trend.get("cls", "neutral")
    adx   = float(d4h.get("adx") or 0)
    if cls == "bull" and adx >= 25:
        return "trending"
    if cls == "bear" and adx >= 25:
        return "trending"
    if adx < 20:
        return "choppy"
    return "ranging"


def _get_session() -> str:
    from datetime import datetime, timezone
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return "London"
    if 13 <= hour < 17: return "London/NY Overlap"
    if 17 <= hour < 21: return "New York"
    if 0  <= hour < 8:  return "Asia"
    return "Off Hours"


def _get_total_trades() -> int:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()
    except Exception:
        return 0


def _get_ml_probability(signal: dict) -> float | None:
    try:
        from ml.predictor import predict_win_probability
        wconf = {
            "factors":      [],
            "market_score": signal.get("sweep_score", 0) * 100,
            "entry_score":  signal.get("trigger_score", 0) * 100,
            "btc_score":    6.0,
        }
        return predict_win_probability(signal, wconf)
    except Exception:
        return None


def _get_funding_rate_cached(coin: str) -> float:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return 0.0
        raw = r.get(f"funding:{coin}USDT")
        if raw:
            return float(raw)
        return 0.0
    except Exception:
        return 0.0


def _get_oi_trend(coin: str) -> str:
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            return "unknown"
        raw = r.get(f"oi:{coin}USDT")
        if not raw:
            return "unknown"
        data = json.loads(raw)
        return data.get("trend", "unknown")
    except Exception:
        return "unknown"


def _hard_filters_pass(
    coin:         str,
    direction:    str,
    sweep_result: dict,
    zone_result:  dict,
    trace:        DecisionTrace,
) -> tuple[bool, str]:

    sweep_data = sweep_result.get("sweep") or {}
    age_hours  = float(sweep_data.get("age_hours", 999) or 999)
    max_age    = SE["sweep_max_age_hours"]

    if age_hours > max_age:
        reason = f"sweep_too_old_{age_hours:.1f}h"
        trace.stop(reason, f"Sweep {age_hours:.1f}h old — max {max_age}h")
        store_trace(trace)
        record_scan(coin, direction, reason)
        return False, reason

    zone_data   = zone_result.get("zone") or {}
    touch_count = int(zone_data.get("touch_count", 0) or 0)
    max_touches = SE["zone_max_touches"]

    if touch_count > max_touches:
        reason = f"zone_too_many_touches_{touch_count}"
        trace.stop(reason, f"Zone touched {touch_count}x — max {max_touches}")
        store_trace(trace)
        record_scan(coin, direction, reason)
        return False, reason

    return True, ""


async def run(
    coin:    str,
    df_4h:   object,
    df_1h:   object,
    df_15m:  object,
    balance: float,
    df_1d:   object = None,
    df_1w:   object = None,
) -> dict:

    no_signal = {"coin": coin, "signal": False}
    trace     = DecisionTrace(coin=coin, direction="")
    session   = _get_session()
    trace.session = session

    try:
        d4h  = calculate_all(df_4h,  timeframe="4h")
        d1h  = calculate_all(df_1h,  timeframe="1h")
        d15m_indicators = calculate_all(df_15m, timeframe="15m")

        atr_4h  = d4h.get("atr")  or float(df_4h["close"].iloc[-1])  * 0.01
        atr_1h  = d1h.get("atr")  or float(df_1h["close"].iloc[-1])  * 0.01
        atr_15m = d15m_indicators.get("atr") or float(df_15m["close"].iloc[-1]) * 0.005

        regime = _get_regime(d4h)
        trace.regime = regime

        ctx = context.check(d4h, coin, df_1d=df_1d, df_1w=df_1w)

        trace.direction = ctx.get("direction", "NEUTRAL")
        trace.add_step(
            "ema_context",
            "PASS" if ctx["pass"] else "FAIL",
            0.0,
            ctx.get("trace", {}).get("ema", ""),
        )
        trace.add_step(
            "btc_context",
            "SCORE",
            ctx.get("btc_score", 0),
            ctx.get("trace", {}).get("btc", ""),
        )
        trace.add_step(
            "htf_alignment",
            "SCORE",
            ctx.get("htf_score", 0),
            ctx.get("trace", {}).get("htf", ""),
        )

        if not ctx["pass"]:
            trace.stop(ctx.get("reason", "context"), ctx.get("reason", ""))
            store_trace(trace)
            record_scan(coin, trace.direction, ctx.get("reason", "context"))
            return {
                **no_signal,
                "reason":  ctx.get("reason"),
                "trace":   trace.to_dict(),
            }

        direction = ctx["direction"]
        alignment = ctx.get("alignment")

        funding = _get_funding_rate_cached(coin)
        if abs(funding) > 0.0005:
            reason = "funding_extreme"
            trace.stop(reason, f"Funding {funding:.4f} — extreme squeeze risk")
            store_trace(trace)
            record_scan(coin, direction, reason)
            return {
                **no_signal,
                "reason":  reason,
                "trace":   trace.to_dict(),
            }

        sig_score           = SignalScore()
        sig_score.coin      = coin
        sig_score.direction = direction

        sig_score.add(
            "btc_context",
            ctx.get("btc_score", 0),
            SCORE_WEIGHTS["btc_context"]["max"],
            True,
            ctx.get("trace", {}).get("btc", ""),
        )
        sig_score.add(
            "htf_alignment",
            ctx.get("htf_score", 0),
            SCORE_WEIGHTS["htf_alignment"]["max"],
            True,
            ctx.get("trace", {}).get("htf", ""),
        )

        sweep_result = sweep.detect(df_1h, d1h, direction)

        trace.add_step(
            "sweep",
            "PASS" if sweep_result["detected"] else "FAIL",
            sweep_result.get("score", 0),
            sweep_result.get("desc", ""),
        )

        if not sweep_result["detected"]:
            trace.stop("no_sweep", "No liquidity sweep detected")
            store_trace(trace)
            record_scan(coin, direction, "no_sweep")
            return {
                **no_signal,
                "reason": "no_sweep",
                "trace":  trace.to_dict(),
            }

        if sweep_result["score"] < SE["sweep_min_score"]:
            trace.stop("sweep_score_low", f"Sweep score {sweep_result['score']:.3f} < {SE['sweep_min_score']}")
            store_trace(trace)
            record_scan(coin, direction, "sweep_score_low")
            return {
                **no_signal,
                "reason":      "sweep_score_low",
                "sweep_found": True,
                "sweep_score": sweep_result["score"],
                "sweep":       sweep_result["sweep"],
                "direction":   direction,
                "trace":       trace.to_dict(),
            }

        disp = sweep_result.get("displacement", {})
        if not disp.get("found"):
            trace.stop("no_displacement", "No displacement after sweep — institutional intent not confirmed")
            store_trace(trace)
            record_scan(coin, direction, "no_displacement")
            return {
                **no_signal,
                "reason":      "no_displacement",
                "sweep_found": True,
                "sweep_score": sweep_result["score"],
                "direction":   direction,
                "trace":       trace.to_dict(),
            }

        sig_score.add(
            "sweep",
            sweep_result["score"] * SCORE_WEIGHTS["sweep"]["max"],
            SCORE_WEIGHTS["sweep"]["max"],
            True,
            sweep_result.get("desc", ""),
        )

        zone_result = zone.detect(d4h, df_4h, direction, atr_1h)

        trace.add_step(
            "zone",
            "PASS" if zone_result["detected"] else "FAIL",
            zone_result.get("score", 0),
            zone_result.get("zone", {}).get("origin_desc", "") if zone_result.get("zone") else "",
        )

        if not zone_result["detected"]:
            trace.stop("no_zone", "No order block or FVG found")
            store_trace(trace)
            record_scan(coin, direction, "no_zone")
            return {
                **no_signal,
                "reason":      "no_zone",
                "sweep_found": True,
                "sweep_score": sweep_result["score"],
                "sweep":       sweep_result["sweep"],
                "direction":   direction,
                "trace":       trace.to_dict(),
            }

        if zone_result["score"] < SE["zone_min_score"]:
            trace.stop("zone_score_low", f"Zone score {zone_result['score']:.3f} < {SE['zone_min_score']}")
            store_trace(trace)
            record_scan(coin, direction, "zone_score_low")
            return {
                **no_signal,
                "reason":      "zone_score_low",
                "sweep_found": True,
                "zone_found":  True,
                "sweep_score": sweep_result["score"],
                "zone_score":  zone_result["score"],
                "sweep":       sweep_result["sweep"],
                "zone":        zone_result["zone"],
                "direction":   direction,
                "trace":       trace.to_dict(),
            }

        hard_pass, hard_reason = _hard_filters_pass(
            coin         = coin,
            direction    = direction,
            sweep_result = sweep_result,
            zone_result  = zone_result,
            trace        = trace,
        )

        if not hard_pass:
            return {
                **no_signal,
                "reason":      hard_reason,
                "sweep_found": True,
                "zone_found":  True,
                "direction":   direction,
                "trace":       trace.to_dict(),
            }

        oi_trend = _get_oi_trend(coin)
        is_long  = direction == "LONG"

        if oi_trend != "unknown":
            if is_long and oi_trend == "falling":
                trace.stop("oi_divergence", "OI falling while price rising — fake move")
                store_trace(trace)
                record_scan(coin, direction, "oi_divergence")
                return {
                    **no_signal,
                    "reason":      "oi_divergence",
                    "sweep_found": True,
                    "zone_found":  True,
                    "direction":   direction,
                    "trace":       trace.to_dict(),
                }
            if not is_long and oi_trend == "falling":
                trace.stop("oi_divergence", "OI falling while price falling — fake move")
                store_trace(trace)
                record_scan(coin, direction, "oi_divergence")
                return {
                    **no_signal,
                    "reason":      "oi_divergence",
                    "sweep_found": True,
                    "zone_found":  True,
                    "direction":   direction,
                    "trace":       trace.to_dict(),
                }

        sig_score.add(
            "zone",
            zone_result["score"] * SCORE_WEIGHTS["zone"]["max"],
            SCORE_WEIGHTS["zone"]["max"],
            True,
            zone_result.get("zone", {}).get("origin_desc", "") if zone_result.get("zone") else "",
        )

        trigger_result = trigger.detect(df_15m, zone_result["zone"], direction, atr_15m)

        trace.add_step(
            "trigger",
            "PASS" if trigger_result["confirmed"] else "FAIL",
            trigger_result.get("score", 0),
            trigger_result.get("reason", ""),
        )

        if not trigger_result["confirmed"]:
            trace.stop("no_trigger", trigger_result.get("reason", "No trigger pattern"))
            store_trace(trace)
            record_scan(coin, direction, "no_trigger")
            return {
                **no_signal,
                "reason":      trigger_result.get("reason", "no_trigger"),
                "sweep_found": True,
                "zone_found":  True,
                "sweep_score": sweep_result["score"],
                "zone_score":  zone_result["score"],
                "sweep":       sweep_result["sweep"],
                "zone":        zone_result["zone"],
                "direction":   direction,
                "trace":       trace.to_dict(),
            }

        sig_score.add(
            "trigger",
            trigger_result["score"] * SCORE_WEIGHTS["trigger"]["max"],
            SCORE_WEIGHTS["trigger"]["max"],
            True,
            trigger_result.get("pattern", ""),
        )

        session_score, session_reason = score_session(session)
        sig_score.add(
            "session",
            session_score,
            SCORE_WEIGHTS["session"]["max"],
            True,
            session_reason,
        )
        trace.add_step("session", "SCORE", session_score, session_reason)

        zone_data   = zone_result["zone"]
        limit_entry = zone_data["top"] if is_long else zone_data["bottom"]

        risk_result = risk.calculate(
            direction = direction,
            entry     = limit_entry,
            sweep     = sweep_result["sweep"],
            zone      = zone_data,
            trigger   = {**trigger_result, "entry_price": limit_entry},
            atr_15m   = atr_15m,
            d1h       = d1h,
            d4h       = d4h,
        )

        trace.add_step(
            "risk",
            "PASS" if risk_result["valid"] else "FAIL",
            0.0,
            risk_result.get("reason", ""),
        )

        if not risk_result["valid"]:
            trace.stop(f"risk_{risk_result['reason']}", risk_result["reason"])
            store_trace(trace)
            record_scan(coin, direction, "risk_invalid")
            return {
                **no_signal,
                "reason": risk_result["reason"],
                "trace":  trace.to_dict(),
            }

        total_trades   = _get_total_trades()
        ml_probability = _get_ml_probability({
            "coin":          coin,
            "direction":     direction,
            "sweep_score":   sweep_result["score"],
            "zone_score":    zone_result["score"],
            "trigger_score": trigger_result["score"],
            "grade":         "A",
            "score":         sig_score.pct(),
            "funding":       funding,
        })

        ml_score, ml_reason = score_ml(ml_probability, total_trades)
        sig_score.add(
            "ml",
            ml_score,
            SCORE_WEIGHTS["ml"]["max"],
            True,
            ml_reason,
        )
        trace.add_step("ml", "SCORE", ml_score, ml_reason)

        context_score   = ctx.get("context_score", 0)
        sig_score.total = round(sig_score.total + context_score, 3)

        pct   = sig_score.pct()
        grade = assign_grade(pct, regime)

        trace.score_breakdown = sig_score.to_dict()

        if grade == "F":
            trace.stop("combined_score_low", f"Score {pct:.1f}% below grade threshold for {regime} regime")
            store_trace(trace)
            record_scan(coin, direction, "combined_score_low")
            return {
                **no_signal,
                "reason": "combined_score_low",
                "trace":  trace.to_dict(),
            }

        sizing_result = sizing.calculate(
            balance        = balance,
            sl_pct         = risk_result["sl_pct"],
            sl_dist        = risk_result["sl_dist"],
            grade          = grade,
            direction      = direction,
            ml_probability = ml_probability,
            alignment      = alignment,
        )

        if sizing_result.get("skip"):
            reason = sizing_result["reason"]
            trace.stop(reason, reason)
            store_trace(trace)
            record_scan(coin, direction, reason)
            return {
                **no_signal,
                "reason": reason,
                "trace":  trace.to_dict(),
            }

        narrative_text = narrative.build(
            coin      = coin,
            direction = direction,
            grade     = grade,
            context   = ctx,
            sweep     = sweep_result,
            zone      = zone_data,
            trigger   = {**trigger_result, "entry_price": limit_entry},
            risk      = risk_result,
            sizing    = sizing_result,
        )

        displacement = sweep_result.get("displacement", {})

        combined = round(
            sweep_result["score"]   * 0.40 +
            zone_result["score"]    * 0.35 +
            trigger_result["score"] * 0.25,
            3,
        )

        trace.approve(grade, pct)
        store_trace(trace)
        record_scan(coin, direction, "TRADE")

        return {
            "signal":         True,
            "coin":           coin,
            "direction":      direction,
            "grade":          grade,
            "score":          combined,
            "score_pct":      pct,
            "score_detail":   sig_score.to_dict(),
            "entry":          limit_entry,
            "entry_type":     "limit",
            "sl":             risk_result["sl"],
            "tp1":            risk_result["tp1"],
            "tp2":            risk_result["tp2"],
            "sl_pct":         risk_result["sl_pct"],
            "sl_dist":        risk_result["sl_dist"],
            "rr1":            risk_result["rr1"],
            "rr2":            risk_result["rr2"],
            "tp1_label":      risk_result["tp1_label"],
            "tp2_label":      risk_result["tp2_label"],
            "sl_reason":      risk_result["sl_reason"],
            "poc_used":       risk_result.get("poc_used", False),
            "risk_amt":       sizing_result["risk_amt"],
            "pos_size":       sizing_result["position_size"],
            "stake":          sizing_result["stake"],
            "leverage":       sizing_result["leverage"],
            "risk_pct":       sizing_result["risk_pct"],
            "tp1_pct":        sizing_result.get("tp1_pct", 0.65),
            "tp2_pct":        sizing_result.get("tp2_pct", 0.35),
            "sweep_score":    sweep_result["score"],
            "zone_score":     zone_result["score"],
            "trigger_score":  trigger_result["score"],
            "sweep":          sweep_result["sweep"],
            "zone":           zone_data,
            "sweep_found":    True,
            "zone_found":     True,
            "narrative":      narrative_text,
            "signal_type":    "FULL",
            "atr_4h":         atr_4h,
            "atr_1h":         atr_1h,
            "atr_15m":        atr_15m,
            "generated_at":   time.time(),
            "alignment":      alignment,
            "displacement":   displacement,
            "daily_bias":     alignment.get("daily",     "NEUTRAL") if alignment else "NEUTRAL",
            "weekly_bias":    alignment.get("weekly",    "NEUTRAL") if alignment else "NEUTRAL",
            "alignment_str":  alignment.get("alignment", "none")    if alignment else "none",
            "ml_probability": ml_probability,
            "funding":        funding,
            "regime":         regime,
            "session":        session,
            "trace":          trace.to_dict(),
        }

    except Exception as e:
        log.error("signal.run %s: %s", coin, e, exc_info=True)
        store_trace(trace)
        return {**no_signal, "reason": str(e)}