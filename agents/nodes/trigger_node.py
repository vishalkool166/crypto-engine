import logging
from agents.state import SignalAgentState
from engines.indicators import calculate_all
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def trigger_node(state: SignalAgentState) -> SignalAgentState:
    coin        = state["coin"]
    df_15m      = state["df_15m"]
    direction   = state["direction"]
    zone_result = state["zone_result"]

    try:
        d15m = calculate_all(df_15m, timeframe="15m")
        state["d15m"] = d15m

        atr_15m = d15m.get("atr") or float(df_15m["close"].iloc[-1]) * 0.005
        state["atr_15m"] = atr_15m

        zone_data = zone_result.get("zone") or {}

        from engines.trigger import detect
        trigger_result = detect(
            df_15m    = df_15m,
            zone      = zone_data,
            direction = direction,
            atr_15m   = atr_15m,
        )
        state["trigger_result"] = trigger_result

        passed = trigger_result["confirmed"]

        step = {
            "node":        "trigger",
            "passed":      passed,
            "confirmed":   trigger_result["confirmed"],
            "pattern":     trigger_result.get("pattern",     ""),
            "score":       trigger_result.get("score",       0),
            "vol_mult":    trigger_result.get("vol_mult",    0),
            "entry_price": trigger_result.get("entry_price", 0),
            "reason":      trigger_result.get("reason", "") if not passed else "",
        }
        state["trace_steps"].append(step)

        if not passed:
            state["signal"] = False
            state["reason"] = trigger_result.get("reason", "no_trigger")

        log.debug(
            "trigger_node %s — passed:%s pattern:%s score:%.3f",
            coin, passed,
            trigger_result.get("pattern", "--"),
            trigger_result.get("score", 0)
        )

    except Exception as e:
        log.error("trigger_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"trigger_node_error: {e}"
        state["trace_steps"].append({
            "node":   "trigger",
            "passed": False,
            "reason": str(e),
        })

    return state