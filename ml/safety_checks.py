import logging
from datetime import datetime, timezone, timedelta
from config import cfg, ADAPTATION_CONFIG

log = logging.getLogger(__name__)

PILLAR_MIN_WEIGHT = 0.05
PILLAR_MAX_WEIGHT = 0.50
PILLAR_MAX_CHANGE = 0.05
PILLAR_MIN_TRADES = 200
PILLAR_MIN_FAILURES = 20


def check_all(parameter: str, current_value: float, proposed_value: float) -> dict:
    checks = [
        _check_frozen(),
        _check_hard_limits(parameter, proposed_value),
        _check_soft_limits(parameter, proposed_value),
        _check_change_magnitude(parameter, current_value, proposed_value),
        _check_time_since_last_change(parameter),
        _check_monthly_change_count(),
        _check_min_trades(),
        _check_drawdown_state(),
    ]

    failures = [c for c in checks if not c["pass"]]
    passed   = len(failures) == 0

    return {
        "pass":     passed,
        "failures": [f["reason"] for f in failures],
        "checks":   checks,
    }


def check_pillar_weight_change(
    pillar:         str,
    current_weight: float,
    new_weight:     float,
) -> dict:
    checks = [
        _check_frozen(),
        _check_pillar_weight_bounds(pillar, new_weight),
        _check_pillar_weight_magnitude(pillar, current_weight, new_weight),
        _check_pillar_min_trades(),
        _check_pillar_min_failures(pillar),
        _check_monthly_change_count(),
        _check_drawdown_state(),
        _check_pillar_weight_sum(pillar, new_weight, current_weight),
    ]

    failures = [c for c in checks if not c["pass"]]
    passed   = len(failures) == 0

    return {
        "pass":     passed,
        "failures": [f["reason"] for f in failures],
        "checks":   checks,
    }


def _check_frozen() -> dict:
    if cfg.ADAPTATION_FROZEN:
        return {
            "pass":   False,
            "name":   "frozen_check",
            "reason": "Adaptations are frozen — use /unfreeze to resume"
        }
    return {"pass": True, "name": "frozen_check", "reason": ""}


def _check_hard_limits(parameter: str, proposed_value: float) -> dict:
    hard = ADAPTATION_CONFIG["hard_limits"]

    limit_map = {
        "sweep_min_score":    ("min_sweep_score",    ">="),
        "zone_min_score":     ("min_zone_score",     ">="),
        "grade_a_threshold":  ("min_combined_score", ">="),
        "sweep_max_age_hours":("max_sweep_age_hours","<="),
        "base_risk_pct":      ("max_risk_per_trade", "<="),
        "max_open_trades":    ("max_concurrent_trades", "<="),
        "max_leverage":       ("max_leverage",       "<="),
    }

    if parameter not in limit_map:
        return {"pass": True, "name": "hard_limit_check", "reason": ""}

    limit_key, operator = limit_map[parameter]
    limit_value         = hard.get(limit_key)

    if limit_value is None:
        return {"pass": True, "name": "hard_limit_check", "reason": ""}

    if operator == ">=" and proposed_value < limit_value:
        return {
            "pass":   False,
            "name":   "hard_limit_check",
            "reason": f"{parameter} cannot go below hard limit {limit_value} (proposed {proposed_value})"
        }

    if operator == "<=" and proposed_value > limit_value:
        return {
            "pass":   False,
            "name":   "hard_limit_check",
            "reason": f"{parameter} cannot exceed hard limit {limit_value} (proposed {proposed_value})"
        }

    return {"pass": True, "name": "hard_limit_check", "reason": ""}


def _check_soft_limits(parameter: str, proposed_value: float) -> dict:
    soft = ADAPTATION_CONFIG["soft_limits"]

    if parameter not in soft:
        return {"pass": True, "name": "soft_limit_check", "reason": ""}

    limits = soft[parameter]
    lo     = limits["min"]
    hi     = limits["max"]

    if proposed_value < lo:
        return {
            "pass":   False,
            "name":   "soft_limit_check",
            "reason": f"{parameter} below soft floor {lo} (proposed {proposed_value})"
        }

    if proposed_value > hi:
        return {
            "pass":   False,
            "name":   "soft_limit_check",
            "reason": f"{parameter} above soft ceiling {hi} (proposed {proposed_value})"
        }

    return {"pass": True, "name": "soft_limit_check", "reason": ""}


def _check_change_magnitude(parameter: str, current_value: float, proposed_value: float) -> dict:
    rules      = ADAPTATION_CONFIG["change_rules"]
    max_change = rules["max_change_pct_per_cycle"]

    if current_value == 0:
        return {"pass": True, "name": "magnitude_check", "reason": ""}

    actual_change = abs(proposed_value - current_value) / abs(current_value)

    if actual_change > max_change:
        return {
            "pass":   False,
            "name":   "magnitude_check",
            "reason": (
                f"{parameter} change of {actual_change*100:.1f}% exceeds "
                f"max {max_change*100:.0f}% per cycle"
            )
        }

    return {"pass": True, "name": "magnitude_check", "reason": ""}


def _check_time_since_last_change(parameter: str) -> dict:
    try:
        rules    = ADAPTATION_CONFIG["change_rules"]
        min_days = rules["min_days_between_changes"]

        from database import get_session, AdaptationLog
        with get_session() as db:
            last = db.query(AdaptationLog).filter(
                AdaptationLog.parameter   == parameter,
                AdaptationLog.rolled_back == False,
            ).order_by(AdaptationLog.applied_at.desc()).first()

            if not last:
                return {"pass": True, "name": "time_check", "reason": ""}

            applied = last.applied_at
            if applied.tzinfo is None:
                applied = applied.replace(tzinfo=timezone.utc)

            days_since = (datetime.now(timezone.utc) - applied).days

            if days_since < min_days:
                return {
                    "pass":   False,
                    "name":   "time_check",
                    "reason": (
                        f"{parameter} changed {days_since}d ago — "
                        f"minimum {min_days}d between changes"
                    )
                }

        return {"pass": True, "name": "time_check", "reason": ""}

    except Exception as e:
        log.error("_check_time_since_last_change: %s", e)
        return {"pass": True, "name": "time_check", "reason": ""}


def _check_monthly_change_count() -> dict:
    try:
        rules     = ADAPTATION_CONFIG["change_rules"]
        max_month = rules["max_parameter_changes_per_month"]

        from database import get_session, AdaptationLog
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        with get_session() as db:
            count = db.query(AdaptationLog).filter(
                AdaptationLog.applied_at  >= month_start,
                AdaptationLog.rolled_back == False,
            ).count()

        if count >= max_month:
            return {
                "pass":   False,
                "name":   "monthly_limit_check",
                "reason": f"Monthly change limit reached ({count}/{max_month} this month)"
            }

        return {"pass": True, "name": "monthly_limit_check", "reason": ""}

    except Exception as e:
        log.error("_check_monthly_change_count: %s", e)
        return {"pass": True, "name": "monthly_limit_check", "reason": ""}


def _check_min_trades() -> dict:
    try:
        rules      = ADAPTATION_CONFIG["change_rules"]
        min_trades = rules["min_trades_before_change"]

        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            count = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()

        if count < min_trades:
            return {
                "pass":   False,
                "name":   "min_trades_check",
                "reason": f"Only {count} closed trades — need {min_trades} before adapting"
            }

        return {"pass": True, "name": "min_trades_check", "reason": ""}

    except Exception as e:
        log.error("_check_min_trades: %s", e)
        return {"pass": True, "name": "min_trades_check", "reason": ""}


def _check_drawdown_state() -> dict:
    try:
        from database import SessionLocal, Trade as TradeModel

        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"]),
                TradeModel.net_pnl.isnot(None)
            ).order_by(TradeModel.opened_at.asc()).all()

        if not closed:
            return {"pass": True, "name": "drawdown_check", "reason": ""}

        equity = 0.0
        peak   = 0.0
        for t in closed:
            equity += float(t.net_pnl or t.pnl or 0)
            if equity > peak:
                peak = equity

        drawdown = (peak - equity) / peak if peak > 0 else 0.0

        if drawdown > 0.15:
            return {
                "pass":   False,
                "name":   "drawdown_check",
                "reason": (
                    f"Current drawdown {drawdown*100:.1f}% exceeds 15% — "
                    f"no parameter changes during significant drawdown"
                )
            }

        return {"pass": True, "name": "drawdown_check", "reason": ""}

    except Exception as e:
        log.error("_check_drawdown_state: %s", e)
        return {"pass": True, "name": "drawdown_check", "reason": ""}


def _check_pillar_weight_bounds(pillar: str, new_weight: float) -> dict:
    if new_weight < PILLAR_MIN_WEIGHT:
        return {
            "pass":   False,
            "name":   "pillar_bounds_check",
            "reason": f"Pillar {pillar} weight {new_weight:.3f} below minimum {PILLAR_MIN_WEIGHT}"
        }
    if new_weight > PILLAR_MAX_WEIGHT:
        return {
            "pass":   False,
            "name":   "pillar_bounds_check",
            "reason": f"Pillar {pillar} weight {new_weight:.3f} above maximum {PILLAR_MAX_WEIGHT}"
        }
    return {"pass": True, "name": "pillar_bounds_check", "reason": ""}


def _check_pillar_weight_magnitude(
    pillar:         str,
    current_weight: float,
    new_weight:     float,
) -> dict:
    change = abs(new_weight - current_weight)
    if change > PILLAR_MAX_CHANGE:
        return {
            "pass":   False,
            "name":   "pillar_magnitude_check",
            "reason": (
                f"Pillar {pillar} weight change {change:.3f} exceeds "
                f"max {PILLAR_MAX_CHANGE:.3f} per cycle"
            )
        }
    return {"pass": True, "name": "pillar_magnitude_check", "reason": ""}


def _check_pillar_min_trades() -> dict:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            count = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()

        if count < PILLAR_MIN_TRADES:
            return {
                "pass":   False,
                "name":   "pillar_min_trades_check",
                "reason": (
                    f"Only {count} closed trades — need {PILLAR_MIN_TRADES} "
                    f"before changing pillar weights"
                )
            }

        return {"pass": True, "name": "pillar_min_trades_check", "reason": ""}

    except Exception as e:
        log.error("_check_pillar_min_trades: %s", e)
        return {"pass": True, "name": "pillar_min_trades_check", "reason": ""}


def _check_pillar_min_failures(pillar: str) -> dict:
    try:
        from database import SessionLocal, ThesisSnapshot

        valid_key = f"{pillar}_valid"

        with SessionLocal() as db:
            total = db.query(ThesisSnapshot).filter(
                ThesisSnapshot.outcome.isnot(None)
            ).count()

            if total == 0:
                return {
                    "pass":   False,
                    "name":   "pillar_failures_check",
                    "reason": f"No thesis snapshots with outcomes yet"
                }

        from database import SessionLocal as SL
        with SL() as db:
            all_snaps = db.query(ThesisSnapshot).filter(
                ThesisSnapshot.outcome.isnot(None)
            ).all()

        failure_count = sum(
            1 for s in all_snaps
            if not getattr(s, f"{pillar}_valid", True)
        )

        if failure_count < PILLAR_MIN_FAILURES:
            return {
                "pass":   False,
                "name":   "pillar_failures_check",
                "reason": (
                    f"Pillar {pillar} only has {failure_count} failure events — "
                    f"need {PILLAR_MIN_FAILURES} for reliable analysis"
                )
            }

        return {"pass": True, "name": "pillar_failures_check", "reason": ""}

    except Exception as e:
        log.error("_check_pillar_min_failures: %s", e)
        return {"pass": True, "name": "pillar_failures_check", "reason": ""}


def _check_pillar_weight_sum(
    pillar:         str,
    new_weight:     float,
    current_weight: float,
) -> dict:
    try:
        from ml.pillar_analyzer import get_current_weights, PILLAR_NAMES

        current_weights = get_current_weights()
        simulated       = dict(current_weights)
        simulated[pillar] = new_weight

        total = sum(simulated.values())

        if total < 0.80 or total > 1.20:
            return {
                "pass":   False,
                "name":   "pillar_sum_check",
                "reason": (
                    f"Pillar weights would sum to {total:.3f} — "
                    f"must be between 0.80 and 1.20 (auto-normalized)"
                )
            }

        return {"pass": True, "name": "pillar_sum_check", "reason": ""}

    except Exception as e:
        log.error("_check_pillar_weight_sum: %s", e)
        return {"pass": True, "name": "pillar_sum_check", "reason": ""}


def check_win_rate_improvement(
    parameter:        str,
    current_value:    float,
    proposed_value:   float,
    current_wr:       float,
    proposed_wr:      float,
) -> dict:
    rules       = ADAPTATION_CONFIG["change_rules"]
    min_improve = rules["min_win_rate_improvement"]
    improvement = proposed_wr - current_wr

    if improvement < min_improve:
        return {
            "pass":   False,
            "reason": (
                f"{parameter}: proposed WR {proposed_wr*100:.1f}% vs "
                f"current {current_wr*100:.1f}% — "
                f"improvement {improvement*100:.1f}% below minimum {min_improve*100:.0f}%"
            )
        }

    return {
        "pass":        True,
        "reason":      "",
        "improvement": round(improvement * 100, 2),
    }


def check_drawdown_impact(
    current_max_dd:  float,
    proposed_max_dd: float,
) -> dict:
    if proposed_max_dd > current_max_dd * 1.10:
        return {
            "pass":   False,
            "reason": (
                f"Proposed change increases max drawdown from "
                f"{current_max_dd*100:.1f}% to {proposed_max_dd*100:.1f}%"
            )
        }
    return {"pass": True, "reason": ""}


def get_safety_summary() -> dict:
    try:
        from database import get_session, AdaptationLog
        from database import SessionLocal, Trade as TradeModel

        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        with get_session() as db:
            changes_this_month = db.query(AdaptationLog).filter(
                AdaptationLog.applied_at  >= month_start,
                AdaptationLog.rolled_back == False,
            ).count()

        with SessionLocal() as db:
            total_trades = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()

        rules = ADAPTATION_CONFIG["change_rules"]

        pillar_ready = total_trades >= PILLAR_MIN_TRADES

        return {
            "frozen":                cfg.ADAPTATION_FROZEN,
            "changes_this_month":    changes_this_month,
            "max_changes_month":     rules["max_parameter_changes_per_month"],
            "total_trades":          total_trades,
            "min_trades_required":   rules["min_trades_before_change"],
            "ready_to_adapt":        total_trades >= rules["min_trades_before_change"],
            "pillar_min_trades":     PILLAR_MIN_TRADES,
            "pillar_ready":          pillar_ready,
            "require_approval":      rules["require_human_approval"],
        }

    except Exception as e:
        log.error("get_safety_summary: %s", e)
        return {}