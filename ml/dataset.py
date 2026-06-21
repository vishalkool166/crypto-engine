import json
import logging
import pandas as pd
import numpy as np
from database import SessionLocal, Signal as SignalModel

log = logging.getLogger(__name__)

FEATURE_KEYS = [
    "liquidity_sweep",
    "retest_confirmation",
    "displacement",
    "market_regime",
    "weekly_filter",
    "market_structure",
    "session_timing",
    "btc_alignment",
    "oi_behavior",
    "volume_expansion",
    "funding_extreme",
    "rsi_divergence",
    "atr_volatility",
    "rsi_context",
    "macd_histogram",
    "order_blocks",
]

REGIME_MAP = {
    "TRENDING BULLISH":  2,
    "TRENDING BEARISH":  1,
    "RANGING":           0,
    "CHOPPY":           -1,
}

SESSION_MAP = {
    "London/NY Overlap": 3,
    "New York Session":  2,
    "London Session":    2,
    "Asian Session":     0,
    "Off Hours":         0,
}

GRADE_MAP = {
    "A+": 3,
    "A":  2,
    "B":  1,
    "C":  0,
    "F": -1,
}


def build_dataset() -> tuple[pd.DataFrame, pd.Series] | tuple[None, None]:
    """
    Build feature matrix X and label vector y from Signal table.
    Only includes closed signals with win/loss outcome.
    Returns (X, y) or (None, None) if not enough data.
    """
    try:
        with SessionLocal() as db:
            signals = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"]),
                SignalModel.factor_scores.isnot(None)
            ).all()

        if not signals:
            log.warning("No closed signals with factor scores found")
            return None, None

        log.info(f"Building dataset from {len(signals)} closed signals")

        rows   = []
        labels = []

        for s in signals:
            try:
                factor_scores = json.loads(s.factor_scores or "{}")
            except Exception:
                continue

            row = {}

            # Factor scores — 16 features
            for key in FEATURE_KEYS:
                row[key] = float(factor_scores.get(key, 0))

            # Additional numeric features
            row["sweep_score"]  = float(s.sweep_score  or 0)
            row["retest_score"] = float(s.retest_score or 0)
            row["disp_score"]   = float(s.disp_score   or 0)
            row["btc_score"]    = float(s.btc_score     or 0)
            row["market_score"] = float(s.market_score  or 0)
            row["entry_score"]  = float(s.entry_score   or 0)
            row["score"]        = float(s.score         or 0)
            row["funding"]      = float(s.funding       or 0) * 100

            # Categorical features encoded
            row["grade_encoded"]   = GRADE_MAP.get(s.grade, 0)
            row["regime_encoded"]  = REGIME_MAP.get(s.regime or "", 0)
            row["session_encoded"] = SESSION_MAP.get(s.session or "", 0)
            row["direction_encoded"] = 1 if s.direction == "LONG" else -1

            rows.append(row)
            labels.append(1 if s.outcome == "win" else 0)

        if len(rows) < 10:
            log.warning(f"Not enough data: {len(rows)} samples (need 10+)")
            return None, None

        X = pd.DataFrame(rows)
        y = pd.Series(labels, name="outcome")

        # Fill any NaN with 0
        X = X.fillna(0)

        log.info(
            f"Dataset built: {len(X)} samples · "
            f"{X.shape[1]} features · "
            f"wins:{y.sum()} losses:{(y==0).sum()} · "
            f"win_rate:{y.mean()*100:.1f}%"
        )

        return X, y

    except Exception as e:
        log.error(f"Dataset build error: {e}")
        return None, None


def get_feature_names() -> list:
    return FEATURE_KEYS + [
        "sweep_score", "retest_score", "disp_score",
        "btc_score", "market_score", "entry_score",
        "score", "funding",
        "grade_encoded", "regime_encoded",
        "session_encoded", "direction_encoded"
    ]


def get_signal_features(signal: dict, wconf: dict) -> dict | None:
    """
    Extract features from a live signal for ML prediction.
    Same feature engineering as build_dataset().
    """
    try:
        factors = wconf.get("factors", [])
        factor_scores = {f["key"]: f["earned"] for f in factors}

        row = {}

        for key in FEATURE_KEYS:
            row[key] = float(factor_scores.get(key, 0))

        row["sweep_score"]  = float(signal.get("sweep_score",  0))
        row["retest_score"] = float(signal.get("retest_score", 0) if signal.get("retest_score") else 0)
        row["disp_score"]   = float(signal.get("disp_score",   0))
        row["btc_score"]    = float(wconf.get("btc_score",     0))
        row["market_score"] = float(wconf.get("market_score",  0))
        row["entry_score"]  = float(wconf.get("entry_score",   0))
        row["score"]        = float(signal.get("score",        0))
        row["funding"]      = float(signal.get("funding",      0)) * 100

        row["grade_encoded"]     = GRADE_MAP.get(signal.get("grade", "F"), 0)
        row["regime_encoded"]    = 0
        row["session_encoded"]   = 0
        row["direction_encoded"] = 1 if signal.get("direction") == "LONG" else -1

        return row

    except Exception as e:
        log.error(f"Feature extraction error: {e}")
        return None