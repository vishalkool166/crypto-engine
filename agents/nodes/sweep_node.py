import logging
from agents.state import SignalAgentState
from engines.indicators import calculate_all
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def sweep_node(state: SignalAgentState) -> SignalAgentState:
    coin      = state["coin"]
    df_1h     = state["df_1h"]
    direction = state["direction"]

    try:
        d1h = calculate_all(df_1h, timeframe="1h")
        state["d1h"] = d1h

        atr_1h = d1h.get("atr") or float(df_1h["close"].iloc[-1]) * 0.01
        state["atr_1h"] = atr_1h

        from engines.sweep import detect
        sweep_result = detect(df_1h, d1h, direction)
        state["sweep_result"] = sweep_result

        passed = (
            sweep_result["detected"] and
            sweep_result["score"] >= SE["sweep_min_score"]
        )

        step = {
            "node":      "sweep",
            "passed":    passed,
            "detected":  sweep_result["detected"],
            "score":     sweep_result.get("score", 0),
            "label":     sweep_result.get("label", ""),
            "age_hours": (sweep_result.get("sweep") or {}).get("age_hours", 0),
            "reason":    "" if passed else (
                "no_sweep" if not sweep_result["detected"]
                else f"sweep_score_low:{sweep_result['score']:.3f}"
            ),
        }
        state["trace_steps"].append(step)

        if not passed:
            state["signal"] = False
            state["reason"] = step["reason"]

        log.debug(
            "sweep_node %s — passed:%s score:%.3f",
            coin, passed, sweep_result.get("score", 0)
        )

    except Exception as e:
        log.error("sweep_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"sweep_node_error: {e}"
        state["trace_steps"].append({
            "node":   "sweep",
            "passed": False,
            "reason": str(e),
        })

    return state