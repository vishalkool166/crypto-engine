import json
import logging
from database import SessionLocal, Trade, Signal as SignalModel

log = logging.getLogger(__name__)

FACTOR_KEYS = [
    "liquidity_sweep",
    "displacement",
    "order_blocks",
    "retest_confirmation",
    "market_structure",
]

FACTOR_PASS_THRESHOLDS = {
    "liquidity_sweep":     6,
    "displacement":        6,
    "order_blocks":        3,
    "retest_confirmation": 6,
    "market_structure":    5,
}


def run_factor_analysis() -> dict:
    db = SessionLocal()
    try:
        signal_trades = db.query(SignalModel).filter(
            SignalModel.outcome.in_(["win", "loss"])
        ).all()

        trade_records = db.query(Trade).filter(
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss"])
        ).all()

        seen_ids  = set()
        all_items = []

        for sig in signal_trades:
            if sig.id not in seen_ids:
                seen_ids.add(sig.id)
                all_items.append(("signal", sig, sig))

        for trade in trade_records:
            if trade.signal_id and trade.signal_id in seen_ids:
                continue
            sig = None
            if trade.signal_id:
                sig = db.query(SignalModel).filter(
                    SignalModel.id == trade.signal_id
                ).first()
            all_items.append(("trade", trade, sig))
            if sig:
                seen_ids.add(sig.id)

        if not all_items:
            return {
                "error":        "No closed trades yet",
                "total":        0,
                "min_required": 20,
            }

        total  = len(all_items)
        wins   = [x for x in all_items if x[1].outcome == "win"]
        losses = [x for x in all_items if x[1].outcome == "loss"]

        log.info("Factor analysis: %s items — %sW %sL", total, len(wins), len(losses))

        factor_stats = {
            key: {
                "win_present":  0,
                "win_absent":   0,
                "loss_present": 0,
                "loss_absent":  0,
            }
            for key in FACTOR_KEYS
        }

        grade_stats   = {}
        has_real_data = False

        for source, record, sig in all_items:
            grade = record.grade or "?"
            if grade not in grade_stats:
                grade_stats[grade] = {"wins": 0, "losses": 0}

            if record.outcome == "win":
                grade_stats[grade]["wins"] += 1
            else:
                grade_stats[grade]["losses"] += 1

            factor_presence = _get_factor_presence(sig, record)
            if factor_presence.get("_source") == "actual":
                has_real_data = True

            for key in FACTOR_KEYS:
                present = factor_presence.get(key, False)
                if record.outcome == "win":
                    if present:
                        factor_stats[key]["win_present"]  += 1
                    else:
                        factor_stats[key]["win_absent"]   += 1
                else:
                    if present:
                        factor_stats[key]["loss_present"] += 1
                    else:
                        factor_stats[key]["loss_absent"]  += 1

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
                "factor":           key,
                "present_total":    present_total,
                "absent_total":     absent_total,
                "win_rate_present": win_rate_present,
                "win_rate_absent":  win_rate_absent,
                "edge":             edge,
                "observation":      _observation(edge, present_total, total),
            })

        table.sort(key=lambda x: x["edge"] or -999, reverse=True)

        overall_wr  = round(len(wins) / total * 100, 1)
        reliability = _reliability_note(total)

        return {
            "total":        total,
            "wins":         len(wins),
            "losses":       len(losses),
            "overall_wr":   overall_wr,
            "min_required": 20,
            "reliable":     total >= 20,
            "reliability":  reliability,
            "data_source":  "actual" if has_real_data else "proxy",
            "table":        table,
            "grade_stats":  _build_grade_stats(grade_stats),
            "top_factors":  [r for r in table if r["edge"] and r["edge"] > 10][:5],
            "weak_factors": [r for r in table if r["edge"] is not None and r["edge"] < 5][:5],
        }

    except Exception as e:
        log.error("Factor analysis error: %s", e)
        return {"error": str(e)}

    finally:
        db.close()


def _get_factor_presence(sig, record) -> dict:
    if sig and sig.factor_scores:
        try:
            scores = json.loads(sig.factor_scores)
            result = {"_source": "actual"}
            for key in FACTOR_KEYS:
                earned    = scores.get(key, 0)
                threshold = FACTOR_PASS_THRESHOLDS.get(key, 1)
                result[key] = earned >= threshold
            return result
        except Exception:
            pass

    sweep_ok  = False
    retest_ok = False
    disp_ok   = False

    if sig:
        sweep_ok  = (sig.sweep_score  or 0) >= 6
        retest_ok = (sig.retest_score or 0) >= 6
        disp_ok   = (sig.disp_score   or 0) >= 6

    score = 0
    if sig:
        score = sig.score or 0
    elif hasattr(record, "score_at_entry"):
        score = record.score_at_entry or 0

    return {
        "_source":             "proxy",
        "liquidity_sweep":     sweep_ok,
        "displacement":        disp_ok,
        "order_blocks":        score >= 60,
        "retest_confirmation": retest_ok,
        "market_structure":    score >= 55,
    }


def _observation(edge, present_total, total) -> str:
    if present_total < 5:
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
    return "Negative edge — review"


def _reliability_note(total: int) -> str:
    if total >= 200:
        return "Reliable — sufficient sample size"
    if total >= 100:
        return f"Developing — {200 - total} more trades for full reliability"
    if total >= 20:
        return f"Early data — {200 - total} more trades needed"
    return f"Too early — {20 - total} more trades needed"


def _build_grade_stats(grade_stats: dict) -> list:
    result = []
    for grade, s in grade_stats.items():
        total = s["wins"] + s["losses"]
        result.append({
            "grade":    grade,
            "total":    total,
            "wins":     s["wins"],
            "losses":   s["losses"],
            "win_rate": round(s["wins"] / total * 100, 1) if total > 0 else 0,
        })
    result.sort(key=lambda x: x["grade"])
    return result