"""ML training uses fixed entry-time features and a chronological holdout."""
import sys
from types import ModuleType, SimpleNamespace

import pytest

from ml.dataset import FEATURE_NAMES, build_dataset, get_signal_features
from ml.trainer import chronological_split


def test_feature_vector_is_fixed_finite_and_contains_no_exit_outcomes():
    features = get_signal_features({
        'coin': 'ETH', 'direction': 'LONG', 'grade': 'A+', 'session': 'London',
        'regime': 'Trending', 'score': 82, 'sweep_score': 20,
        'risk_reward': 2.0, 'duration_hours': 99, 'outcome': 'win', 'mae': 10,
    }, {'drawdown_at_signal': 3.0})
    assert features is not None
    assert features['combined_score'] == 82
    assert features['drawdown_at_entry'] == 3
    assert features['coin_eth'] == 1
    assert features['grade_aplus'] == 1
    assert len(features) == len(FEATURE_NAMES)
    assert not {'outcome', 'duration_hours', 'mae', 'mfe', 'exit_price'} & set(FEATURE_NAMES)


def test_chronological_split_leaves_latest_rows_only_in_holdout():
    import pandas as pd
    X = pd.DataFrame({'x': list(range(10))})
    y = pd.Series([0, 1] * 5)
    x_train, x_holdout, y_train, y_holdout = chronological_split(X, y)
    assert x_train.x.tolist() == list(range(8))
    assert x_holdout.x.tolist() == [8, 9]
    assert len(y_train) == 8 and len(y_holdout) == 2
    with pytest.raises(ValueError):
        chronological_split(X, y.iloc[:-1])


def test_dataset_uses_closed_outcome_entry_features_and_net_pnl_label(monkeypatch):
    class Field:
        def in_(self, values): return ('in', tuple(values))
        def isnot(self, value): return ('not', value)
        def asc(self): return self

    rows = [
        SimpleNamespace(outcome='win', coin='BTC', direction='LONG', grade='A',
                        session='Asia', regime='trending', combined_score=70,
                        sweep_score=12, zone_score=10, trigger_score=8,
                        drawdown_at_entry=2, win_rate_at_entry=55, balance_at_open=1000,
                        day_of_week=1, hour_of_day=4, binance_net_pnl=None,
                        net_pnl=5, pnl=5, duration_hours=900),
        SimpleNamespace(outcome='loss', coin='ETH', direction='SHORT', grade='B',
                        session='New York', regime='ranging', combined_score=40,
                        sweep_score=2, zone_score=3, trigger_score=1,
                        drawdown_at_entry=1, win_rate_at_entry=45, balance_at_open=900,
                        day_of_week=2, hour_of_day=15, binance_net_pnl=-3,
                        net_pnl=1, pnl=1, duration_hours=0.1),
        SimpleNamespace(outcome='win', coin='SOL', direction='LONG', grade='A',
                        session='Asia', regime='trending', combined_score=80,
                        sweep_score=1, zone_score=1, trigger_score=1,
                        drawdown_at_entry=0, win_rate_at_entry=50, balance_at_open=900,
                        day_of_week=2, hour_of_day=15, binance_net_pnl=None,
                        net_pnl=0, pnl=0, duration_hours=1),
    ]
    model = type('TradeOutcome', (), {name: Field() for name in (
        'outcome', 'recorded_at', 'id', 'coin', 'direction', 'grade', 'session', 'regime',
        'combined_score', 'sweep_score', 'zone_score', 'trigger_score',
        'drawdown_at_entry', 'win_rate_at_entry', 'balance_at_open', 'day_of_week', 'hour_of_day')})

    class Query:
        def filter(self, *args): return self
        def order_by(self, *args): return self
        def all(self): return rows

    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def query(self, _): return Query()

    fake = ModuleType('database')
    fake.TradeOutcome = model
    fake.SessionLocal = Session
    monkeypatch.setitem(sys.modules, 'database', fake)

    X, y = build_dataset()
    assert len(X) == 2
    assert y.tolist() == [1, 0]
    assert X.iloc[0]['coin_btc'] == 1
    assert 'duration_hours' not in X.columns
