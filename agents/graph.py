import logging
from langgraph.graph import StateGraph, END
from agents.state import SignalAgentState
from agents.nodes.regime_node  import regime_node
from agents.nodes.trend_node   import trend_node
from agents.nodes.grade_node   import grade_node
from agents.nodes.risk_node    import risk_node
from agents.nodes.sizing_node  import sizing_node

log = logging.getLogger(__name__)


def _after_trend(state: SignalAgentState) -> str:
    return "end" if not state.get("signal", True) else "continue"


def _after_grade(state: SignalAgentState) -> str:
    return "end" if not state.get("signal", True) else "continue"


def _after_risk(state: SignalAgentState) -> str:
    return "end" if not state.get("signal", True) else "continue"


def _after_sizing(state: SignalAgentState) -> str:
    return "end" if not state.get("signal", True) else "continue"


def _set_session(state: SignalAgentState) -> SignalAgentState:
    from engines.scoring.scorer import get_session
    state["session"] = get_session()
    return state


def _load_1h(state: SignalAgentState) -> SignalAgentState:
    try:
        from engines.core.indicators import get_indicators
        df_1h = state.get("df_1h")
        if df_1h is not None and len(df_1h) >= 50:
            d1h = get_indicators(df_1h, timeframe="1h")
            state["d1h"]    = d1h
            state["atr_1h"] = float(d1h.get("atr") or 0)
        else:
            state["d1h"]    = {}
            state["atr_1h"] = 0.0
    except Exception as e:
        log.error("_load_1h: %s", e)
        state["d1h"]    = {}
        state["atr_1h"] = 0.0
    return state


def _finalize(state: SignalAgentState) -> SignalAgentState:
    try:
        risk    = state["risk_result"]
        sizing  = state["sizing_result"]
        regime  = state["regime_result"]
        coin    = state["coin"]
        direction = state["direction"]
        grade   = state["grade"]
        score   = state["score"]
        session = state["session"]

        state["final_result"] = {
            "signal":    True,
            "coin":      coin,
            "direction": direction,
            "grade":     grade,
            "score":     score,
            "entry":     risk.entry,
            "sl":        risk.sl,
            "tp1":       risk.tp1,
            "tp2":       risk.tp2,
            "sl_pct":    risk.sl_pct,
            "sl_dist":   risk.sl_dist,
            "rr1":       risk.rr1,
            "rr2":       risk.rr2,
            "risk_amt":  sizing.risk_amt,
            "pos_size":  sizing.position_size,
            "stake":     sizing.stake,
            "leverage":  sizing.leverage,
            "risk_pct":  sizing.risk_pct,
            "regime":    regime.label,
            "session":   session,
            "trace": {
                "steps":     state.get("trace_steps", []),
                "direction": direction,
                "grade":     grade,
                "score":     score,
            },
        }

        state["signal"] = True

        log.info(
            "Signal finalized: %s %s grade:%s score:%.1f regime:%s",
            coin, direction, grade, score, regime.label,
        )

    except Exception as e:
        log.error("_finalize %s: %s", state.get("coin"), e)
        state["signal"] = False
        state["reason"] = f"finalize_error:{e}"

    return state


def _reject(state: SignalAgentState) -> SignalAgentState:
    state["signal"] = False
    state["final_result"] = {
        "signal":    False,
        "coin":      state.get("coin", ""),
        "direction": state.get("direction", "NEUTRAL"),
        "grade":     state.get("grade", "F"),
        "score":     0,
        "reason":    state.get("reason", "unknown"),
        "trace": {
            "steps":     state.get("trace_steps", []),
            "direction": state.get("direction", "NEUTRAL"),
            "grade":     state.get("grade", "F"),
            "score":     0,
        },
    }
    return state


def build_signal_graph() -> StateGraph:
    graph = StateGraph(SignalAgentState)

    graph.add_node("set_session", _set_session)
    graph.add_node("load_1h",     _load_1h)
    graph.add_node("regime",      regime_node)
    graph.add_node("trend",       trend_node)
    graph.add_node("grade",       grade_node)
    graph.add_node("risk",        risk_node)
    graph.add_node("sizing",      sizing_node)
    graph.add_node("finalize",    _finalize)
    graph.add_node("reject",      _reject)

    graph.set_entry_point("set_session")

    graph.add_edge("set_session", "load_1h")
    graph.add_edge("load_1h",     "regime")
    graph.add_edge("regime",      "trend")

    graph.add_conditional_edges(
        "trend",
        _after_trend,
        {"continue": "grade", "end": "reject"},
    )
    graph.add_conditional_edges(
        "grade",
        _after_grade,
        {"continue": "risk", "end": "reject"},
    )
    graph.add_conditional_edges(
        "risk",
        _after_risk,
        {"continue": "sizing", "end": "reject"},
    )
    graph.add_conditional_edges(
        "sizing",
        _after_sizing,
        {"continue": "finalize", "end": "reject"},
    )

    graph.add_edge("finalize", END)
    graph.add_edge("reject",   END)

    return graph


_compiled_graph = None


def get_signal_graph():
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph
    graph           = build_signal_graph()
    _compiled_graph = graph.compile()
    log.info("Signal graph compiled — 5-node pipeline active")
    return _compiled_graph