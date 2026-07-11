import logging
import time
from config import cfg
from engines.indicators import calculate_all
from engines import context, sweep, zone, trigger, risk, sizing, narrative

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def _grade(combined: float) -> str:
    if combined >= SE["grade_aplus_threshold"]:
        return "A+"
    if combined >= SE["grade_a_threshold"]:
        return "A"
    if combined >= SE["grade_b_threshold"]:
        return "B"
    return "F"


def _combined_score(sweep_score: float, zone_score: float, trigger_score: float) -> float:
    return round(
        sweep_score   * 0.40 +
        zone_score    * 0.35 +
        trigger_score * 0.25,
        3
    )


async def run(
    coin:    str,
    df_4h:   object,
    df_1h:   object,
    df_15m:  object,
    balance: float,
) -> dict:

    no_signal = {"coin": coin, "signal": False}

    try:
        d4h = calculate_all(df_4h, timeframe="4h")
        d1h = calculate_all(df_1h, timeframe="1h")

        atr_4h  = d4h.get("atr") or float(df_4h["close"].iloc[-1]) * 0.01
        atr_1h  = d1h.get("atr") or float(df_1h["close"].iloc[-1]) * 0.01
        atr_15m = (
            calculate_all(df_15m, timeframe="15m").get("atr")
            or float(df_15m["close"].iloc[-1]) * 0.005
        )

        ctx = context.check(d4h, coin)
        if not ctx["pass"]:
            return {**no_signal, "reason": ctx["reason"]}

        direction = ctx["direction"]

        sweep_result = sweep.detect(df_1h, d1h, direction)
        if not sweep_result["detected"]:
            return {**no_signal, "reason": "no_sweep"}
        if sweep_result["score"] < SE["sweep_min_score"]:
            return {**no_signal, "reason": "sweep_score_low"}

        zone_result = zone.detect(d4h, df_4h, direction, atr_1h)
        if not zone_result["detected"]:
            return {**no_signal, "reason": "no_zone"}
        if zone_result["score"] < SE["zone_min_score"]:
            return {**no_signal, "reason": "zone_score_low"}

        trigger_result = trigger.detect(df_15m, zone_result["zone"], direction, atr_15m)
        if not trigger_result["confirmed"]:
            return {**no_signal, "reason": trigger_result.get("reason", "no_trigger")}

        combined = _combined_score(
            sweep_result["score"],
            zone_result["score"],
            trigger_result["score"],
        )

        grade = _grade(combined)
        if grade == "F":
            return {**no_signal, "reason": "combined_score_low"}

        entry = trigger_result["entry_price"]

        risk_result = risk.calculate(
            direction = direction,
            entry     = entry,
            sweep     = sweep_result["sweep"],
            zone      = zone_result["zone"],
            trigger   = trigger_result,
            atr_15m   = atr_15m,
            d1h       = d1h,
            d4h       = d4h,
        )

        if not risk_result["valid"]:
            return {**no_signal, "reason": risk_result["reason"]}

        sizing_result = sizing.calculate(
            balance   = balance,
            sl_pct    = risk_result["sl_pct"],
            sl_dist   = risk_result["sl_dist"],
            grade     = grade,
            direction = direction,
        )

        if sizing_result.get("skip"):
            return {**no_signal, "reason": sizing_result["reason"]}

        narrative_text = narrative.build(
            coin      = coin,
            direction = direction,
            grade     = grade,
            context   = ctx,
            sweep     = sweep_result,
            zone      = zone_result["zone"],
            trigger   = trigger_result,
            risk      = risk_result,
            sizing    = sizing_result,
        )

        return {
            "signal":        True,
            "coin":          coin,
            "direction":     direction,
            "grade":         grade,
            "score":         combined,
            "entry":         entry,
            "sl":            risk_result["sl"],
            "tp1":           risk_result["tp1"],
            "tp2":           risk_result["tp2"],
            "sl_pct":        risk_result["sl_pct"],
            "sl_dist":       risk_result["sl_dist"],
            "rr1":           risk_result["rr1"],
            "rr2":           risk_result["rr2"],
            "tp1_label":     risk_result["tp1_label"],
            "tp2_label":     risk_result["tp2_label"],
            "sl_reason":     risk_result["sl_reason"],
            "risk_amt":      sizing_result["risk_amt"],
            "pos_size":      sizing_result["position_size"],
            "stake":         sizing_result["stake"],
            "leverage":      sizing_result["leverage"],
            "risk_pct":      sizing_result["risk_pct"],
            "sweep_score":   sweep_result["score"],
            "zone_score":    zone_result["score"],
            "trigger_score": trigger_result["score"],
            "sweep":         sweep_result["sweep"],
            "zone":          zone_result["zone"],
            "narrative":     narrative_text,
            "signal_type":   "FULL",
            "atr_4h":        atr_4h,
            "atr_1h":        atr_1h,
            "atr_15m":       atr_15m,
            "generated_at":  time.time(),
        }

    except Exception as e:
        log.error("signal.run %s: %s", coin, e, exc_info=True)
        return {**no_signal, "reason": str(e)}