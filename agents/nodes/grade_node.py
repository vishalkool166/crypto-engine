import logging
from agents.state import SignalAgentState

log = logging.getLogger(__name__)


def grade_node(state: SignalAgentState) -> SignalAgentState:
    coin          = state["coin"]
    direction     = state["direction"]
    regime_result = state["regime_result"]
    trend_result  = state["trend_result"]
    reversion     = state["reversion_result"]
    ict_result    = state["ict_result"]
    session       = state["session"]

    try:
        from engines.scoring.scorer import build_score, assign_grade
        hs = build_score(
            coin          = coin,
            direction     = direction,
            regime_result = regime_result,
            trend_result  = trend_result,
            reversion     = reversion,
            ict_result    = ict_result,
            session       = session,
        )

        pct   = hs.pct()
        grade = assign_grade(pct, regime_result.label if regime_result else "default")

        state["score"] = pct
        state["grade"] = grade

        passed = grade != "F"

        state["trace_steps"].append({
            "node":       "grade",
            "passed":     passed,
            "grade":      grade,
            "score":      pct,
            "regime":     regime_result.label if regime_result else "",
            "session":    session,
            "components": hs.to_dict()["components"],
            "reason":     "" if passed else f"grade_F_score:{pct:.1f}",
        })

        if not passed:
            state["signal"] = False
            state["reason"] = f"grade_F:{pct:.1f}"

            from data.rejection_stats import record_scan
            record_scan(coin, direction, "combined_score_low")

        log.debug(
            "grade_node %s — grade:%s score:%.1f regime:%s session:%s",
            coin, grade, pct,
            regime_result.label if regime_result else "",
            session,
        )

    except Exception as e:
        log.error("grade_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"grade_node_error:{e}"
        state["trace_steps"].append({
            "node":   "grade",
            "passed": False,
            "reason": str(e),
        })

    return state