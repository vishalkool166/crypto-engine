import logging
import numpy as np
from datetime import datetime, timezone
from config import cfg, ADAPTATION_CONFIG

log = logging.getLogger(__name__)


def optimize_all() -> dict:
    try:
        from ml.performance_tracker import get_win_rate_at_threshold

        results = {}

        parameters = [
            {
                "name":       "sweep_min_score",
                "thresholds": list(np.arange(0.15, 0.55, 0.05)),
                "direction":  "higher_is_better",
            },
            {
                "name":       "zone_min_score",
                "thresholds": list(np.arange(0.30, 0.75, 0.05)),
                "direction":  "higher_is_better",
            },
            {
                "name":       "grade_a_threshold",
                "thresholds": list(np.arange(0.55, 0.80, 0.05)),
                "direction":  "higher_is_better",
            },
        ]

        for param in parameters:
            result = optimize_parameter(
                parameter  = param["name"],
                thresholds = [round(t, 2) for t in param["thresholds"]],
            )
            if result:
                results[param["name"]] = result

        return results

    except Exception as e:
        log.error("optimize_all: %s", e)
        return {}


def optimize_parameter(
    parameter:  str,
    thresholds: list,
    min_trades: int = 10,
) -> dict | None:
    try:
        from ml.performance_tracker import get_win_rate_at_threshold

        wr_data = get_win_rate_at_threshold(
            parameter  = parameter,
            thresholds = thresholds,
            min_trades = min_trades,
        )

        if not wr_data:
            log.info("optimize_parameter %s: insufficient data", parameter)
            return None

        current_value = _get_current_value(parameter)
        current_wr    = _get_wr_at_value(wr_data, current_value)

        best          = max(wr_data, key=lambda x: x["win_rate_raw"])
        best_threshold= best["threshold"]
        best_wr       = best["win_rate_raw"]

        improvement   = best_wr - (current_wr or 0)

        min_improve   = ADAPTATION_CONFIG["change_rules"]["min_win_rate_improvement"]

        if improvement < min_improve:
            log.info(
                "optimize_parameter %s: best threshold %.2f WR %.1f%% — improvement %.1f%% below minimum %.1f%%",
                parameter, best_threshold, best_wr * 100, improvement * 100, min_improve * 100
            )
            return {
                "parameter":       parameter,
                "current_value":   current_value,
                "optimal_value":   best_threshold,
                "current_wr":      round((current_wr or 0) * 100, 1),
                "optimal_wr":      round(best_wr * 100, 1),
                "improvement":     round(improvement * 100, 1),
                "data_basis":      best["trades"],
                "recommend_change":False,
                "reason":          f"Improvement {improvement*100:.1f}% below minimum {min_improve*100:.0f}%",
                "all_thresholds":  wr_data,
            }

        soft = ADAPTATION_CONFIG["soft_limits"].get(parameter, {})
        lo   = soft.get("min", 0)
        hi   = soft.get("max", 1)

        if best_threshold < lo or best_threshold > hi:
            return {
                "parameter":       parameter,
                "current_value":   current_value,
                "optimal_value":   best_threshold,
                "current_wr":      round((current_wr or 0) * 100, 1),
                "optimal_wr":      round(best_wr * 100, 1),
                "improvement":     round(improvement * 100, 1),
                "data_basis":      best["trades"],
                "recommend_change":False,
                "reason":          f"Optimal value {best_threshold} outside soft limits [{lo}, {hi}]",
                "all_thresholds":  wr_data,
            }

        max_change = ADAPTATION_CONFIG["change_rules"]["max_change_pct_per_cycle"]
        if current_value > 0:
            actual_change = abs(best_threshold - current_value) / current_value
            if actual_change > max_change:
                direction     = 1 if best_threshold > current_value else -1
                best_threshold= round(current_value * (1 + direction * max_change), 3)
                best_threshold= max(lo, min(hi, best_threshold))
                log.info(
                    "optimize_parameter %s: capped change to %.3f (max %.0f%%)",
                    parameter, best_threshold, max_change * 100
                )

        confidence = _get_confidence(best["trades"])

        return {
            "parameter":       parameter,
            "current_value":   current_value,
            "optimal_value":   round(best_threshold, 3),
            "current_wr":      round((current_wr or 0) * 100, 1),
            "optimal_wr":      round(best_wr * 100, 1),
            "improvement":     round(improvement * 100, 1),
            "data_basis":      best["trades"],
            "recommend_change":True,
            "confidence":      confidence,
            "reason":          (
                f"Threshold {best_threshold:.2f} yields {best_wr*100:.1f}% WR "
                f"vs current {(current_wr or 0)*100:.1f}% — "
                f"+{improvement*100:.1f}% improvement on {best['trades']} trades"
            ),
            "all_thresholds":  wr_data,
        }

    except Exception as e:
        log.error("optimize_parameter %s: %s", parameter, e)
        return None


def optimize_sweep_age() -> dict | None:
    try:
        from database import SessionLocal, Signal as SignalModel, Trade as TradeModel

        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.signal_id.isnot(None)
            ).all()

            signal_ids = [t.signal_id for t in closed]
            signals    = db.query(SignalModel).filter(
                SignalModel.id.in_(signal_ids)
            ).all()

        if len(closed) < 20:
            return None

        sig_map = {s.id: s for s in signals}

        age_buckets = {
            "0-3h":   [],
            "3-6h":   [],
            "6-9h":   [],
            "9-12h":  [],
            "12-24h": [],
        }

        for t in closed:
            sig = sig_map.get(t.signal_id)
            if not sig:
                continue
            try:
                from database import SignalSnapshot
                with SessionLocal() as db2:
                    snap = db2.query(SignalSnapshot).filter(
                        SignalSnapshot.signal_id == sig.id
                    ).first()
                age = float(snap.sweep_age_hours or 0) if snap else 0.0
            except Exception:
                age = 0.0

            if age <= 3:
                age_buckets["0-3h"].append(t)
            elif age <= 6:
                age_buckets["3-6h"].append(t)
            elif age <= 9:
                age_buckets["6-9h"].append(t)
            elif age <= 12:
                age_buckets["9-12h"].append(t)
            else:
                age_buckets["12-24h"].append(t)

        results = {}
        for bucket, trades in age_buckets.items():
            if len(trades) >= 5:
                wins = sum(1 for t in trades if t.outcome == "win")
                results[bucket] = {
                    "trades":   len(trades),
                    "wins":     wins,
                    "win_rate": round(wins / len(trades) * 100, 1),
                }

        if not results:
            return None

        best_bucket = max(results, key=lambda x: results[x]["win_rate"])
        current_max = cfg.SCALP_ENGINE.get("sweep_max_age_hours", 12)

        age_map = {"0-3h": 3, "3-6h": 6, "6-9h": 9, "9-12h": 12, "12-24h": 24}
        optimal_max = age_map.get(best_bucket, current_max)

        return {
            "parameter":       "sweep_max_age_hours",
            "current_value":   current_max,
            "optimal_value":   optimal_max,
            "buckets":         results,
            "best_bucket":     best_bucket,
            "recommend_change":optimal_max != current_max,
            "reason":          f"Best WR in {best_bucket} bucket — optimal max age {optimal_max}h",
        }

    except Exception as e:
        log.error("optimize_sweep_age: %s", e)
        return None


def optimize_session_sizing() -> dict:
    try:
        from ml.performance_tracker import get_stats_by_session

        session_stats = get_stats_by_session(min_trades=5)
        if not session_stats:
            return {}

        recommendations = {}
        for session, stats in session_stats.items():
            wr = stats.get("win_rate", 0)
            if wr < 40:
                recommendations[session] = {
                    "action":   "avoid",
                    "win_rate": wr,
                    "reason":   f"{session} WR {wr:.1f}% below 40% threshold",
                }
            elif wr < 50:
                recommendations[session] = {
                    "action":   "reduce_size",
                    "win_rate": wr,
                    "reason":   f"{session} WR {wr:.1f}% — reduce position size 50%",
                }
            else:
                recommendations[session] = {
                    "action":   "normal",
                    "win_rate": wr,
                    "reason":   f"{session} WR {wr:.1f}% — trade normally",
                }

        return recommendations

    except Exception as e:
        log.error("optimize_session_sizing: %s", e)
        return {}


def run_full_optimization() -> dict:
    try:
        log.info("Running full threshold optimization")

        results = {
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "parameters":     optimize_all(),
            "sweep_age":      optimize_sweep_age(),
            "session_sizing": optimize_session_sizing(),
        }

        recommendations = []
        for param, result in results["parameters"].items():
            if result and result.get("recommend_change"):
                recommendations.append({
                    "parameter":     param,
                    "current_value": result["current_value"],
                    "new_value":     result["optimal_value"],
                    "improvement":   result["improvement"],
                    "confidence":    result.get("confidence", "low"),
                    "data_basis":    result["data_basis"],
                    "reason":        result["reason"],
                })

        if results.get("sweep_age") and results["sweep_age"].get("recommend_change"):
            sa = results["sweep_age"]
            recommendations.append({
                "parameter":     "sweep_max_age_hours",
                "current_value": sa["current_value"],
                "new_value":     sa["optimal_value"],
                "improvement":   0.0,
                "confidence":    "medium",
                "data_basis":    sum(v["trades"] for v in sa.get("buckets", {}).values()),
                "reason":        sa["reason"],
            })

        results["recommendations"] = recommendations
        log.info("Optimization complete — %s recommendations", len(recommendations))
        return results

    except Exception as e:
        log.error("run_full_optimization: %s", e)
        return {}


def _get_current_value(parameter: str) -> float:
    SE = cfg.SCALP_ENGINE
    mapping = {
        "sweep_min_score":       SE.get("sweep_min_score",       0.30),
        "zone_min_score":        SE.get("zone_min_score",        0.40),
        "grade_a_threshold":     SE.get("grade_a_threshold",     0.65),
        "grade_aplus_threshold": SE.get("grade_aplus_threshold", 0.80),
        "sweep_max_age_hours":   SE.get("sweep_max_age_hours",   12),
        "base_risk_pct":         SE.get("base_risk_pct",         0.01),
    }
    return mapping.get(parameter, 0.0)


def _get_wr_at_value(wr_data: list, value: float) -> float | None:
    for item in wr_data:
        if abs(item["threshold"] - value) < 0.001:
            return item["win_rate_raw"]
    if wr_data:
        closest = min(wr_data, key=lambda x: abs(x["threshold"] - value))
        return closest["win_rate_raw"]
    return None


def _get_confidence(trade_count: int) -> str:
    if trade_count >= 200:
        return "high"
    if trade_count >= 100:
        return "medium"
    if trade_count >= 50:
        return "low"
    return "very_low"