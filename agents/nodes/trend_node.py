import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def trend_node(state: SignalAgentState) -> SignalAgentState:
    try:
        from engines.trend.direction import detect

        d4h  = state["d4h"]
        coin = state["coin"]

        trend = detect(d4h, coin)

        if not trend.passed:
            state["signal"] = False
            state["reason"] = trend.reason
            state["trace_steps"].append({
                "node":   "trend",
                "passed": False,
                "reason": trend.reason,
            })
            return state

        state["trend_result"] = trend
        state["direction"]    = trend.direction

        state["trace_steps"].append({
            "node":      "trend",
            "passed":    True,
            "direction": trend.direction,
            "adx":       trend.adx,
        })

    except Exception as e:
        log.error("trend_node: %s", e)
        state["signal"] = False
        state["reason"] = f"trend_error:{e}"

    return state