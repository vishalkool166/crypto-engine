import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def risk_node(state: SignalAgentState) -> SignalAgentState:
    coin       = state["coin"]
    direction  = state["direction"]
    d4h        = state["d4h"]
    d1h        = state["d1h"]
    atr_15m    = state["atr_15m"]
    ict_result = state["ict_result"]

    try:
        sweep = ict_result.sweep if ict_result else None
        zone  = ict_result.zone  if ict_result else None

        entry = float(ict_result.entry_price) if ict_result and ict_result.entry_price else 0.0

        if not entry:
            if zone:
                is_long = direction == "LONG"
                entry   = float(zone.top) if is_long else float(zone.bottom)
            else:
                entry = float(d4h.get("price") or 0)

        from engines.risk.calculator import calculate
        risk_result = calculate(
            direction = direction,
            entry     = entry,
            sweep     = sweep,
            zone      = zone,
            ict       = ict_result.trigger if ict_result else None,
            atr_15m   = atr_15m,
            d1h       = d1h,
            d4h       = d4h,
        )

        state["risk_result"] = risk_result

        passed = risk_result.valid

        state["trace_steps"].append({
            "node":      "risk",
            "passed":    passed,
            "entry":     risk_result.entry,
            "sl":        risk_result.sl,
            "tp1":       risk_result.tp1,
            "tp2":       risk_result.tp2,
            "sl_pct":    risk_result.sl_pct,
            "rr1":       risk_result.rr1,
            "rr2":       risk_result.rr2,
            "sl_reason": risk_result.sl_reason,
            "reason":    risk_result.reason if not passed else "",
        })

        if not passed:
            state["signal"] = False
            state["reason"] = f"risk_invalid:{risk_result.reason}"

            from data.rejection_stats import record_scan
            record_scan(coin, direction, f"risk_{risk_result.reason}")

        log.debug(
            "risk_node %s — passed:%s entry:%.6f sl:%.6f tp1:%.6f rr1:%.2f",
            coin, passed,
            risk_result.entry,
            risk_result.sl,
            risk_result.tp1,
            risk_result.rr1,
        )

    except Exception as e:
        log.error("risk_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"risk_node_error:{e}"
        state["trace_steps"].append({
            "node":   "risk",
            "passed": False,
            "reason": str(e),
        })

    return state