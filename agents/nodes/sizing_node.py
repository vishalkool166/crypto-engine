import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def sizing_node(state: SignalAgentState) -> SignalAgentState:
    coin          = state["coin"]
    direction     = state["direction"]
    grade         = state["grade"]
    risk_result   = state["risk_result"]
    regime_result = state["regime_result"]
    trend_result  = state["trend_result"]
    session       = state["session"]
    ml_prob       = state.get("ml_probability")

    try:
        alignment_mult = float(trend_result.size_mult) if trend_result else 1.0
        regime_mult    = float(regime_result.size_mult) if regime_result else 1.0

        from engines.sizing.adaptive import calculate
        sizing_result = calculate(
            balance        = state["balance"],
            sl_pct         = float(risk_result.sl_pct),
            sl_dist        = float(risk_result.sl_dist),
            grade          = grade,
            direction      = direction,
            regime_mult    = regime_mult,
            ml_probability = ml_prob,
            alignment_mult = alignment_mult,
            session        = session,
        )

        state["sizing_result"] = sizing_result

        passed = not sizing_result.skip

        state["trace_steps"].append({
            "node":           "sizing",
            "passed":         passed,
            "skip":           sizing_result.skip,
            "risk_pct":       sizing_result.risk_pct,
            "risk_amt":       sizing_result.risk_amt,
            "stake":          sizing_result.stake,
            "leverage":       sizing_result.leverage,
            "regime_mult":    sizing_result.regime_mult,
            "alignment_mult": sizing_result.alignment_mult,
            "session_mult":   sizing_result.session_mult,
            "reason":         sizing_result.reason if not passed else "",
        })

        if not passed:
            state["signal"] = False
            state["reason"] = sizing_result.reason

            from data.rejection_stats import record_scan
            record_scan(coin, direction, sizing_result.reason or "sizing_skip")

        log.debug(
            "sizing_node %s — passed:%s stake:%.2f lev:%dx risk_pct:%.3f",
            coin, passed,
            sizing_result.stake,
            sizing_result.leverage,
            sizing_result.risk_pct,
        )

    except Exception as e:
        log.error("sizing_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"sizing_node_error:{e}"
        state["trace_steps"].append({
            "node":   "sizing",
            "passed": False,
            "reason": str(e),
        })

    return state