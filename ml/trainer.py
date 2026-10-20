import os
import json
import logging
import pickle
import numpy as np
from datetime import datetime, timezone
from ml.dataset import build_dataset, get_feature_names

log = logging.getLogger(__name__)


def chronological_split(X, y, test_fraction: float = 0.2):
    """Split already time-ordered rows without shuffling or overlap."""
    if len(X) != len(y) or not 0 < test_fraction < 1:
        raise ValueError('Invalid chronological training data')
    split_idx = int(len(X) * (1 - test_fraction))
    if split_idx < 1 or split_idx >= len(X):
        raise ValueError('Chronological split needs non-empty train and holdout windows')
    return X.iloc[:split_idx], X.iloc[split_idx:], y.iloc[:split_idx], y.iloc[split_idx:]

MODEL_DIR  = "ml/models"
MODEL_PATH = "ml/models/lgbm_model.pkl"
META_PATH  = "ml/models/lgbm_meta.json"


def _ensure_model_dir():
    os.makedirs(MODEL_DIR, exist_ok=True)


def train_model() -> dict:
    log.info("Starting LightGBM training")

    X, y = build_dataset()
    if X is None or y is None:
        return {"success": False, "reason": "Not enough data to train"}

    if len(X) < 10:
        return {"success": False, "reason": f"Need at least 10 samples, got {len(X)}"}

    try:
        import lightgbm as lgb
    except ImportError:
        return {"success": False, "reason": "lightgbm not installed"}

    try:
        from sklearn.model_selection import TimeSeriesSplit, cross_val_score
        from sklearn.metrics import (
            classification_report,
            roc_auc_score,
            precision_score,
            recall_score,
            f1_score,
            confusion_matrix,
        )
        has_sklearn = True
    except ImportError:
        has_sklearn = False

    _ensure_model_dir()

    # Reserve the latest chronological tail as an untouched evaluation set.
    # Never fit, calibrate, or choose features using this holdout.
    try:
        X_train, X_holdout, y_train, y_holdout = chronological_split(X, y)
    except ValueError as exc:
        return {"success": False, "reason": str(exc)}
    if len(X_train) < 10 or y_train.nunique() < 2:
        return {"success": False, "reason": "Chronological training window needs both outcome classes"}

    n_pos    = y_train.sum()
    n_neg    = (y_train == 0).sum()
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
        n_jobs            = 1,
    )

    cv_score    = None
    cv_std      = None
    auc_score   = None
    precision   = None
    recall      = None
    f1          = None
    conf_matrix = None
    report_dict = {}

    if has_sklearn and len(X_train) >= 20:
        try:
            n_splits = min(5, len(X_train) // 4)
            tscv     = TimeSeriesSplit(n_splits=n_splits)
            scores   = cross_val_score(model, X_train, y_train, cv=tscv, scoring="roc_auc")
            cv_score = round(float(scores.mean()), 4)
            cv_std   = round(float(scores.std()),  4)
            log.info("CV AUC: %s +/- %s", cv_score, cv_std)
        except Exception as e:
            log.warning("Cross-validation failed: %s", e)

    model.fit(X_train, y_train)
    final_model = model

    if has_sklearn:
        try:
            probs     = final_model.predict_proba(X_holdout)[:, 1]
            preds     = final_model.predict(X_holdout)
            if y_holdout.nunique() > 1:
                auc_score = round(float(roc_auc_score(y_holdout, probs)), 4)
            precision = round(float(precision_score(y_holdout, preds, zero_division=0)), 4)
            recall    = round(float(recall_score(y_holdout, preds, zero_division=0)), 4)
            f1        = round(float(f1_score(y_holdout, preds, zero_division=0)), 4)
            cm        = confusion_matrix(y_holdout, preds, labels=[0, 1])
            conf_matrix = {
                "true_negative":  int(cm[0][0]),
                "false_positive": int(cm[0][1]),
                "false_negative": int(cm[1][0]),
                "true_positive":  int(cm[1][1]),
            }
            report    = classification_report(y_holdout, preds, output_dict=True, labels=[0, 1], zero_division=0)
            report_dict = {
                "precision_win":  round(report.get("1", {}).get("precision", 0), 3),
                "recall_win":     round(report.get("1", {}).get("recall",    0), 3),
                "f1_win":         round(report.get("1", {}).get("f1-score",  0), 3),
                "precision_loss": round(report.get("0", {}).get("precision", 0), 3),
                "recall_loss":    round(report.get("0", {}).get("recall",    0), 3),
                "f1_loss":        round(report.get("0", {}).get("f1-score",  0), 3),
            }
        except Exception as e:
            log.warning("Metrics calculation failed: %s", e)

    feature_names      = get_feature_names()
    base_model         = model
    importances        = base_model.feature_importances_
    feature_importance = sorted(
        zip(feature_names, importances),
        key     = lambda x: x[1],
        reverse = True,
    )

    top_features = [
        {"feature": f, "importance": int(i)}
        for f, i in feature_importance[:10]
    ]

    zero_importance_features = [
        f for f, i in feature_importance if i == 0
    ]

    shap_top_features = []
    try:
        import shap
        explainer   = shap.TreeExplainer(base_model)
        shap_values = explainer.shap_values(X)
        if isinstance(shap_values, list):
            shap_matrix = shap_values[1]
        else:
            shap_matrix = shap_values
        shap_mean = np.abs(shap_matrix).mean(axis=0)
        shap_importance = sorted(
            zip(feature_names, shap_mean.tolist()),
            key     = lambda x: x[1],
            reverse = True,
        )
        shap_top_features = [
            {"feature": f, "shap_mean": round(float(v), 6)}
            for f, v in shap_importance[:10]
        ]
    except ImportError:
        pass
    except Exception as e:
        log.warning("SHAP failed: %s", e)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(final_model, f)

    meta = {
        "trained_at":               datetime.now(timezone.utc).isoformat(),
        "samples":                  len(X_train),
        "evaluation_samples":       len(X_holdout),
        "wins":                     int(y_train.sum()),
        "losses":                   int((y_train == 0).sum()),
        "win_rate":                 round(float(y_train.mean()) * 100, 1),
        "features":                 len(feature_names),
        "cv_auc":                   cv_score,
        "cv_std":                   cv_std,
        "cv_method":                "TimeSeriesSplit",
        "holdout_auc":              auc_score,
        "precision":                precision,
        "recall":                   recall,
        "f1":                       f1,
        "confusion_matrix":         conf_matrix,
        "calibrated":               False,
        "evaluation_method":        "chronological_untouched_last_20_percent",
        "top_features":             top_features,
        "zero_importance_features": zero_importance_features,
        "shap_top_features":        shap_top_features,
        "classification":           report_dict,
        "threshold":                0.50,
    }

    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    log.info(
        "Model saved — samples:%s win_rate:%s%% cv_auc:%s precision:%s recall:%s f1:%s",
        len(X), meta["win_rate"], cv_score, precision, recall, f1,
    )

    _notify_training_complete(meta)

    return {
        "success":                  True,
        "samples":                  len(X_train),
        "evaluation_samples":       len(X_holdout),
        "wins":                     int(y_train.sum()),
        "losses":                   int((y_train == 0).sum()),
        "win_rate":                 meta["win_rate"],
        "cv_auc":                   cv_score,
        "cv_std":                   cv_std,
        "holdout_auc":              auc_score,
        "precision":                precision,
        "recall":                   recall,
        "f1":                       f1,
        "confusion_matrix":         conf_matrix,
        "calibrated":               meta["calibrated"],
        "top_features":             top_features,
        "zero_importance_features": zero_importance_features,
        "shap_top_features":        shap_top_features,
        "model_path":               MODEL_PATH,
    }


def retrain_if_needed() -> bool:
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
                SignalModel.factor_scores.isnot(None),
            ).count()
        new_trades = current_count - last_samples
        if new_trades >= 25:
            log.info("Retraining triggered — %s new trades since last train", new_trades)
            result = train_model()
            return result.get("success", False)
        return False
    except Exception as e:
        log.error("Retrain check error: %s", e)
        return False


def _notify_training_complete(meta: dict):
    try:
        import asyncio
        from alerts.telegram import send

        top      = meta.get("top_features",      [])[:3]
        shap_top = meta.get("shap_top_features", [])[:3]

        top_str = "\n".join(
            f"  `{f['feature']}` — `{f['importance']}`"
            for f in top
        )

        shap_str = ""
        if shap_top:
            shap_str = "\n*Top by SHAP:*\n" + "\n".join(
                f"  `{f['feature']}` — `{f['shap_mean']}`"
                for f in shap_top
            )

        cm = meta.get("confusion_matrix", {})
        cm_str = ""
        if cm:
            tp = cm.get("true_positive",  0)
            tn = cm.get("true_negative",  0)
            fp = cm.get("false_positive", 0)
            fn = cm.get("false_negative", 0)
            cm_str = (
                f"\n*Confusion Matrix:*\n"
                f"  TP:`{tp}` FP:`{fp}`\n"
                f"  FN:`{fn}` TN:`{tn}`"
            )

        asyncio.create_task(send(
            f"🤖 *LightGBM Model Trained*\n\n"
            f"Samples:    `{meta['samples']}`\n"
            f"Win Rate:   `{meta['win_rate']}%`\n"
            f"CV AUC:     `{meta.get('cv_auc', '--')}` ± `{meta.get('cv_std', '--')}`\n"
            f"Train AUC:  `{meta.get('train_auc', '--')}`\n"
            f"Precision:  `{meta.get('precision', '--')}`\n"
            f"Recall:     `{meta.get('recall', '--')}`\n"
            f"F1:         `{meta.get('f1', '--')}`\n"
            f"Calibrated: `{'Yes' if meta.get('calibrated') else 'No'}`\n\n"
            f"*Top Features:*\n{top_str}"
            f"{shap_str}"
            f"{cm_str}"
        ))
    except Exception as e:
        log.error("Training notification error: %s", e)


def get_model_meta() -> dict:
    try:
        if not os.path.exists(META_PATH):
            return {}
        with open(META_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def get_validation_report() -> dict:
    meta = get_model_meta()
    if not meta:
        return {"error": "No model trained yet"}
    return {
        "trained_at":       meta.get("trained_at"),
        "samples":          meta.get("samples",    0),
        "win_rate":         meta.get("win_rate",   0),
        "cv_auc":           meta.get("cv_auc"),
        "cv_std":           meta.get("cv_std"),
        "train_auc":        meta.get("train_auc"),
        "precision":        meta.get("precision"),
        "recall":           meta.get("recall"),
        "f1":               meta.get("f1"),
        "confusion_matrix": meta.get("confusion_matrix"),
        "calibrated":       meta.get("calibrated", False),
        "top_features":     meta.get("top_features",     []),
        "shap_top_features":meta.get("shap_top_features",[]),
        "threshold":        meta.get("threshold",  0.50),
        "classification":   meta.get("classification",  {}),
    }
