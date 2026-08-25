import logging
from agents.state import SignalAgentState
from engines.indicators import calculate_all

log = logging.getLogger(__name__)


def ict_node(state: SignalAgentState) -> SignalAgentState:
    coin      = state["coin"]
    df_4h     = state["df_4h"]
    df_1h     = state["df_1h"]
    df_15m    = state["df_15m"]
    d4h       = state["d4h"]
    d1h       = state["d1h"]
    direction = state["direction"]
    atr_1h    = state["atr_1h"]

    try:
        d15m = calculate_all(df_15m, timeframe="15m")
        state["d15m"]    = d15m
        state["atr_15m"] = float(d15m.get("atr") or df_15m["close"].iloc[-1] * 0.005)

        atr_15m = state["atr_15m"]

        from engines.ict.confirmation import confirm
        ict_result = confirm(
            df_4h     = df_4h,
            d4h       = d4h,
            df_1h     = df_1h,
            d1h       = d1h,
            df_15m    = df_15m,
            d15m      = d15m,
            direction = direction,
            atr_1h    = atr_1h,
            atr_15m   = atr_15m,
        )

        state["ict_result"] = ict_result

        passed = ict_result.confirmed

        sweep_data = ict_result.sweep
        zone_data  = ict_result.zone

        state["trace_steps"].append({
            "node":          "ict",
            "passed":        passed,
            "sweep_score":   ict_result.sweep_score,
            "zone_score":    ict_result.zone_score,
            "trigger_score": ict_result.trigger_score,
            "combined":      ict_result.score,
            "sweep_label":   sweep_data.label     if sweep_data else "",
            "sweep_age":     sweep_data.age_hours if sweep_data else 0,
            "zone_type":     zone_data.type       if zone_data  else "",
            "entry_price":   ict_result.entry_price,
            "reason":        ict_result.reason,
        })

        if not passed:
            state["signal"] = False
            state["reason"] = ict_result.reason

            from data.rejection_stats import record_scan
            record_scan(coin, direction, ict_result.reason or "ict_failed")

        log.debug(
            "ict_node %s — passed:%s sweep:%.3f zone:%.3f trigger:%.3f combined:%.3f",
            coin, passed,
            ict_result.sweep_score,
            ict_result.zone_score,
            ict_result.trigger_score,
            ict_result.score,
        )

    except Exception as e:
        log.error("ict_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"ict_node_error:{e}"
        state["trace_steps"].append({
            "node":   "ict",
            "passed": False,
            "reason": str(e),
        })

    return state