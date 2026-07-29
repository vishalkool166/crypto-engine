import logging
from agents.state import SignalAgentState
from engines.indicators import calculate_all

log = logging.getLogger(__name__)


def context_node(state: SignalAgentState) -> SignalAgentState:
    coin  = state["coin"]
    df_4h = state["df_4h"]
    df_1d = state.get("df_1d")
    df_1w = state.get("df_1w")

    try:
        d4h = calculate_all(df_4h, timeframe="4h")
        state["d4h"] = d4h

        atr_4h = d4h.get("atr") or float(df_4h["close"].iloc[-1]) * 0.01
        state["atr_4h"] = atr_4h

        from engines.context import check
        ctx = check(d4h, coin, df_1d=df_1d, df_1w=df_1w)
        state["ctx"] = ctx

        step = {
            "node":      "context",
            "passed":    ctx["pass"],
            "direction": ctx.get("direction", "NEUTRAL"),
            "btc_score": ctx.get("btc_score", 0),
            "htf_score": ctx.get("htf_score", 0),
            "reason":    ctx.get("reason", ""),
        }
        state["trace_steps"].append(step)

        if ctx["pass"]:
            state["direction"] = ctx["direction"]
            state["reason"]    = ""
        else:
            state["direction"] = "NEUTRAL"
            state["signal"]    = False
            state["reason"]    = ctx.get("reason", "context_failed")

        log.debug(
            "context_node %s — passed:%s direction:%s",
            coin, ctx["pass"], ctx.get("direction")
        )

    except Exception as e:
        log.error("context_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"context_node_error: {e}"
        state["trace_steps"].append({
            "node":   "context",
            "passed": False,
            "reason": str(e),
        })

    return state