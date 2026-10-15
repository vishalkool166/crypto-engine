"""P0/P1 regression tests; zero financial/network side effects."""
from __future__ import annotations
import math
import sys
import types

import pandas as pd
import pytest

from engines.risk.calculator import calculate as risk
from engines.trend.direction import detect as trend
from engines.scoring.scorer import score
from engines.regime.detector import detect as regime


def test_bad_risk_values_never_produce_executable_trades():
    valid = dict(direction='LONG', entry=100., swing_level=99., atr=1., coin='ETH')
    for name, values in {
        'entry': [0, -1, float('nan'), float('inf')],
        'atr': [0, -1, float('nan'), float('inf')],
        'swing_level': [0, -1, float('nan'), float('inf')],
        'direction': ['HOLD', 'NEUTRAL', ''],
        'rr1': [-1, 0, float('nan'), float('inf')],
        'rr2': [-1, 0, float('nan'), float('inf')],
    }.items():
        for value in values:
            assert not risk(**{**valid, name: value}).valid, (name, value)


def test_invalid_short_negative_target_prevented():
    # Huge RR for otherwise valid short must not yield negative target.
    trade = risk(direction='SHORT', entry=1.0, swing_level=1.03,
                 atr=.01, coin='SOL', rr1=30)
    assert not trade.valid
    assert trade.reason == 'invalid_target_price'


def test_nan_adx_and_broken_ema_never_pass_trend():
    base = {'price': 100., 'ema20': 110., 'ema50': 105., 'ema200': 90., 'adx': 35.}
    for field in ('price', 'ema20', 'ema50', 'ema200', 'adx'):
        for value in (float('nan'), float('inf'), -1):
            assert not trend({**base, field: value}, 'ETH', record_rejection=False).passed


def test_corrupt_regime_never_returns_tradeable_condition():
    for values in ({'price': 0., 'atr': 1., 'adx': 25.},
                   {'price': 100., 'atr': float('nan'), 'adx': 25.},
                   {'price': 100., 'atr': 1., 'adx': float('nan')},
                   {'price': 100., 'atr': 1., 'adx': -1.}):
        result = regime(values)
        assert result.is_volatile and result.size_mult == 0


def test_invalid_scoring_is_untradeable():
    for inputs in ((float('nan'), 45., 2., 'LONG'),
                   (25., float('inf'), 2., 'LONG'),
                   (25., 45., float('nan'), 'LONG'),
                   (25., 150., 2., 'LONG'),
                   (25., 45., 2., 'NEUTRAL')):
        s = score(*inputs, regime='trending')
        assert s.grade == 'F' and s.total == 0


def test_nonexistent_coin_would_not_gain_fake_trading_quality():
    assert not risk('NEUTRAL', 100, 99, 1).valid


def test_strict_date_boundaries_reject_future_overlapping_and_short_samples():
    from backtest.walkforward import validate_dates
    validate_dates('2023-01-01', '2025-01-01', '2026-08-01')
    for start, split, end in (
        ('2025-02-01', '2025-01-01', '2026-01-01'),
        ('2025-01-01', '2025-03-01', '2025-08-01'),
        ('2024-01-01', '2025-01-01', '2025-02-01'),
        ('2024-01-01', '2025-01-01', '2035-01-01'),
    ):
        with pytest.raises(ValueError):
            validate_dates(start, split, end)


def test_training_selection_cannot_read_holdout_metrics(monkeypatch, tmp_path):
    from backtest import walkforward
    from config import COIN_CONFIG
    original = COIN_CONFIG['ETH']
    training_arms = []
    holdout_arms = []
    def fake_evaluate(coin, data_dir, **kwargs):
        variant = COIN_CONFIG['ETH']
        # Shared reference wins training, while original wins holdout.
        training = kwargs['signal_start'] == '2023-01-01'
        if training:
            training_arms.append(variant['tp'])
            score_value = 4.0 if variant['tp'] == 2.0 else 1.0
        else:
            holdout_arms.append(variant['tp'])
            score_value = -4.0 if variant['tp'] == 2.0 else 10.0
        return {'total_trades': 60, 'total_signals': 100,
                'expectancy': score_value, 'profit_factor': 2 if score_value > 0 else .5,
                'funding_modeled': True}
    monkeypatch.setattr(walkforward, 'evaluate', fake_evaluate)
    result = walkforward.audit_coin('ETH', tmp_path, '2023-01-01', '2025-01-01', '2026-08-01')
    assert len(training_arms) == 6
    assert len(holdout_arms) == 1
    assert result['training_selected'] in walkforward.variants('ETH')
    assert result['assessment'] == 'NO_VERIFIED_EDGE'
    assert COIN_CONFIG['ETH'] is original


def test_no_positive_training_sample_defaults_to_frozen_config(monkeypatch, tmp_path):
    from backtest import walkforward
    observed = []
    def fake_evaluate(coin, data_dir, **kwargs):
        from config import COIN_CONFIG
        observed.append(COIN_CONFIG[coin]['tp'])
        return {'total_trades': 3, 'expectancy': 10, 'profit_factor': 12,
                'funding_modeled': True}
    monkeypatch.setattr(walkforward, 'evaluate', fake_evaluate)
    result = walkforward.audit_coin('SOL', tmp_path, '2023-01-01', '2025-01-01', '2026-08-01')
    assert result['training_selected'] == 'configured'
    assert result['assessment'] == 'NO_VERIFIED_EDGE'
    assert observed[-1] == 3.5


@pytest.mark.asyncio
async def test_missing_binance_exchange_rules_raises_not_permissive_fallback(monkeypatch):
    from trade import exchange
    async def broken(*a, **kw):
        raise ConnectionError('market metadata unavailable')
    monkeypatch.setattr(exchange, '_get', broken)
    with pytest.raises(RuntimeError, match='blocking order'):
        await exchange.get_symbol_precision('ETH')


def test_position_db_failure_blocks_trading():
    import logging
    from test_security_regression import extracted_function
    def broken():
        raise RuntimeError('db down')
    subject = extracted_function('trade/executor.py', 'has_open_trade', {
        'get_session': broken,
        'log': logging.getLogger(__name__),
    })
    assert subject('ETH') is True


@pytest.mark.asyncio
async def test_position_exchange_failure_blocks_trading():
    import logging
    from test_security_regression import extracted_function
    async def broken():
        raise RuntimeError('exchange unavailable')
    subject = extracted_function('trade/executor.py', 'has_open_trade_or_position', {
        'has_open_trade': lambda coin: False,
        'get_positions': broken,
        'log': logging.getLogger(__name__),
    })
    assert await subject('ETH') is True


def test_manifest_coverage_rejects_missing_tail_and_sparse_funding():
    from backtest.research import _verify_manifest_times
    start = pd.Timestamp('2025-01-01', tz='UTC')
    end = start + pd.Timedelta(days=2)
    manifest = {'start': str(start), 'end_exclusive': str(end)}
    d4 = pd.DataFrame({'close': 1.}, index=pd.date_range(start, end, freq='4h', inclusive='left'))
    d1 = pd.DataFrame({'close': 1.}, index=pd.date_range(start, end, freq='1h', inclusive='left'))
    funding = pd.DataFrame({'funding_rate': 0.}, index=pd.date_range(start + pd.Timedelta(hours=8), end,
                                               freq='8h', inclusive='left'))
    _verify_manifest_times('ETH', manifest, d4, d1, funding)
    with pytest.raises(ValueError, match='does not cover'):
        _verify_manifest_times('ETH', manifest, d4.iloc[:-1], d1, funding)
    with pytest.raises(ValueError, match='funding settlement'):
        _verify_manifest_times('ETH', manifest, d4, d1, funding.iloc[:1])


def test_backtest_boundaries_do_not_trade_on_incomplete_holdout(monkeypatch):
    from backtest.engine import run_backtest
    # Regression: date boundaries are accepted and full holding-time embargo
    # prevents a signal near the fold edge from being scored as an exit.
    import sys, types
    ind_mod = types.ModuleType('engines.core.indicators')
    def indicators(frame, timeframe='4h'):
        if timeframe == '1h':
            return {'rsi': 42.}
        return {'price': 100., 'ema20': 103., 'ema50': 101., 'ema200': 95.,
                'adx': 35., 'atr': 1., 'vol_ratio': 2.,
                'swing_low': 99.5, 'swing_high': 101.5}
    ind_mod.get_indicators = indicators
    monkeypatch.setitem(sys.modules, 'engines.core.indicators', ind_mod)
    idx = pd.date_range('2025-01-01', periods=340, freq='4h', tz='UTC')
    d4 = pd.DataFrame({'open': 100., 'high': 105., 'low': 99.5,
                       'close': 100., 'volume': 10.}, index=idx)
    d1 = pd.DataFrame({'open': 100., 'high': 105., 'low': 99.5,
                       'close': 100., 'volume': 10.},
                      index=pd.date_range('2025-01-01', periods=1360, freq='1h', tz='UTC'))
    baseline = run_backtest('ETH', df_4h=d4, df_1h=d1, persist=False)
    assert baseline['total_trades'] > 0
    bounded = run_backtest('ETH', df_4h=d4, df_1h=d1, persist=False,
                           signal_start=idx[275], signal_end=idx[316])
    assert bounded['total_trades'] == 0
    with pytest.raises(ValueError):
        run_backtest('ETH', df_4h=d4, df_1h=d1, persist=False,
                     signal_start=idx[300], signal_end=idx[200])


def test_rolling_periods_never_reuse_a_test_interval():
    from backtest.walkforward import rolling_periods
    periods = rolling_periods('2023-01-01', '2026-10-01')
    assert len(periods) >= 5
    for i, (start, split, end) in enumerate(periods):
        assert start == '2023-01-01'
        assert split < end
        if i:
            assert split == periods[i-1][2]
    with pytest.raises(ValueError):
        rolling_periods('2026-01-01', '2026-05-01')


def test_rolling_audit_runs_each_fold_without_auto_promoting(monkeypatch, tmp_path):
    from backtest import walkforward
    calls = []
    def simulated(coin, directory, start, split, end):
        calls.append((coin, split, end))
        return {'assessment': 'NO_VERIFIED_EDGE', 'coin': coin}
    monkeypatch.setattr(walkforward, 'audit_coin', simulated)
    result = walkforward.rolling_audit_coin('ETH', tmp_path, '2023-01-01', '2025-01-01')
    assert len(calls) >= 2
    assert result['status'] == 'RESEARCH_ONLY_NOT_APPROVED_FOR_LIVE'
    assert result['positive_folds'] == 0


def test_sizing_halts_on_unacceptable_portfolio_drawdown(monkeypatch):
    from engines.sizing import adaptive
    monkeypatch.setattr(adaptive, '_get_today_pnl', lambda: 0.0)
    monkeypatch.setattr(adaptive, '_get_open_counts', lambda: {'total': 0, 'long': 0, 'short': 0})
    monkeypatch.setattr(adaptive, '_get_performance', lambda: {'total': 0, 'win_rate': None, 'streak': 0, 'streak_type': None})
    monkeypatch.setattr(adaptive, '_get_total_trades', lambda: 0)
    monkeypatch.setattr(adaptive, '_get_circuit_breaker_multiplier', lambda: 1)
    monkeypatch.setattr(adaptive, '_session_matches', lambda s: True)
    fake = types.ModuleType('engines.state')
    fake.should_skip_after_loss = lambda _: False
    monkeypatch.setitem(sys.modules, 'engines.state', fake)
    kwargs = dict(balance=1000, sl_pct=1., sl_dist=1., grade='A', direction='LONG', coin='SOL')
    for dd in (.20, .33):
        monkeypatch.setattr(adaptive, '_get_drawdown', lambda balance: dd)
        assert adaptive.calculate(**kwargs).reason == 'portfolio_drawdown_halt'
    monkeypatch.setattr(adaptive, '_get_drawdown', lambda balance: float('nan'))
    assert adaptive.calculate(**kwargs).reason == 'invalid_portfolio_drawdown'
