import logging
from agents.state import SignalAgentState
from engines.indicators import calculate_all

log = logging.getLogger(__name__)


def trend_node(state: SignalAgentState) -> SignalAgentState:
    coin  = state["coin"]
    df_1d = state.get("df_1d")
    df_1w = state.get("df_1w")
    d4h   = state["d4h"]

    try:
        from engines.trend.direction import detect
        trend_result = detect(d4h, coin, df_1d=df_1d, df_1w=df_1w)

        state["trend_result"]   = trend_result
        state["direction"]      = trend_result.direction
        state["trend_strength"] = trend_result.strength

        passed = trend_result.passed

        state["trace_steps"].append({
            "node":        "trend",
            "passed":      passed,
            "direction":   trend_result.direction,
            "adx":         trend_result.adx,
            "alignment":   trend_result.alignment,
            "daily_bias":  trend_result.daily_bias,
            "weekly_bias": trend_result.weekly_bias,
            "btc_score":   trend_result.btc_score,
            "htf_score":   trend_result.htf_score,
            "reason":      trend_result.reason,
        })

        if not passed:
            state["signal"] = False
            state["reason"] = trend_result.reason

        log.debug("trend_node %s — passed:%s direction:%s adx:%.1f alignment:%s",
                  coin, passed, trend_result.direction,
                  trend_result.adx, trend_result.alignment)

    except Exception as e:
        log.error("trend_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"trend_node_error:{e}"
        state["trace_steps"].append({
            "node":   "trend",
            "passed": False,
            "reason": str(e),
        })

    return state