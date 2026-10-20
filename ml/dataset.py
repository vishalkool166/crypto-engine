"""Chronological, entry-time-only ML dataset construction.

Features exclude trade outcomes, exit prices, duration, MAE/MFE, and any other
post-entry values. The model remains disabled unless separately enabled by
configuration and sufficient closed outcomes exist.
"""
from __future__ import annotations

import math

import pandas as pd


NUMERIC_FEATURES = (
    'combined_score', 'sweep_score', 'zone_score', 'trigger_score',
    'drawdown_at_entry', 'win_rate_at_entry', 'daily_pnl_at_entry',
    'open_trades_at_entry', 'balance_at_open', 'day_of_week', 'hour_of_day',
    'risk_reward',
)
GRADE_FEATURES = ('grade_aplus', 'grade_a', 'grade_b')
DIRECTION_FEATURES = ('direction_long',)
SESSION_FEATURES = ('session_asia', 'session_london', 'session_overlap', 'session_new_york', 'session_off_hours')
REGIME_FEATURES = ('regime_trending', 'regime_ranging', 'regime_choppy', 'regime_volatile')
COIN_FEATURES = tuple(f'coin_{coin.lower()}' for coin in (
    'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'AVAX', 'LINK',
    'DOT', 'LTC', 'BCH', 'ATOM', 'UNI', 'APT', 'NEAR', 'SUI', 'ARB',
))
FEATURE_NAMES = NUMERIC_FEATURES + GRADE_FEATURES + DIRECTION_FEATURES + SESSION_FEATURES + REGIME_FEATURES + COIN_FEATURES


def get_feature_names() -> list[str]:
    return list(FEATURE_NAMES)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _number(value, default=0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else float(default)
    except (TypeError, ValueError, OverflowError):
        return float(default)


def get_signal_features(signal: dict, wconf: dict | None = None) -> dict[str, float] | None:
    """Return a fixed finite feature vector from pre-entry signal context."""
    if not isinstance(signal, dict):
        return None
    wconf = wconf if isinstance(wconf, dict) else {}
    features = {
        'combined_score': _number(signal.get('combined_score', signal.get('score'))),
        'sweep_score': _number(signal.get('sweep_score')),
        'zone_score': _number(signal.get('zone_score')),
        'trigger_score': _number(signal.get('trigger_score')),
        'drawdown_at_entry': _number(signal.get('drawdown_at_entry', wconf.get('drawdown_at_signal'))),
        'win_rate_at_entry': _number(signal.get('win_rate_at_entry', wconf.get('win_rate_at_signal'))),
        'daily_pnl_at_entry': _number(signal.get('daily_pnl_at_entry', wconf.get('daily_pnl_at_signal'))),
        'open_trades_at_entry': _number(signal.get('open_trades_at_entry', wconf.get('open_trades_at_signal'))),
        'balance_at_open': _number(signal.get('balance_at_open', wconf.get('balance_at_signal'))),
        'day_of_week': _number(signal.get('day_of_week')),
        'hour_of_day': _number(signal.get('hour_of_day')),
        'risk_reward': _number(signal.get('risk_reward', signal.get('rr1'))),
    }
    grade = str(signal.get('grade') or '').upper()
    features.update({name: float(grade == label) for name, label in (
        ('grade_aplus', 'A+'), ('grade_a', 'A'), ('grade_b', 'B'))})
    features['direction_long'] = float(str(signal.get('direction') or '').upper() == 'LONG')
    session = str(signal.get('session') or '').lower()
    features.update({
        'session_asia': float(session == 'asia'),
        'session_london': float(session == 'london'),
        'session_overlap': float('overlap' in session),
        'session_new_york': float(session in ('new york', 'ny')),
        'session_off_hours': float(session in ('off hours', 'off_hours')),
    })
    regime = str(signal.get('regime') or '').lower()
    features.update({f'regime_{label}': float(label in regime) for label in ('trending', 'ranging', 'choppy', 'volatile')})
    coin = str(signal.get('coin') or '').upper()
    features.update({name: float(name == f'coin_{coin.lower()}') for name in COIN_FEATURES})
    return features


def build_dataset():
    """Load closed outcomes in timestamp order; return (X, y) or (None, None)."""
    try:
        from database import SessionLocal, TradeOutcome
        with SessionLocal() as db:
            rows = (db.query(TradeOutcome)
                    .filter(TradeOutcome.outcome.in_(['win', 'loss']),
                            TradeOutcome.recorded_at.isnot(None))
                    .order_by(TradeOutcome.recorded_at.asc(), TradeOutcome.id.asc())
                    .all())
        examples, labels = [], []
        for row in rows:
            # Outcome and exit-only fields are deliberately not passed to feature extraction.
            features = get_signal_features({
                'coin': _get(row, 'coin'), 'direction': _get(row, 'direction'),
                'grade': _get(row, 'grade'), 'session': _get(row, 'session'),
                'regime': _get(row, 'regime'), 'combined_score': _get(row, 'combined_score'),
                'sweep_score': _get(row, 'sweep_score'), 'zone_score': _get(row, 'zone_score'),
                'trigger_score': _get(row, 'trigger_score'),
                'drawdown_at_entry': _get(row, 'drawdown_at_entry'),
                'win_rate_at_entry': _get(row, 'win_rate_at_entry'),
                'balance_at_open': _get(row, 'balance_at_open'),
                'day_of_week': _get(row, 'day_of_week'), 'hour_of_day': _get(row, 'hour_of_day'),
            })
            pnl = _get(row, 'binance_net_pnl')
            if pnl is None:
                pnl = _get(row, 'net_pnl', _get(row, 'pnl'))
            pnl = _number(pnl, float('nan'))
            if features is None or not math.isfinite(pnl) or pnl == 0:
                continue
            examples.append([features[name] for name in FEATURE_NAMES])
            labels.append(int(pnl > 0))
        if not examples:
            return None, None
        return pd.DataFrame(examples, columns=FEATURE_NAMES), pd.Series(labels, dtype='int64')
    except Exception:
        return None, None
