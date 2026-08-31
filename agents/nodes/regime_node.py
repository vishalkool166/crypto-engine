import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def regime_node(state: SignalAgentState) -> SignalAgentState:
    try:
        from engines.core.indicators import get_indicators
        from engines.regime.detector import detect

        df_4h = state["df_4h"]
        df_1h = state.get("df_1h")

        if df_4h is None or len(df_4h) < 50:
            state["signal"] = False
            state["reason"] = "insufficient_4h_data"
            return state

        d4h = get_indicators(df_4h, timeframe="4h")
        state["d4h"]    = d4h
        state["atr_4h"] = float(d4h.get("atr") or 0)

        if df_1h is not None and len(df_1h) >= 50:
            d1h = get_indicators(df_1h, timeframe="1h")
            state["d1h"]    = d1h
            state["atr_1h"] = float(d1h.get("atr") or 0)
        else:
            state["d1h"]    = {}
            state["atr_1h"] = 0.0

        regime = detect(d4h)
        state["regime_result"] = regime
        state["regime_label"]  = regime.label
        state["regime_mult"]   = regime.size_mult

        if regime.is_volatile:
            state["signal"] = False
            state["reason"] = "volatile_regime"
            return state

        state["trace_steps"].append({
            "node":      "regime",
            "passed":    True,
            "label":     regime.label,
            "adx":       regime.adx,
            "size_mult": regime.size_mult,
        })

    except Exception as e:
        log.error("regime_node: %s", e)
        state["signal"] = False
        state["reason"] = f"regime_error:{e}"

    return state