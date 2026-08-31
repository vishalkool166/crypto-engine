import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def grade_node(state: SignalAgentState) -> SignalAgentState:
    try:
        from engines.scoring.scorer import score, get_session

        d4h       = state["d4h"]
        d1h       = state["d1h"]
        direction = state["direction"]
        regime    = state["regime_result"]

        adx       = float(d4h.get("adx")       or 0)
        vol_ratio = float(d4h.get("vol_ratio") or 1.0)
        session   = get_session()

        rsi = float(d1h.get("rsi") or 0)
        if not rsi:
            rsi = float(d4h.get("rsi") or 50)

        state["session"] = session

        result = score(
            adx       = adx,
            rsi       = rsi,
            vol_ratio = vol_ratio,
            direction = direction,
            regime    = regime.label,
        )

        state["score"] = result.total
        state["grade"] = result.grade

        if result.grade == "F":
            state["signal"] = False
            state["reason"] = "grade_f"
            state["trace_steps"].append({
                "node":   "grade",
                "passed": False,
                "grade":  result.grade,
                "score":  result.total,
                "reason": "grade_f",
            })
            return state

        state["trace_steps"].append({
            "node":    "grade",
            "passed":  True,
            "grade":   result.grade,
            "score":   result.total,
            "adx_pts": result.adx_pts,
            "rsi_pts": result.rsi_pts,
            "vol_pts": result.vol_pts,
        })

    except Exception as e:
        log.error("grade_node: %s", e)
        state["signal"] = False
        state["reason"] = f"grade_error:{e}"

    return state