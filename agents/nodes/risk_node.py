import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def risk_node(state: SignalAgentState) -> SignalAgentState:
    coin           = state["coin"]
    direction      = state["direction"]
    d4h            = state["d4h"]
    d1h            = state["d1h"]
    atr_15m        = state["atr_15m"]
    sweep_result   = state["sweep_result"]
    zone_result    = state["zone_result"]
    trigger_result = state["trigger_result"]

    try:
        sweep_data = sweep_result.get("sweep") or {}
        zone_data  = zone_result.get("zone")   or {}
        entry      = trigger_result.get("entry_price") or d4h.get("price", 0)

        from engines.risk import calculate
        risk_result = calculate(
            direction = direction,
            entry     = entry,
            sweep     = sweep_data,
            zone      = zone_data,
            trigger   = trigger_result,
            atr_15m   = atr_15m,
            d1h       = d1h,
            d4h       = d4h,
        )
        state["risk_result"] = risk_result

        passed = risk_result["valid"]

        step = {
            "node":      "risk",
            "passed":    passed,
            "valid":     risk_result["valid"],
            "sl":        risk_result.get("sl",      0),
            "tp1":       risk_result.get("tp1",     0),
            "tp2":       risk_result.get("tp2"),
            "sl_pct":    risk_result.get("sl_pct",  0),
            "rr1":       risk_result.get("rr1",     0),
            "rr2":       risk_result.get("rr2"),
            "sl_reason": risk_result.get("sl_reason", ""),
            "reason":    risk_result.get("reason",  "") if not passed else "",
        }
        state["trace_steps"].append(step)

        if not passed:
            state["signal"] = False
            state["reason"] = f"risk_invalid:{risk_result.get('reason', '')}"

        log.debug(
            "risk_node %s — passed:%s sl:%.6f tp1:%.6f rr1:%.2f",
            coin, passed,
            risk_result.get("sl",  0),
            risk_result.get("tp1", 0),
            risk_result.get("rr1", 0),
        )

    except Exception as e:
        log.error("risk_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"risk_node_error: {e}"
        state["trace_steps"].append({
            "node":   "risk",
            "passed": False,
            "reason": str(e),
        })

    return state