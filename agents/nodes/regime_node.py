import logging
from agents.state import SignalAgentState
from engines.indicators import calculate_all

log = logging.getLogger(__name__)


def regime_node(state: SignalAgentState) -> SignalAgentState:
    coin  = state["coin"]
    df_4h = state["df_4h"]
    df_1w = state.get("df_1w")

    try:
        d4h = calculate_all(df_4h, timeframe="4h")
        state["d4h"]    = d4h
        state["atr_4h"] = float(d4h.get("atr") or df_4h["close"].iloc[-1] * 0.01)

        d1w = None
        if df_1w is not None and len(df_1w) >= 10:
            d1w = calculate_all(df_1w, timeframe="1w")

        from engines.regime.detector import detect
        regime_result = detect(d4h, d1w)

        state["regime_result"] = regime_result
        state["regime_label"]  = regime_result.label
        state["regime_mult"]   = regime_result.size_mult

        state["trace_steps"].append({
            "node":       "regime",
            "passed":     True,
            "label":      regime_result.label,
            "adx":        regime_result.adx,
            "atr_pct":    regime_result.atr_pct,
            "size_mult":  regime_result.size_mult,
            "reason":     regime_result.reason,
        })

        log.debug("regime_node %s — label:%s adx:%.1f mult:%.2f",
                  coin, regime_result.label, regime_result.adx, regime_result.size_mult)

    except Exception as e:
        log.error("regime_node %s: %s", coin, e)
        from engines.regime.detector import RegimeResult
        fallback = RegimeResult(
            label       = "ranging",
            size_mult   = 0.8,
            adx         = 0.0,
            atr_pct     = 0.0,
            trend_cls   = "neutral",
            is_trending = False,
            is_ranging  = True,
            is_choppy   = False,
            is_volatile = False,
            reason      = f"regime_node_error:{e}",
        )
        state["regime_result"] = fallback
        state["regime_label"]  = "ranging"
        state["regime_mult"]   = 0.8
        state["trace_steps"].append({
            "node":   "regime",
            "passed": True,
            "label":  "ranging",
            "reason": f"error_fallback:{e}",
        })

    return state