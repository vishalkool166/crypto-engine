import json
import logging
import pandas as pd
import numpy as np
from database import SessionLocal, Signal as SignalModel, Trade as TradeModel

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

RAW_FEATURE_KEYS = [
    "c1_body_pct",
    "c1_upper_wick_pct",
    "c1_lower_wick_pct",
    "c1_close_position",
    "c1_body_atr_ratio",
    "c2_body_pct",
    "c2_upper_wick_pct",
    "c2_lower_wick_pct",
    "atr_pct",
    "volume_ratio",
    "dist_to_swing_high_pct",
    "dist_to_swing_low_pct",
    "pullback_depth_pct",
    "higher_highs",
    "higher_lows",
    "sweep_wick_atr",
    "sweep_vol_ratio",
    "sweep_age_hours",
    "sweep_intensity",
    "ob_touch_count",
    "ob_distance_pct",
    "ob_score",
    "ob_width_atr",
    "ema20_distance_pct",
    "ema50_distance_pct",
    "ema20_slope",
    "ema50_slope",
    "adx",
    "rsi",
    "btc_atr_pct",
    "btc_adx",
    "btc_rsi",
    "funding_rate",
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

ROLE_MAP = {
    "maker": 0,
    "taker": 1,
}


def build_dataset() -> tuple[pd.DataFrame, pd.Series] | tuple[None, None]:
    try:
        with SessionLocal() as db:
            signals = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"]),
                SignalModel.factor_scores.isnot(None)
            ).all()

            signal_ids = [s.id for s in signals]

            trades_map = {}
            if signal_ids:
                trades = db.query(TradeModel).filter(
                    TradeModel.signal_id.in_(signal_ids),
                    TradeModel.outcome.in_(["win", "loss"])
                ).all()
                trades_map = {t.signal_id: t for t in trades}

        if not signals:
            log.warning("No closed signals with factor scores found")
            return None, None

        snapshot_map = _load_snapshots(signal_ids)

        log.info("Building dataset from %s closed signals (%s with snapshots)",
                 len(signals), len(snapshot_map))

        rows   = []
        labels = []

        for s in signals:
            try:
                factor_scores = json.loads(s.factor_scores or "{}")
            except Exception:
                continue

            row = {}

            for key in FEATURE_KEYS:
                row[key] = float(factor_scores.get(key, 0))

            row["sweep_score"]  = float(s.sweep_score  or 0)
            row["retest_score"] = float(s.retest_score or 0)
            row["disp_score"]   = float(s.disp_score   or 0)
            row["btc_score"]    = float(s.btc_score     or 0)
            row["market_score"] = float(s.market_score  or 0)
            row["entry_score"]  = float(s.entry_score   or 0)
            row["score"]        = float(s.score         or 0)
            row["funding"]      = float(s.funding       or 0) * 100

            row["grade_encoded"]     = GRADE_MAP.get(s.grade, 0)
            row["regime_encoded"]    = REGIME_MAP.get(s.regime or "", 0)
            row["session_encoded"]   = SESSION_MAP.get(s.session or "", 0)
            row["direction_encoded"] = 1 if s.direction == "LONG" else -1

            snapshot = snapshot_map.get(s.id)
            if snapshot:
                raw = snapshot.get("raw_features", {})
                for key in RAW_FEATURE_KEYS:
                    row[key] = float(raw.get(key, 0) or 0)
            else:
                for key in RAW_FEATURE_KEYS:
                    row[key] = 0.0

            trade = trades_map.get(s.id)
            if trade:
                row["entry_role_encoded"]   = ROLE_MAP.get(trade.entry_role or "taker", 1)
                row["exit_role_encoded"]    = ROLE_MAP.get(trade.exit_role  or "taker", 1)
                row["slippage_entry_pct"]   = float(trade.slippage_entry_pct or 0)
                row["slippage_exit_pct"]    = float(trade.slippage_exit_pct  or 0)
                row["total_commission_pct"] = (
                    float(trade.total_commission or 0) /
                    float(trade.margin_used or 1) * 100
                )
                row["funding_fees_pct"] = (
                    float(trade.funding_fees_paid or 0) /
                    float(trade.margin_used or 1) * 100
                )
                row["tp1_hit"] = 1 if trade.tp1_hit else 0

                if trade.opened_at and trade.closed_at:
                    try:
                        opened = trade.opened_at
                        closed = trade.closed_at
                        if opened.tzinfo is None:
                            from datetime import timezone
                            opened = opened.replace(tzinfo=timezone.utc)
                        if closed.tzinfo is None:
                            from datetime import timezone
                            closed = closed.replace(tzinfo=timezone.utc)
                        hold_hours = (closed - opened).total_seconds() / 3600
                        row["hold_duration_hours"] = round(hold_hours, 2)
                    except Exception:
                        row["hold_duration_hours"] = 0.0
                else:
                    row["hold_duration_hours"] = 0.0

                net_pnl = float(trade.net_pnl or trade.pnl or 0)
                margin  = float(trade.margin_used or 1)
                row["net_pnl_pct"] = round(net_pnl / margin * 100, 4) if margin > 0 else 0.0

            else:
                row["entry_role_encoded"]   = 1
                row["exit_role_encoded"]    = 1
                row["slippage_entry_pct"]   = 0.0
                row["slippage_exit_pct"]    = 0.0
                row["total_commission_pct"] = 0.1
                row["funding_fees_pct"]     = 0.0
                row["tp1_hit"]              = 0
                row["hold_duration_hours"]  = 0.0
                row["net_pnl_pct"]          = 0.0

            rows.append(row)
            labels.append(1 if s.outcome == "win" else 0)

        if len(rows) < 10:
            log.warning("Not enough data: %s samples (need 10+)", len(rows))
            return None, None

        X = pd.DataFrame(rows)
        y = pd.Series(labels, name="outcome")

        X = X.fillna(0)

        raw_present = sum(
            1 for r in rows
            if any(r.get(k, 0) != 0 for k in RAW_FEATURE_KEYS)
        )

        log.info(
            "Dataset built: %s samples · %s features · wins:%s losses:%s · "
            "win_rate:%.1f%% · samples_with_raw_features:%s",
            len(X), X.shape[1], y.sum(), (y == 0).sum(),
            y.mean() * 100, raw_present
        )

        return X, y

    except Exception as e:
        log.error("Dataset build error: %s", e)
        return None, None


def _load_snapshots(signal_ids: list) -> dict:
    try:
        from database import SessionLocal, SignalSnapshot
        with SessionLocal() as db:
            snapshots = db.query(SignalSnapshot).filter(
                SignalSnapshot.signal_id.in_(signal_ids)
            ).all()

        result = {}
        for snap in snapshots:
            raw = {}
            if snap.raw_features_json:
                try:
                    raw = json.loads(snap.raw_features_json)
                except Exception:
                    raw = {}
            result[snap.signal_id] = {"raw_features": raw}

        return result

    except Exception as e:
        log.error("_load_snapshots error: %s", e)
        return {}


def get_feature_names() -> list:
    return (
        FEATURE_KEYS
        + RAW_FEATURE_KEYS
        + [
            "sweep_score", "retest_score", "disp_score",
            "btc_score", "market_score", "entry_score",
            "score", "funding",
            "grade_encoded", "regime_encoded",
            "session_encoded", "direction_encoded",
            "entry_role_encoded", "exit_role_encoded",
            "slippage_entry_pct", "slippage_exit_pct",
            "total_commission_pct", "funding_fees_pct",
            "tp1_hit", "hold_duration_hours", "net_pnl_pct",
        ]
    )


def get_signal_features(signal: dict, wconf: dict) -> dict | None:
    try:
        factors       = wconf.get("factors", [])
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

        for key in RAW_FEATURE_KEYS:
            row[key] = 0.0

        row["entry_role_encoded"]   = 1
        row["exit_role_encoded"]    = 1
        row["slippage_entry_pct"]   = 0.0
        row["slippage_exit_pct"]    = 0.0
        row["total_commission_pct"] = 0.1
        row["funding_fees_pct"]     = 0.0
        row["tp1_hit"]              = 0
        row["hold_duration_hours"]  = 0.0
        row["net_pnl_pct"]          = 0.0

        return row

    except Exception as e:
        log.error("Feature extraction error: %s", e)
        return None