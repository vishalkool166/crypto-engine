from database import SessionLocal, Trade, Signal as SignalModel
from engines.confluence import score_confluence
from data.store import load_candles
from engines.indicators import calculate_all
import logging

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# FACTOR ANALYSIS
# Observes which confluence factors were present
# on winning vs losing trades.
# No optimization — pure observation.
# Requires 200+ trades for meaningful results.
# ═══════════════════════════════════════════════════════

FACTOR_KEYS = [
    "liquidity_sweep",
    "retest_confirmation",
    "displacement",
    "market_regime",
    "weekly_filter",
    "market_structure",
    "session_timing",
    "btc_alignment",
    "oi_behavior",
    "volume_expansion",
    "funding_extreme",
    "rsi_divergence",
    "atr_volatility",
    "rsi_context",
    "macd_histogram",
    "order_blocks"
]


def run_factor_analysis() -> dict:
    """
    Reads all closed trades from DB.
    For each trade reads its linked signal's
    factor scores.
    Builds win/loss breakdown per factor.
    Returns observation table — no changes made.
    """
    db = SessionLocal()
    try:
        trades = db.query(Trade).filter(
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss"])
        ).all()

        if not trades:
            return {
                "error":       "No closed trades yet",
                "total":       0,
                "min_required": 200
            }

        total  = len(trades)
        wins   = [t for t in trades if t.outcome == "win"]
        losses = [t for t in trades if t.outcome == "loss"]

        log.info(
            f"Factor analysis: "
            f"{total} trades — "
            f"{len(wins)}W {len(losses)}L"
        )

        # Per-factor counters
        factor_stats = {
            key: {
                "win_present":  0,
                "win_absent":   0,
                "loss_present": 0,
                "loss_absent":  0
            }
            for key in FACTOR_KEYS
        }

        # Grade counters
        grade_stats = {}

        for trade in trades:
            sig = None
            if trade.signal_id:
                sig = db.query(SignalModel).filter(
                    SignalModel.id == trade.signal_id
                ).first()

            grade = trade.grade or "?"
            if grade not in grade_stats:
                grade_stats[grade] = {"wins": 0, "losses": 0}

            if trade.outcome == "win":
                grade_stats[grade]["wins"] += 1
            else:
                grade_stats[grade]["losses"] += 1

            if not sig:
                continue

            # Use signal scores as proxy for factor presence
            # sweep_score >= 6 = sweep was present
            # retest_score >= 6 = retest was present
            # disp_score >= 6 = displacement was present
            factor_presence = _infer_factor_presence(sig)

            for key in FACTOR_KEYS:
                present = factor_presence.get(key, False)
                if trade.outcome == "win":
                    if present:
                        factor_stats[key]["win_present"]  += 1
                    else:
                        factor_stats[key]["win_absent"]   += 1
                else:
                    if present:
                        factor_stats[key]["loss_present"] += 1
                    else:
                        factor_stats[key]["loss_absent"]  += 1

        # Build observation table
        table = []
        for key in FACTOR_KEYS:
            s = factor_stats[key]

            present_total = s["win_present"] + s["loss_present"]
            absent_total  = s["win_absent"]  + s["loss_absent"]

            win_rate_present = round(
                s["win_present"] / present_total * 100, 1
            ) if present_total > 0 else None

            win_rate_absent = round(
                s["win_absent"] / absent_total * 100, 1
            ) if absent_total > 0 else None

            edge = None
            if win_rate_present is not None and win_rate_absent is not None:
                edge = round(win_rate_present - win_rate_absent, 1)

            table.append({
                "factor":            key,
                "present_total":     present_total,
                "absent_total":      absent_total,
                "win_rate_present":  win_rate_present,
                "win_rate_absent":   win_rate_absent,
                "edge":              edge,
                "observation": _observation(
                    edge, present_total, total
                )
            })

        # Sort by edge descending
        table.sort(
            key=lambda x: x["edge"] or -999,
            reverse=True
        )

        overall_wr = round(len(wins) / total * 100, 1)

        reliability = _reliability_note(total)

        return {
            "total":          total,
            "wins":           len(wins),
            "losses":         len(losses),
            "overall_wr":     overall_wr,
            "min_required":   200,
            "reliable":       total >= 200,
            "reliability":    reliability,
            "table":          table,
            "grade_stats":    _build_grade_stats(grade_stats),
            "top_factors":    [
                r for r in table
                if r["edge"] and r["edge"] > 10
            ][:5],
            "weak_factors":   [
                r for r in table
                if r["edge"] is not None and r["edge"] < 5
            ][:5]
        }

    except Exception as e:
        log.error(f"Factor analysis error: {e}")
        return {"error": str(e)}

    finally:
        db.close()


def _infer_factor_presence(sig) -> dict:
    """
    Infers factor presence from signal scores.
    Uses stored sweep/retest/disp scores as proxy.
    Not perfect — but sufficient for observation.
    """
    sweep_ok  = (sig.sweep_score  or 0) >= 6
    retest_ok = (sig.retest_score or 0) >= 6
    disp_ok   = (sig.disp_score   or 0) >= 6

    # Score-based inference for remaining factors
    score = sig.score or 0

    return {
        "liquidity_sweep":     sweep_ok,
        "retest_confirmation": retest_ok,
        "displacement":        disp_ok,
        "market_regime":       score >= 60,
        "weekly_filter":       score >= 65,
        "market_structure":    score >= 55,
        "session_timing":      score >= 50,
        "btc_alignment":       score >= 60,
        "oi_behavior":         score >= 55,
        "volume_expansion":    score >= 50,
        "funding_extreme":     score >= 45,
        "rsi_divergence":      score >= 70,
        "atr_volatility":      score >= 45,
        "rsi_context":         score >= 50,
        "macd_histogram":      score >= 65,
        "order_blocks":        score >= 60
    }


def _observation(
    edge:          float,
    present_total: int,
    total:         int
) -> str:
    if present_total < 10:
        return "Insufficient data"
    if edge is None:
        return "No edge data"
    if edge > 20:
        return "Strong positive edge"
    if edge > 10:
        return "Positive edge"
    if edge > 0:
        return "Weak positive edge"
    if edge > -10:
        return "Neutral — monitor"
    return "Negative edge — review weight"


def _reliability_note(total: int) -> str:
    if total >= 200:
        return "Reliable — sufficient sample size"
    if total >= 100:
        return f"Developing — {200 - total} more trades needed for full reliability"
    if total >= 50:
        return f"Early data — {200 - total} more trades needed — treat as directional only"
    return f"Too early — {200 - total} more trades needed — do not draw conclusions"


def _build_grade_stats(grade_stats: dict) -> list:
    result = []
    for grade, s in grade_stats.items():
        total = s["wins"] + s["losses"]
        result.append({
            "grade":    grade,
            "total":    total,
            "wins":     s["wins"],
            "losses":   s["losses"],
            "win_rate": round(s["wins"] / total * 100, 1) if total > 0 else 0
        })
    result.sort(key=lambda x: x["grade"])
    return result