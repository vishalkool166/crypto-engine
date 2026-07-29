import logging
from agents.state import SignalAgentState
from config import cfg

log = logging.getLogger(__name__)

SE = cfg.SCALP_ENGINE


def zone_node(state: SignalAgentState) -> SignalAgentState:
    coin      = state["coin"]
    df_4h     = state["df_4h"]
    d4h       = state["d4h"]
    direction = state["direction"]
    atr_1h    = state["atr_1h"]

    try:
        from engines.zone import detect
        zone_result = detect(d4h, df_4h, direction, atr_1h)
        state["zone_result"] = zone_result

        passed = (
            zone_result["detected"] and
            zone_result["score"] >= SE["zone_min_score"]
        )

        zone_data = zone_result.get("zone") or {}

        step = {
            "node":         "zone",
            "passed":       passed,
            "detected":     zone_result["detected"],
            "score":        zone_result.get("score", 0),
            "zone_type":    zone_data.get("type", "--"),
            "zone_top":     zone_data.get("top",    0),
            "zone_bottom":  zone_data.get("bottom", 0),
            "touch_count":  zone_data.get("touch_count", 0),
            "distance_pct": zone_data.get("distance_pct", 0),
            "reason":       "" if passed else (
                "no_zone" if not zone_result["detected"]
                else f"zone_score_low:{zone_result['score']:.3f}"
            ),
        }
        state["trace_steps"].append(step)

        if not passed:
            state["signal"] = False
            state["reason"] = step["reason"]

        log.debug(
            "zone_node %s — passed:%s score:%.3f type:%s",
            coin, passed, zone_result.get("score", 0),
            zone_data.get("type", "--")
        )

    except Exception as e:
        log.error("zone_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"zone_node_error: {e}"
        state["trace_steps"].append({
            "node":   "zone",
            "passed": False,
            "reason": str(e),
        })

    return state