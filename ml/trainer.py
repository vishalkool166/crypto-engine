import os
import json
import logging
import pickle
import numpy as np
from datetime import datetime, timezone
from ml.dataset import build_dataset, get_feature_names

log = logging.getLogger(__name__)

MODEL_DIR  = "ml/models"
MODEL_PATH = "ml/models/lgbm_model.pkl"
META_PATH  = "ml/models/lgbm_meta.json"


def _ensure_model_dir():
    os.makedirs(MODEL_DIR, exist_ok=True)


def train_model() -> dict:
    """
    Train LightGBM classifier on closed signal data.
    Returns training report dict.
    """
    log.info("Starting LightGBM training...")

    X, y = build_dataset()
    if X is None or y is None:
        return {"success": False, "reason": "Not enough data to train"}

    if len(X) < 10:
        return {"success": False, "reason": f"Need at least 10 samples, got {len(X)}"}

    try:
        import lightgbm as lgb
    except ImportError:
        return {"success": False, "reason": "lightgbm not installed — run: pip install lightgbm"}

    try:
        from sklearn.model_selection import StratifiedKFold, cross_val_score
        from sklearn.metrics import classification_report, roc_auc_score
        has_sklearn = True
    except ImportError:
        has_sklearn = False
        log.warning("sklearn not available — skipping cross validation")

    _ensure_model_dir()

    # Class weights to handle imbalanced data
    n_pos    = y.sum()
    n_neg    = (y == 0).sum()
    scale_pw = n_neg / n_pos if n_pos > 0 else 1.0

    model = lgb.LGBMClassifier(
        n_estimators      = 200,
        learning_rate     = 0.05,
        max_depth         = 4,
        num_leaves        = 15,
        min_child_samples = 5,
        subsample         = 0.8,
        colsample_bytree  = 0.8,
        scale_pos_weight  = scale_pw,
        random_state      = 42,
        verbose           = -1,
        n_jobs            = 1
    )

    cv_score    = None
    cv_std      = None
    auc_score   = None
    report_dict = {}

    if has_sklearn and len(X) >= 20:
        try:
            cv      = StratifiedKFold(n_splits=min(5, len(X) // 4), shuffle=True, random_state=42)
            scores  = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
            cv_score = round(float(scores.mean()), 4)
            cv_std   = round(float(scores.std()),  4)
            log.info(f"Cross-validation AUC: {cv_score:.4f} ± {cv_std:.4f}")
        except Exception as e:
            log.warning(f"Cross-validation failed: {e}")

    # Train on full dataset
    model.fit(X, y)

    # AUC on training data
    if has_sklearn:
        try:
            probs     = model.predict_proba(X)[:, 1]
            auc_score = round(float(roc_auc_score(y, probs)), 4)
            report    = classification_report(y, model.predict(X), output_dict=True)
            report_dict = {
                "precision_win":  round(report.get("1", {}).get("precision", 0), 3),
                "recall_win":     round(report.get("1", {}).get("recall",    0), 3),
                "f1_win":         round(report.get("1", {}).get("f1-score",  0), 3),
                "precision_loss": round(report.get("0", {}).get("precision", 0), 3),
                "recall_loss":    round(report.get("0", {}).get("recall",    0), 3),
            }
        except Exception as e:
            log.warning(f"Metrics calculation failed: {e}")

    # Feature importance
    feature_names      = get_feature_names()
    importances        = model.feature_importances_
    feature_importance = sorted(
        zip(feature_names, importances),
        key=lambda x: x[1],
        reverse=True
    )

    top_features = [
        {"feature": f, "importance": int(i)}
        for f, i in feature_importance[:10]
    ]

    log.info("Top features:")
    for f, i in feature_importance[:5]:
        log.info(f"  {f}: {i}")

    # Save model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    # Save metadata
    meta = {
        "trained_at":       datetime.now(timezone.utc).isoformat(),
        "samples":          len(X),
        "wins":             int(y.sum()),
        "losses":           int((y == 0).sum()),
        "win_rate":         round(float(y.mean()) * 100, 1),
        "features":         len(feature_names),
        "cv_auc":           cv_score,
        "cv_std":           cv_std,
        "train_auc":        auc_score,
        "top_features":     top_features,
        "classification":   report_dict,
        "threshold":        0.65,
    }

    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    log.info(
        f"Model saved — samples:{len(X)} "
        f"win_rate:{meta['win_rate']}% "
        f"cv_auc:{cv_score} "
        f"train_auc:{auc_score}"
    )

    # Enable ML in config
    _enable_ml()

    # Send Telegram notification
    _notify_training_complete(meta)

    return {
        "success":      True,
        "samples":      len(X),
        "wins":         int(y.sum()),
        "losses":       int((y == 0).sum()),
        "win_rate":     meta["win_rate"],
        "cv_auc":       cv_score,
        "train_auc":    auc_score,
        "top_features": top_features,
        "model_path":   MODEL_PATH,
    }


def retrain_if_needed() -> bool:
    """
    Check if retraining is needed.
    Retrain every 50 new trades after initial training.
    Returns True if retrained.
    """
    try:
        if not os.path.exists(META_PATH):
            return False

        with open(META_PATH, "r") as f:
            meta = json.load(f)

        last_samples = meta.get("samples", 0)

        from database import SessionLocal, Signal as SignalModel
        with SessionLocal() as db:
            current_count = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"]),
                SignalModel.factor_scores.isnot(None)
            ).count()

        new_trades = current_count - last_samples

        if new_trades >= 50:
            log.info(f"Retraining triggered — {new_trades} new trades since last training")
            result = train_model()
            return result.get("success", False)

        log.debug(f"No retrain needed — {new_trades} new trades since last training (need 50)")
        return False

    except Exception as e:
        log.error(f"Retrain check error: {e}")
        return False


def _enable_ml():
    try:
        from config import cfg, _ensure
        _ensure("ML_ENABLED", "true")
        cfg.ML_ENABLED = True
        log.info("ML_ENABLED set to True")
    except Exception as e:
        log.error(f"Failed to enable ML: {e}")


def _notify_training_complete(meta: dict):
    try:
        import asyncio
        from alerts.telegram import send

        top = meta.get("top_features", [])[:3]
        top_str = "\n".join(
            f"  `{f['feature']}` — importance: `{f['importance']}`"
            for f in top
        )

        asyncio.create_task(send(
            f"🤖 *LightGBM Model Trained*\n\n"
            f"Samples:   `{meta['samples']}`\n"
            f"Wins:      `{meta['wins']}` · Losses: `{meta['losses']}`\n"
            f"Win Rate:  `{meta['win_rate']}%`\n"
            f"CV AUC:    `{meta.get('cv_auc', '--')}`\n"
            f"Train AUC: `{meta.get('train_auc', '--')}`\n\n"
            f"*Top Features:*\n{top_str}\n\n"
            f"ML filter now active — threshold: `0.65`\n"
            f"Signals below 65% win probability will be skipped."
        ))
    except Exception as e:
        log.error(f"Training notification error: {e}")


def get_model_meta() -> dict:
    try:
        if not os.path.exists(META_PATH):
            return {}
        with open(META_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}