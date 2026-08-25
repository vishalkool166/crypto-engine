import logging
from langgraph.graph import StateGraph, END
from agents.state import SignalAgentState
from agents.nodes.regime_node    import regime_node
from agents.nodes.trend_node     import trend_node
from agents.nodes.reversion_node import reversion_node
from agents.nodes.ict_node       import ict_node
from agents.nodes.risk_node      import risk_node
from agents.nodes.sizing_node    import sizing_node
from agents.nodes.grade_node     import grade_node
from agents.nodes.ml_node        import ml_node

log = logging.getLogger(__name__)


def _after_trend(state: SignalAgentState) -> str:
    if not state.get("signal", True):
        return "end"
    return "continue"


def _after_reversion(state: SignalAgentState) -> str:
    if not state.get("signal", True):
        return "end"
    return "continue"


def _after_ict(state: SignalAgentState) -> str:
    if not state.get("signal", True):
        return "end"
    return "continue"


def _after_risk(state: SignalAgentState) -> str:
    if not state.get("signal", True):
        return "end"
    return "continue"


def _after_grader(state: SignalAgentState) -> str:
    if not state.get("signal", True):
        return "end"
    if state.get("grade", "F") == "F":
        return "end"
    return "continue"


def _after_ml(state: SignalAgentState) -> str:
    if not state.get("signal", True):
        return "end"
    return "continue"


def _after_sizing(state: SignalAgentState) -> str:
    if not state.get("signal", True):
        return "end"
    return "continue"


def _set_session(state: SignalAgentState) -> SignalAgentState:
    from engines.scoring.scorer import get_session
    state["session"] = get_session()
    return state


def _finalize(state: SignalAgentState) -> SignalAgentState:
    try:
        ict_result    = state["ict_result"]
        risk_result   = state["risk_result"]
        sizing_result = state["sizing_result"]
        regime_result = state["regime_result"]
        trend_result  = state["trend_result"]
        reversion     = state["reversion_result"]
        coin          = state["coin"]
        direction     = state["direction"]
        grade         = state["grade"]
        session       = state["session"]

        from engines.narrative.builder import build
        narrative = build(
            coin          = coin,
            direction     = direction,
            grade         = grade,
            regime_result = regime_result,
            trend_result  = trend_result,
            reversion     = reversion,
            ict_result    = ict_result,
            risk_result   = risk_result,
            sizing_result = sizing_result,
            session       = session,
        )

        sweep = ict_result.sweep
        zone  = ict_result.zone

        sweep_dict = None
        if sweep:
            sweep_dict = {
                "type":        sweep.type,
                "label":       sweep.label,
                "level":       sweep.level,
                "sweep_low":   sweep.sweep_low,
                "sweep_high":  sweep.sweep_high,
                "wick_atr":    sweep.wick_atr,
                "vol_ratio":   sweep.vol_ratio,
                "intensity":   sweep.intensity,
                "confirmed":   sweep.confirmed,
                "age_hours":   sweep.age_hours,
                "level_label": sweep.label,
            }

        zone_dict = None
        if zone:
            zone_dict = {
                "type":         zone.type,
                "top":          zone.top,
                "bottom":       zone.bottom,
                "mid":          zone.mid,
                "touch_count":  zone.touch_count,
                "in_zone":      zone.in_zone,
                "score":        zone.score,
                "distance_pct": zone.distance_pct,
                "origin_desc":  zone.origin_desc,
                "strength":     zone.strength,
                "timeframe":    zone.timeframe,
            }

        alignment_dict = None
        if trend_result:
            alignment_dict = {
                "daily":     trend_result.daily_bias,
                "weekly":    trend_result.weekly_bias,
                "alignment": trend_result.alignment,
                "size_mult": trend_result.size_mult,
            }

        state["final_result"] = {
            "signal":         True,
            "coin":           coin,
            "direction":      direction,
            "grade":          grade,
            "score":          ict_result.score,
            "score_pct":      state["score"],
            "entry":          risk_result.entry,
            "sl":             risk_result.sl,
            "tp1":            risk_result.tp1,
            "tp2":            risk_result.tp2,
            "sl_pct":         risk_result.sl_pct,
            "sl_dist":        risk_result.sl_dist,
            "rr1":            risk_result.rr1,
            "rr2":            risk_result.rr2,
            "tp1_label":      risk_result.tp1_label,
            "tp2_label":      risk_result.tp2_label,
            "sl_reason":      risk_result.sl_reason,
            "risk_amt":       sizing_result.risk_amt,
            "pos_size":       sizing_result.position_size,
            "stake":          sizing_result.stake,
            "leverage":       sizing_result.leverage,
            "risk_pct":       sizing_result.risk_pct,
            "tp1_pct":        0.65,
            "tp2_pct":        0.35,
            "sweep_score":    ict_result.sweep_score,
            "zone_score":     ict_result.zone_score,
            "trigger_score":  ict_result.trigger_score,
            "sweep":          sweep_dict,
            "zone":           zone_dict,
            "sweep_found":    True,
            "zone_found":     True,
            "narrative":      narrative,
            "signal_type":    "FULL",
            "atr_4h":         state.get("atr_4h",  0.0),
            "atr_1h":         state.get("atr_1h",  0.0),
            "atr_15m":        state.get("atr_15m", 0.0),
            "ml_probability": state.get("ml_probability"),
            "regime":         regime_result.label if regime_result else "",
            "regime_mult":    regime_result.size_mult if regime_result else 1.0,
            "session":        session,
            "alignment":      alignment_dict,
            "btc_score":      trend_result.btc_score     if trend_result else 0.0,
            "htf_score":      trend_result.htf_score     if trend_result else 0.0,
            "context_score":  trend_result.context_score if trend_result else 0.0,
            "drawdown_pct":   sizing_result.drawdown_pct,
            "win_rate":       sizing_result.win_rate,
            "streak":         sizing_result.streak,
            "streak_type":    sizing_result.streak_type,
            "today_pnl":      sizing_result.today_pnl,
            "open_trades":    sizing_result.open_trades,
            "trace": {
                "steps":     state.get("trace_steps", []),
                "direction": direction,
                "grade":     grade,
                "score":     ict_result.score,
            },
        }

        state["signal"] = True

        state["trace_steps"].append({
            "node":     "finalize",
            "passed":   True,
            "grade":    grade,
            "score":    ict_result.score,
            "stake":    sizing_result.stake,
            "leverage": sizing_result.leverage,
        })

        log.info(
            "Signal finalized: %s %s grade:%s score:%.3f regime:%s session:%s",
            coin, direction, grade, ict_result.score,
            regime_result.label if regime_result else "",
            session,
        )

    except Exception as e:
        log.error("_finalize %s: %s", state.get("coin"), e)
        state["signal"] = False
        state["reason"] = f"finalize_error:{e}"

    return state


def _reject(state: SignalAgentState) -> SignalAgentState:
    state["signal"] = False

    ict_result = state.get("ict_result")
    sweep_dict = None
    zone_dict  = None

    if ict_result:
        sweep = ict_result.sweep
        zone  = ict_result.zone
        if sweep:
            sweep_dict = {
                "type":      sweep.type,
                "label":     sweep.label,
                "level":     sweep.level,
                "age_hours": sweep.age_hours,
                "score":     ict_result.sweep_score,
            }
        if zone:
            zone_dict = {
                "type":   zone.type,
                "top":    zone.top,
                "bottom": zone.bottom,
                "score":  ict_result.zone_score,
            }

    state["final_result"] = {
        "signal":      False,
        "coin":        state.get("coin", ""),
        "direction":   state.get("direction", "NEUTRAL"),
        "grade":       state.get("grade", "F"),
        "score":       0,
        "reason":      state.get("reason", "unknown"),
        "sweep_found": bool(ict_result and ict_result.sweep_score > 0) if ict_result else False,
        "zone_found":  bool(ict_result and ict_result.zone_score  > 0) if ict_result else False,
        "sweep_score": ict_result.sweep_score  if ict_result else 0.0,
        "zone_score":  ict_result.zone_score   if ict_result else 0.0,
        "sweep":       sweep_dict,
        "zone":        zone_dict,
        "regime":      state.get("regime_label", ""),
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

    graph.add_node("set_session", _set_session)
    graph.add_node("regime",      regime_node)
    graph.add_node("trend",       trend_node)
    graph.add_node("reversion",   reversion_node)
    graph.add_node("ict",         ict_node)
    graph.add_node("risk",        risk_node)
    graph.add_node("grader",      grade_node)
    graph.add_node("ml",          ml_node)
    graph.add_node("sizing",      sizing_node)
    graph.add_node("finalize",    _finalize)
    graph.add_node("reject",      _reject)

    graph.set_entry_point("set_session")

    graph.add_edge("set_session", "regime")
    graph.add_edge("regime",      "trend")

    graph.add_conditional_edges(
        "trend",
        _after_trend,
        {"continue": "reversion", "end": "reject"},
    )
    graph.add_conditional_edges(
        "reversion",
        _after_reversion,
        {"continue": "ict", "end": "reject"},
    )
    graph.add_conditional_edges(
        "ict",
        _after_ict,
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
    log.info("Hybrid signal graph compiled — 5-layer pipeline active")
    return _compiled_graph