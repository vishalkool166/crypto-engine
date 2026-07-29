import logging
from datetime import datetime, timezone
from agents.state import SignalAgentState
from engines.scorer import (
    SignalScore,
    assign_grade,
    score_session,
    SCORE_WEIGHTS,
    score_btc_context,
    score_htf_alignment,
)

log = logging.getLogger(__name__)


def _get_session() -> str:
    hour = datetime.now(timezone.utc).hour
    if 8  <= hour < 13: return "London"
    if 13 <= hour < 17: return "London/NY Overlap"
    if 17 <= hour < 21: return "New York"
    if 0  <= hour < 8:  return "Asia"
    return "Off Hours"


def _get_regime(d4h: dict) -> str:
    trend = d4h.get("trend", {})
    cls   = trend.get("cls", "neutral")
    adx   = float(d4h.get("adx") or 0)
    if cls == "bull" and adx >= 25:
        return "trending"
    if cls == "bear" and adx >= 25:
        return "trending"
    if adx < 20:
        return "choppy"
    return "ranging"


def grade_node(state: SignalAgentState) -> SignalAgentState:
    coin           = state["coin"]
    direction      = state["direction"]
    d4h            = state["d4h"]
    ctx            = state["ctx"]
    sweep_result   = state["sweep_result"]
    zone_result    = state["zone_result"]
    trigger_result = state["trigger_result"]

    try:
        session = _get_session()
        regime  = _get_regime(d4h)
        state["session"] = session
        state["regime"]  = regime

        sig_score           = SignalScore()
        sig_score.coin      = coin
        sig_score.direction = direction

        btc_score = ctx.get("btc_score", 0)
        htf_score = ctx.get("htf_score", 0)

        sig_score.add(
            "btc_context",
            btc_score,
            SCORE_WEIGHTS["btc_context"]["max"],
            True,
            ctx.get("trace", {}).get("btc", ""),
        )
        sig_score.add(
            "htf_alignment",
            htf_score,
            SCORE_WEIGHTS["htf_alignment"]["max"],
            True,
            ctx.get("trace", {}).get("htf", ""),
        )
        sig_score.add(
            "sweep",
            sweep_result["score"] * SCORE_WEIGHTS["sweep"]["max"],
            SCORE_WEIGHTS["sweep"]["max"],
            True,
            sweep_result.get("desc", ""),
        )
        sig_score.add(
            "zone",
            zone_result["score"] * SCORE_WEIGHTS["zone"]["max"],
            SCORE_WEIGHTS["zone"]["max"],
            True,
            zone_result.get("zone", {}).get("origin_desc", "") if zone_result.get("zone") else "",
        )
        sig_score.add(
            "trigger",
            trigger_result["score"] * SCORE_WEIGHTS["trigger"]["max"],
            SCORE_WEIGHTS["trigger"]["max"],
            True,
            trigger_result.get("pattern", ""),
        )

        session_score, session_reason = score_session(session)
        sig_score.add(
            "session",
            session_score,
            SCORE_WEIGHTS["session"]["max"],
            True,
            session_reason,
        )

        context_score = ctx.get("context_score", 0)
        sig_score.total = round(sig_score.total + context_score, 3)

        pct   = sig_score.pct()
        grade = assign_grade(pct, regime)

        state["score"] = pct
        state["grade"] = grade

        step = {
            "node":          "grade",
            "passed":        grade not in ("F",),
            "grade":         grade,
            "score":         pct,
            "regime":        regime,
            "session":       session,
            "btc_score":     btc_score,
            "htf_score":     htf_score,
            "sweep_contrib": round(sweep_result["score"]   * SCORE_WEIGHTS["sweep"]["max"],   2),
            "zone_contrib":  round(zone_result["score"]    * SCORE_WEIGHTS["zone"]["max"],    2),
            "trig_contrib":  round(trigger_result["score"] * SCORE_WEIGHTS["trigger"]["max"], 2),
            "session_score": session_score,
            "reason":        "" if grade != "F" else f"score_too_low:{pct:.1f}",
        }
        state["trace_steps"].append(step)

        if grade == "F":
            state["signal"] = False
            state["reason"] = f"grade_F_score:{pct:.1f}"

        log.debug(
            "grade_node %s — grade:%s score:%.1f regime:%s session:%s",
            coin, grade, pct, regime, session
        )

    except Exception as e:
        log.error("grade_node %s: %s", coin, e)
        state["signal"] = False
        state["reason"] = f"grade_node_error: {e}"
        state["trace_steps"].append({
            "node":   "grade",
            "passed": False,
            "reason": str(e),
        })

    return state