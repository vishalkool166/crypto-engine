"""Contract tests for shared market-session and historical-report behavior."""
from datetime import datetime, timedelta, timezone
import sys
import types

import pandas as pd
import pytest

from engines.core.sessions import session_at, session_matches
from backtest.engine import _session_matches, _summary, run_backtest


@pytest.mark.parametrize('hour,expected', [
    (0, 'Asia'), (7, 'Asia'), (8, 'London'), (12, 'London'),
    (13, 'London/NY Overlap'), (16, 'London/NY Overlap'),
    (17, 'New York'), (20, 'New York'), (21, 'Off Hours'), (23, 'Off Hours'),
])
def test_utc_session_boundaries(hour, expected):
    assert session_at(datetime(2025, 7, 4, hour, tzinfo=timezone.utc)) == expected


def test_session_timezone_normalization_and_aware_enforcement():
    ts = datetime(2025, 7, 4, 18, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert session_at(ts) == 'London'
    assert session_matches('london', ts)
    with pytest.raises(ValueError, match='timezone-aware'):
        session_at(datetime(2025, 7, 4, 12))


@pytest.mark.parametrize('label,hours,accepted', [
    ('asia', [0, 7], True), ('asia', [8, 16, 19, 23], False),
    ('london', [8, 12, 13, 16], True), ('london', [0, 17, 21], False),
    ('ny', [13, 16, 17, 20], True), ('ny', [0, 8, 21], False),
    ('all', [0, 8, 13, 17], True), ('all', [21, 23], False),
    ('garbage', [12], False),
])
def test_session_match_policy(label, hours, accepted):
    for hour in hours:
        ts = datetime(2025, 7, 4, hour, tzinfo=timezone.utc)
        assert session_matches(label, ts) is accepted


def test_coin_backtest_session_uses_shared_policy():
    from config import COIN_CONFIG
    for coin, config in COIN_CONFIG.items():
        for hour in (0, 7, 8, 12, 13, 16, 17, 20, 21, 23):
            ts = pd.Timestamp(f'2025-07-04T{hour:02d}:00:00Z')
            assert _session_matches(coin, ts) == session_matches(config['session'], ts)


def test_net_pnl_drives_trade_win_count_not_exit_label():
    result = _summary([{'pnl': -2}, {'pnl': 3}, {'pnl': 0}], 1000)
    assert result['wins'] == 1
    assert result['losses'] == 1
    assert result['win_rate'] == pytest.approx(33.33)
    assert result['expectancy'] == pytest.approx(1 / 3, abs=1e-4)


def test_research_dataset_end_enforces_holding_time_embargo(monkeypatch):
    # If there is insufficient observation time beyond signal_start, even an
    # otherwise perfect setup must not be evaluated as a profitable timeout.
    indicator_module = types.ModuleType('engines.core.indicators')
    def forbidden(*args, **kwargs):
        raise AssertionError('No complete observation horizon exists')
    indicator_module.get_indicators = forbidden
    monkeypatch.setitem(sys.modules, 'engines.core.indicators', indicator_module)
    start = pd.Timestamp('2025-01-01', tz='UTC')
    candles = lambda freq, n: pd.DataFrame(
        {'open': 100.0, 'high': 101.0, 'low': 99.0, 'close': 100.0, 'volume': 1000.0},
        index=pd.date_range(start, periods=n, freq=freq))
    four = candles('4h', 320)
    one = candles('1h', 1280)
    result = run_backtest('ETH', df_4h=four, df_1h=one,
                          persist=False, signal_start='2025-02-22')
    assert result['total_trades'] == 0
    assert result['total_signals'] == 0
    assert result['error'] == 'No completed trades in the sample'


def test_legacy_report_expectancy_uses_net_pnl(monkeypatch):
    import backtest.report as report
    monkeypatch.setattr(report, '_save_to_db', lambda *a, **k: None)
    trades = [
        {'outcome': 'win', 'pnl': -4.0, 'date': '2025-01-01', 'grade': 'A',
         'tp1_hit': True, 'tp2_hit': False},
        {'outcome': 'win', 'pnl': 6.0, 'date': '2025-01-02', 'grade': 'A+',
         'tp1_hit': True, 'tp2_hit': False},
    ]
    result = report.build_report('ETH', trades, [], 1000, 1002)
    assert result['wins'] == result['losses'] == 1
    assert result['win_rate'] == 50.0
    assert result['expectancy'] == 1.0
    assert result['profit_factor'] == 1.5
    assert result['max_drawdown'] == pytest.approx(0.4)
