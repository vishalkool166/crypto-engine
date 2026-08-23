import logging
from langgraph.graph import StateGraph, END
from agents.state import SignalAgentState
from agents.nodes.context_node import context_node
from agents.nodes.sweep_node   import sweep_node
from agents.nodes.zone_node    import zone_node
from agents.nodes.trigger_node import trigger_node
from agents.nodes.risk_node    import risk_node
from agents.nodes.grade_node   import grade_node
from agents.nodes.ml_node      import ml_node

log = logging.getLogger(__name__)


def _after_context(state: SignalAgentState) -> str:
    ctx = state.get("ctx", {})
    if not ctx.get("pass", False):
        return "end"
    return "continue"


def _after_sweep(state: SignalAgentState) -> str:
    sweep = state.get("sweep_result", {})
    from config import cfg
    if not sweep.get("detected", False):
        return "end"
    if sweep.get("score", 0) < cfg.SCALP_ENGINE["sweep_min_score"]:
        return "end"
    return "continue"


def _after_zone(state: SignalAgentState) -> str:
    zone = state.get("zone_result", {})
    from config import cfg
    if not zone.get("detected", False):
        return "end"
    if zone.get("score", 0) < cfg.SCALP_ENGINE["zone_min_score"]:
        return "end"
    return "continue"


def _after_trigger(state: SignalAgentState) -> str:
    trigger = state.get("trigger_result", {})
    if not trigger.get("confirmed", False):
        return "end"
    return "continue"


def _after_risk(state: SignalAgentState) -> str:
    risk = state.get("risk_result", {})
    if not risk.get("valid", False):
        return "end"
    return "continue"


def _after_grader(state: SignalAgentState) -> str:
    grade = state.get("grade", "F")
    if grade == "F":
        return "end"
    return "continue"


def _after_ml(state: SignalAgentState) -> str:
    if not state.get("signal", True):
        return "end"
    return "continue"


def _finalize_signal(state: SignalAgentState) -> SignalAgentState:
    try:
        sweep_result   = state.get("sweep_result",   {})
        zone_result    = state.get("zone_result",    {})
        trigger_result = state.get("trigger_result", {})
        risk_result    = state.get("risk_result",    {})

        combined = round(
            sweep_result.get("score",   0) * 0.40 +
            zone_result.get("score",    0) * 0.35 +
            trigger_result.get("score", 0) * 0.25,
            3,
        )

        from engines.narrative import build as build_narrative
        from engines.sizing import calculate as calculate_sizing

        sizing_result = calculate_sizing(
            balance        = state["balance"],
            sl_pct         = risk_result.get("sl_pct",  0),
            sl_dist        = risk_result.get("sl_dist", 0),
            grade          = state["grade"],
            direction      = state["direction"],
            ml_probability = state.get("ml_probability"),
            alignment      = state.get("ctx", {}).get("alignment"),
        )

        if sizing_result.get("skip"):
            state["signal"] = False
            state["reason"] = sizing_result.get("reason", "sizing_skip")
            state["trace_steps"].append({
                "node":   "finalize",
                "passed": False,
                "reason": sizing_result.get("reason", "sizing_skip"),
            })
            return state

        narrative = build_narrative(
            coin      = state["coin"],
            direction = state["direction"],
            grade     = state["grade"],
            context   = state.get("ctx", {}),
            sweep     = sweep_result,
            zone      = zone_result.get("zone", {}),
            trigger   = trigger_result,
            risk      = risk_result,
            sizing    = sizing_result,
        )

        state["sizing_result"] = sizing_result
        state["signal"]        = True

        ctx = state.get("ctx", {})

        state["final_result"] = {
            "signal":         True,
            "coin":           state["coin"],
            "direction":      state["direction"],
            "grade":          state["grade"],
            "score":          combined,
            "score_pct":      state["score"],
            "entry":          trigger_result.get("entry_price", 0),
            "sl":             risk_result.get("sl",   0),
            "tp1":            risk_result.get("tp1",  0),
            "tp2":            risk_result.get("tp2"),
            "sl_pct":         risk_result.get("sl_pct",  0),
            "sl_dist":        risk_result.get("sl_dist", 0),
            "rr1":            risk_result.get("rr1",  0),
            "rr2":            risk_result.get("rr2"),
            "tp1_label":      risk_result.get("tp1_label", ""),
            "tp2_label":      risk_result.get("tp2_label", ""),
            "sl_reason":      risk_result.get("sl_reason", ""),
            "risk_amt":       sizing_result.get("risk_amt",      0),
            "pos_size":       sizing_result.get("position_size", 0),
            "stake":          sizing_result.get("stake",         0),
            "leverage":       sizing_result.get("leverage",      0),
            "risk_pct":       sizing_result.get("risk_pct",      0),
            "sweep_score":    sweep_result.get("score",          0),
            "zone_score":     zone_result.get("score",           0),
            "trigger_score":  trigger_result.get("score",        0),
            "sweep":          sweep_result.get("sweep"),
            "zone":           zone_result.get("zone"),
            "sweep_found":    True,
            "zone_found":     True,
            "narrative":      narrative,
            "signal_type":    "FULL",
            "atr_4h":         state.get("atr_4h",  0),
            "atr_1h":         state.get("atr_1h",  0),
            "atr_15m":        state.get("atr_15m", 0),
            "ml_probability": state.get("ml_probability"),
            "regime":         state.get("regime",  ""),
            "session":        state.get("session", ""),
            "alignment":      ctx.get("alignment"),
            "btc_score":      ctx.get("btc_score",     0),
            "htf_score":      ctx.get("htf_score",     0),
            "context_score":  ctx.get("context_score", 0),
            "trace": {
                "steps":     state.get("trace_steps", []),
                "direction": state["direction"],
                "grade":     state["grade"],
                "score":     combined,
            },
        }

        state["trace_steps"].append({
            "node":     "finalize",
            "passed":   True,
            "grade":    state["grade"],
            "score":    combined,
            "stake":    sizing_result.get("stake",    0),
            "leverage": sizing_result.get("leverage", 0),
        })

        log.info(
            "Signal finalized: %s %s grade:%s score:%.3f btc_score:%.1f",
            state["coin"], state["direction"],
            state["grade"], combined,
            ctx.get("btc_score", 0),
        )

    except Exception as e:
        log.error("_finalize_signal %s: %s", state["coin"], e)
        state["signal"] = False
        state["reason"] = f"finalize_error: {e}"

    return state


def _build_rejection_result(state: SignalAgentState) -> SignalAgentState:
    state["signal"] = False
    state["final_result"] = {
        "signal":      False,
        "coin":        state["coin"],
        "direction":   state.get("direction", "NEUTRAL"),
        "grade":       state.get("grade",     "F"),
        "score":       0,
        "reason":      state.get("reason",    "unknown"),
        "sweep_found": bool(state.get("sweep_result", {}).get("detected")),
        "zone_found":  bool(state.get("zone_result",  {}).get("detected")),
        "sweep_score": state.get("sweep_result", {}).get("score", 0),
        "zone_score":  state.get("zone_result",  {}).get("score", 0),
        "sweep":       state.get("sweep_result", {}).get("sweep"),
        "zone":        state.get("zone_result",  {}).get("zone"),
        "direction_raw": state.get("direction", "NEUTRAL"),
        "trace": {
            "steps":     state.get("trace_steps", []),
            "direction": state.get("direction",   "NEUTRAL"),
            "grade":     state.get("grade",       "F"),
            "score":     0,
        },
    }
    return state


def build_signal_graph() -> StateGraph:
    graph = StateGraph(SignalAgentState)

    graph.add_node("context",  context_node)
    graph.add_node("sweep",    sweep_node)
    graph.add_node("zone",     zone_node)
    graph.add_node("trigger",  trigger_node)
    graph.add_node("risk",     risk_node)
    graph.add_node("grader",   grade_node)
    graph.add_node("ml",       ml_node)
    graph.add_node("finalize", _finalize_signal)
    graph.add_node("reject",   _build_rejection_result)

    graph.set_entry_point("context")

    graph.add_conditional_edges(
        "context",
        _after_context,
        {"continue": "sweep", "end": "reject"},
    )
    graph.add_conditional_edges(
        "sweep",
        _after_sweep,
        {"continue": "zone", "end": "reject"},
    )
    graph.add_conditional_edges(
        "zone",
        _after_zone,
        {"continue": "trigger", "end": "reject"},
    )
    graph.add_conditional_edges(
        "trigger",
        _after_trigger,
        {"continue": "risk", "end": "reject"},
    )
    graph.add_conditional_edges(
        "risk",
        _after_risk,
        {"continue": "grader", "end": "reject"},
    )
    graph.add_conditional_edges(
        "grader",
        _after_grader,
        {"continue": "ml", "end": "reject"},
    )
    graph.add_conditional_edges(
        "ml",
        _after_ml,
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
    log.info("LangGraph signal graph compiled")
    return _compiled_graph