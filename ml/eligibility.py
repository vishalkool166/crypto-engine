import logging
import os
from config import cfg

log = logging.getLogger(__name__)

MODEL_PATH = "ml/models/lgbm_model.pkl"


def check_ml_eligibility() -> bool:
    try:
        from database import SessionLocal, Signal
        with SessionLocal() as db:
            count = db.query(Signal).filter(
                Signal.outcome.in_(["win", "loss"]),
                Signal.factor_scores.isnot(None)
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
                Signal.outcome.in_(["win", "loss"]),
                Signal.factor_scores.isnot(None)
            ).count()
    except Exception as e:
        log.error(f"ML status query failed: {e}")
        count = 0

    eligible  = count >= cfg.ML_MIN_TRADES
    remaining = max(0, cfg.ML_MIN_TRADES - count)

    model_exists = os.path.exists(MODEL_PATH)

    from ml.trainer import get_model_meta
    meta = get_model_meta()

    if cfg.ML_ENABLED and model_exists:
        message = f"ML active — model trained on {meta.get('samples', 0)} trades · AUC:{meta.get('cv_auc', '--')}"
    elif eligible and not model_exists:
        message = f"Ready to train — {count} trades available. Run /ml train to activate."
    else:
        message = f"{remaining} more trades needed before ML activates"

    return {
        "closed_trades": count,
        "required":      cfg.ML_MIN_TRADES,
        "eligible":      eligible,
        "ml_enabled":    cfg.ML_ENABLED,
        "model_exists":  model_exists,
        "trained_at":    meta.get("trained_at", "--"),
        "cv_auc":        meta.get("cv_auc", "--"),
        "win_rate":      meta.get("win_rate", 0),
        "top_features":  meta.get("top_features", []),
        "message":       message
    }


def check_and_train_if_ready():
    """
    Called by scheduler every hour.
    Auto-trains when 100 trades hit for first time.
    Auto-retrains every 50 new trades after that.
    """
    try:
        if not check_ml_eligibility():
            return

        if not cfg.ML_ENABLED:
            log.info("ML eligibility reached — triggering initial training")
            from ml.trainer import train_model
            result = train_model()
            if result.get("success"):
                log.info(f"Initial ML training complete: {result}")
            else:
                log.error(f"Initial ML training failed: {result}")
            return

        from ml.trainer import retrain_if_needed
        retrained = retrain_if_needed()
        if retrained:
            log.info("ML model retrained successfully")

    except Exception as e:
        log.error(f"check_and_train_if_ready error: {e}")