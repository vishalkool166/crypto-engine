import os
import pickle
import logging
import numpy as np
import pandas as pd
from ml.dataset import get_signal_features, get_feature_names

log = logging.getLogger(__name__)

MODEL_PATH = "ml/models/lgbm_model.pkl"

_model       = None
_model_mtime = 0.0


def _load_model():
    global _model, _model_mtime

    if not os.path.exists(MODEL_PATH):
        return None

    try:
        mtime = os.path.getmtime(MODEL_PATH)
        if _model is not None and mtime == _model_mtime:
            return _model

        with open(MODEL_PATH, "rb") as f:
            _model = pickle.load(f)
        _model_mtime = mtime
        log.info("LightGBM model loaded from %s", MODEL_PATH)
        return _model

    except Exception as e:
        log.error("Model load error: %s", e)
        return None


def predict_win_probability(signal: dict, wconf: dict) -> float:
    model = _load_model()

    if model is None:
        return 0.5

    try:
        features = get_signal_features(signal, wconf)
        if features is None:
            return 0.5

        feature_names = get_feature_names()
        row  = [features.get(f, 0) for f in feature_names]
        X    = pd.DataFrame([row], columns=feature_names)
        prob = float(model.predict_proba(X)[0][1])

        log.debug(
            "ML prediction: %s grade:%s prob:%.3f",
            signal.get("coin", "--"),
            signal.get("grade"),
            prob,
        )

        return round(prob, 4)

    except Exception as e:
        log.error("Prediction error: %s", e)
        return 0.5


def is_ml_approved(signal: dict, wconf: dict, threshold: float = 0.50) -> tuple[bool, float]:
    prob     = predict_win_probability(signal, wconf)
    approved = prob >= threshold

    if not approved:
        log.info(
            "ML scored low: %s grade:%s prob:%.3f threshold:%.2f",
            signal.get("coin", "--"),
            signal.get("grade"),
            prob,
            threshold,
        )
    else:
        log.info(
            "ML scored positive: %s grade:%s prob:%.3f threshold:%.2f",
            signal.get("coin", "--"),
            signal.get("grade"),
            prob,
            threshold,
        )

    return approved, prob


def get_predictor_status() -> dict:
    model_exists = os.path.exists(MODEL_PATH)

    if not model_exists:
        return {
            "model_loaded":  False,
            "model_path":    MODEL_PATH,
            "ready":         False,
            "message":       "No model yet — scoring neutral 0.5 until 50 trades collected",
        }

    model = _load_model()

    from ml.trainer import get_model_meta
    meta = get_model_meta()

    return {
        "model_loaded":  model is not None,
        "model_path":    MODEL_PATH,
        "ready":         model is not None,
        "trained_at":    meta.get("trained_at", "--"),
        "samples":       meta.get("samples", 0),
        "win_rate":      meta.get("win_rate", 0),
        "cv_auc":        meta.get("cv_auc", "--"),
        "threshold":     meta.get("threshold", 0.50),
        "top_features":  meta.get("top_features", []),
        "message":       f"Model active — {meta.get('samples', 0)} training samples · AUC:{meta.get('cv_auc', '--')}",
    }