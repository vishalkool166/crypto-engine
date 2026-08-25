import logging
from agents.state import SignalAgentState
from engines.indicators import calculate_all

log = logging.getLogger(__name__)


def reversion_node(state: SignalAgentState) -> SignalAgentState:
    coin      = state["coin"]
    df_1h     = state["df_1h"]
    direction = state["direction"]

    try:
        d1h = calculate_all(df_1h, timeframe="1h")
        state["d1h"]    = d1h
        state["atr_1h"] = float(d1h.get("atr") or df_1h["close"].iloc[-1] * 0.01)

        from engines.reversion.timing import detect
        reversion = detect(d1h, df_1h, direction)

        state["reversion_result"] = reversion
        state["reversion_open"]   = reversion.window_open

        state["trace_steps"].append({
            "node":        "reversion",
            "passed":      reversion.window_open,
            "rsi":         reversion.rsi,
            "bb_touch":    reversion.bb_touch,
            "extreme":     reversion.extreme,
            "score":       reversion.score,
            "reason":      reversion.reason,
        })

        if not reversion.window_open:
            state["signal"] = False
            state["reason"] = f"reversion_window_closed:{reversion.reason}"

        log.debug("reversion_node %s — open:%s rsi:%.1f score:%.3f",
                  coin, reversion.window_open, reversion.rsi, reversion.score)

    except Exception as e:
        log.error("reversion_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"reversion_node_error:{e}"
        state["trace_steps"].append({
            "node":   "reversion",
            "passed": False,
            "reason": str(e),
        })

    return state