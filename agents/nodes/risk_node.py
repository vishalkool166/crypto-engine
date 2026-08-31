import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def risk_node(state: SignalAgentState) -> SignalAgentState:
    try:
        from engines.risk.calculator import calculate

        d4h       = state["d4h"]
        direction = state["direction"]

        price       = float(d4h.get("price")      or 0)
        atr         = float(d4h.get("atr")        or 0)
        swing_high  = float(d4h.get("swing_high") or 0)
        swing_low   = float(d4h.get("swing_low")  or 0)

        if not price or not atr:
            state["signal"] = False
            state["reason"] = "missing_price_or_atr"
            return state

        swing_level = swing_low if direction == "LONG" else swing_high

        if not swing_level:
            state["signal"] = False
            state["reason"] = "missing_swing_level"
            return state

        risk = calculate(
            direction   = direction,
            entry       = price,
            swing_level = swing_level,
            atr         = atr,
        )

        if not risk.valid:
            state["signal"] = False
            state["reason"] = risk.reason
            state["trace_steps"].append({
                "node":   "risk",
                "passed": False,
                "reason": risk.reason,
            })
            return state

        state["risk_result"] = risk

        state["trace_steps"].append({
            "node":   "risk",
            "passed": True,
            "entry":  risk.entry,
            "sl":     risk.sl,
            "tp1":    risk.tp1,
            "sl_pct": risk.sl_pct,
            "rr1":    risk.rr1,
        })

    except Exception as e:
        log.error("risk_node: %s", e)
        state["signal"] = False
        state["reason"] = f"risk_error:{e}"

    return state