import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def sizing_node(state: SignalAgentState) -> SignalAgentState:
    try:
        from engines.sizing.adaptive import calculate

        risk      = state["risk_result"]
        regime    = state["regime_result"]
        direction = state["direction"]
        grade     = state["grade"]
        balance   = state["balance"]
        session   = state["session"]

        sizing = calculate(
            balance     = balance,
            sl_pct      = risk.sl_pct,
            sl_dist     = risk.sl_dist,
            grade       = grade,
            direction   = direction,
            regime_mult = regime.size_mult,
            session     = session,
        )

        if sizing.skip:
            state["signal"] = False
            state["reason"] = sizing.reason
            state["trace_steps"].append({
                "node":   "sizing",
                "passed": False,
                "reason": sizing.reason,
            })
            return state

        state["sizing_result"] = sizing

        state["trace_steps"].append({
            "node":     "sizing",
            "passed":   True,
            "stake":    sizing.stake,
            "leverage": sizing.leverage,
            "risk_pct": sizing.risk_pct,
            "risk_amt": sizing.risk_amt,
        })

    except Exception as e:
        log.error("sizing_node: %s", e)
        state["signal"] = False
        state["reason"] = f"sizing_error:{e}"

    return state