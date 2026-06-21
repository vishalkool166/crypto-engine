import logging
from config import cfg

log = logging.getLogger(__name__)


def check_ml_eligibility() -> bool:
    try:
        from database import SessionLocal, Signal
        with SessionLocal() as db:
            count = db.query(Signal).filter(
                Signal.outcome.notin_(["pending"]),
                Signal.outcome.isnot(None)
            ).count()
        log.info(f"ML eligibility: {count}/{cfg.ML_MIN_TRADES} closed trades")
        return count >= cfg.ML_MIN_TRADES
    except Exception as e:
        log.error(f"ML eligibility check failed: {e}")
        return False


def get_ml_status() -> dict:
    try:
        from database import SessionLocal, Signal
        with SessionLocal() as db:
            count = db.query(Signal).filter(
                Signal.outcome.notin_(["pending"]),
                Signal.outcome.isnot(None)
            ).count()
    except Exception as e:
        log.error(f"ML status query failed: {e}")
        count = 0

    eligible = count >= cfg.ML_MIN_TRADES
    remaining = max(0, cfg.ML_MIN_TRADES - count)

    message = (
        f"ML ready to activate — {count} closed trades recorded"
        if eligible else
        f"{remaining} more trades needed before ML activates"
    )

    return {
        "closed_trades": count,
        "required":      cfg.ML_MIN_TRADES,
        "eligible":      eligible,
        "ml_enabled":    cfg.ML_ENABLED,
        "message":       message
    }