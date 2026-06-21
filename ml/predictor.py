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
        log.info(f"LightGBM model loaded from {MODEL_PATH}")
        return _model

    except Exception as e:
        log.error(f"Model load error: {e}")
        return None


def predict_win_probability(signal: dict, wconf: dict) -> float:
    """
    Predict win probability for a signal.
    Returns float 0.0 - 1.0.
    Returns 0.5 (neutral) if model not available.
    """
    model = _load_model()
    if model is None:
        return 0.5

    try:
        features = get_signal_features(signal, wconf)
        if features is None:
            return 0.5

        feature_names = get_feature_names()
        row = [features.get(f, 0) for f in feature_names]

        X    = pd.DataFrame([row], columns=feature_names)
        prob = float(model.predict_proba(X)[0][1])

        log.debug(
            f"ML prediction: {signal.get('coin', '--')} "
            f"grade:{signal.get('grade')} "
            f"prob:{prob:.3f}"
        )

        return round(prob, 4)

    except Exception as e:
        log.error(f"Prediction error: {e}")
        return 0.5


def is_ml_approved(signal: dict, wconf: dict, threshold: float = 0.65) -> tuple[bool, float]:
    """
    Check if signal passes ML filter.
    Returns (approved: bool, probability: float)
    """
    prob = predict_win_probability(signal, wconf)
    approved = prob >= threshold

    if not approved:
        log.info(
            f"ML filtered out: {signal.get('coin', '--')} "
            f"grade:{signal.get('grade')} "
            f"prob:{prob:.3f} < threshold:{threshold}"
        )
    else:
        log.info(
            f"ML approved: {signal.get('coin', '--')} "
            f"grade:{signal.get('grade')} "
            f"prob:{prob:.3f} >= threshold:{threshold}"
        )

    return approved, prob


def get_predictor_status() -> dict:
    """
    Returns current predictor status for health endpoint.
    """
    model_exists = os.path.exists(MODEL_PATH)

    if not model_exists:
        return {
            "model_loaded":  False,
            "model_path":    MODEL_PATH,
            "ready":         False,
            "message":       "Model not trained yet"
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
        "threshold":     meta.get("threshold", 0.65),
        "top_features":  meta.get("top_features", []),
        "message":       f"Model ready — {meta.get('samples', 0)} training samples"
    }