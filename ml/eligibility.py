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
        log.info("ML eligibility: %s/%s closed trades", count, cfg.ML_MIN_TRADES)
        return count >= cfg.ML_MIN_TRADES
    except Exception as e:
        log.error("ML eligibility check failed: %s", e)
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
        log.error("ML status query failed: %s", e)
        count = 0

    eligible     = count >= cfg.ML_MIN_TRADES
    remaining    = max(0, cfg.ML_MIN_TRADES - count)
    model_exists = os.path.exists(MODEL_PATH)

    from ml.trainer import get_model_meta
    meta = get_model_meta()

    if model_exists:
        message = f"ML active — model trained on {meta.get('samples', 0)} trades · AUC:{meta.get('cv_auc', '--')}"
    elif eligible and not model_exists:
        message = f"Ready to train — {count} trades available — training will start automatically"
    else:
        message = f"{remaining} more trades needed before ML trains — scoring neutral until then"

    return {
        "closed_trades": count,
        "required":      cfg.ML_MIN_TRADES,
        "eligible":      eligible,
        "ml_enabled":    True,
        "model_exists":  model_exists,
        "trained_at":    meta.get("trained_at", "--"),
        "cv_auc":        meta.get("cv_auc", "--"),
        "win_rate":      meta.get("win_rate", 0),
        "top_features":  meta.get("top_features", []),
        "message":       message,
    }


def check_and_train_if_ready():
    try:
        if not check_ml_eligibility():
            return

        model_exists = os.path.exists(MODEL_PATH)

        if not model_exists:
            log.info("ML eligibility reached — triggering initial training")
            from ml.trainer import train_model
            result = train_model()
            if result.get("success"):
                log.info("Initial ML training complete: %s", result)
            else:
                log.error("Initial ML training failed: %s", result)
            return

        from ml.trainer import retrain_if_needed
        retrained = retrain_if_needed()
        if retrained:
            log.info("ML model retrained successfully")

    except Exception as e:
        log.error("check_and_train_if_ready error: %s", e)