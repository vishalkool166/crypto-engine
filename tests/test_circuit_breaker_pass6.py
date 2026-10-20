"""Bounded, read-only 4h circuit-breaker checks. No Redis/exchange calls."""
import sys
from types import ModuleType

import pandas as pd
import pytest

# The scanner imports large runtime services at module import time; our test
# inspects the pure documented circuit functions without starting those services.
from test_security_regression import extracted_function
from config import CIRCUIT_BREAKER_CONFIG


def checker():
    import logging
    return extracted_function('alerts/scanner.py', '_check_coin_circuit_breaker', {
        'CIRCUIT_BREAKER_CONFIG': CIRCUIT_BREAKER_CONFIG,
        'log': logging.getLogger(__name__),
    })


def two_closed_bars(previous=100.0, current=100.5):
    import datetime
    now = pd.Timestamp.now(tz='UTC')
    last_open = now.floor('4h') - pd.Timedelta(hours=4)
    return pd.DataFrame({'close': [previous, current]},
                        index=pd.DatetimeIndex([last_open-pd.Timedelta(hours=4), last_open]))


def test_four_hour_risk_checks_four_hour_candles_not_daily_ticker():
    check = checker()
    assert check('ETH', two_closed_bars()) is True
    assert check('ETH', two_closed_bars(100, 90)) is False
    assert check('ETH', two_closed_bars(100, 110)) is False


def test_missing_gap_stale_or_nonfinite_candles_block_signals():
    check = checker()
    assert check('ETH', None) is False
    assert check('ETH', two_closed_bars(100, float('nan'))) is False
    old = two_closed_bars()
    old.index = old.index - pd.Timedelta(days=2)
    assert check('ETH', old) is False
    gap = two_closed_bars()
    gap.index = pd.DatetimeIndex([gap.index[-1]-pd.Timedelta(hours=8),gap.index[-1]])
    assert check('ETH', gap) is False


def test_halt_snapshot_is_sticky_until_explicit_reset():
    resolve = extracted_function('alerts/scanner.py', '_resolve_circuit_level', {})
    assert resolve(3, None) == 3
    assert resolve(3, 0) == 3
    assert resolve(3, 4) == 4


def test_coin_specific_target_is_not_blocked_by_hardcoded_2r():
    from config import get_coin_config
    meets = extracted_function('alerts/scanner.py', '_meets_coin_rr', {
        'get_coin_config': get_coin_config,
    })
    assert meets('BNB', 1.5)
    assert meets('LTC', 1.5)
    assert meets('ETH', 2.0)
    assert not meets('ETH', 1.5)
    assert not meets('BNB', float('nan'))


def test_daily_stop_limit_is_fail_closed_and_not_in_memory():
    level = {'count': 0}
    count = lambda: level['count']
    size = extracted_function('alerts/scanner.py', '_get_portfolio_size_multiplier', {
        'CIRCUIT_BREAKER_CONFIG': CIRCUIT_BREAKER_CONFIG,
        '_get_portfolio_circuit_level': lambda: 0,
        '_get_daily_sl_count': count,
    })
    assert size() == 1.0
    level['count'] = 3
    assert size() == 0.0
    level['count'] = None
    assert size() == 0.0


@pytest.mark.parametrize('circuit_level, expected', [
    (0, 1.0),
    (1, CIRCUIT_BREAKER_CONFIG['size_mult_level1']),
    (2, CIRCUIT_BREAKER_CONFIG['size_mult_level2']),
    (3, CIRCUIT_BREAKER_CONFIG['size_mult_level3']),
    (4, CIRCUIT_BREAKER_CONFIG['size_mult_level4']),
    (5, CIRCUIT_BREAKER_CONFIG['size_mult_level5']),
    (6, 0.0),
])
def test_portfolio_circuit_levels_only_reduce_risk_and_halt_unknown_level(circuit_level, expected):
    make_size = extracted_function('alerts/scanner.py', '_get_portfolio_size_multiplier', {
        'CIRCUIT_BREAKER_CONFIG': CIRCUIT_BREAKER_CONFIG,
        '_get_portfolio_circuit_level': lambda: circuit_level,
        '_get_daily_sl_count': lambda: 0,
    })
    assert make_size() == expected
    assert expected <= 1.0


def test_periodic_circuit_level_resolution_never_lowers_a_halt():
    resolve = extracted_function('alerts/scanner.py', '_resolve_circuit_level', {})
    for current in range(6):
        for requested in (None, 0, 1):
            assert resolve(current, requested) >= current
