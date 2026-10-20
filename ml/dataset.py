"""Research-only dataset builder using recorded entry features and net outcomes.

Missing entry features are excluded, never filled using future prices. This
module is not part of the active signal decision path.
"""

import math
import numpy as np
import pandas as pd

FEATURES = ("score", "adx", "rsi", "vol_ratio")


def get_feature_names():
    return list(FEATURES)


def get_signal_features(signal, wconf=None):
    values = {k: signal.get(k) for k in FEATURES}
    if any(
        v is None or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values.values()
    ):
        return None
    return {k: float(v) for k, v in values.items()}


def build_dataset():
    import json
    from database import SessionLocal, Signal, Trade

    rows = []
    targets = []
    with SessionLocal() as db:
        records = (
            db.query(Signal, Trade)
            .join(Trade, Trade.signal_id == Signal.id)
            .filter(Trade.closed_at.isnot(None), Trade.net_pnl.isnot(None))
            .order_by(Signal.timestamp.asc())
            .all()
        )
        for signal, trade in records:
            try:
                trace = json.loads(signal.factor_scores or "{}")
                values = trace.get("entry_features", {})
                features = get_signal_features(values)
                if features is None:
                    continue
                rows.append([features[k] for k in FEATURES])
                targets.append(int(trade.net_pnl > 0))
            except (ValueError, TypeError):
                continue
    if not rows:
        return None, None
    return pd.DataFrame(rows, columns=FEATURES), np.asarray(targets)
