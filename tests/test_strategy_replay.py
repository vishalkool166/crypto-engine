"""Offline, repeatable replay checks. No Binance credentials or live orders."""
import math
import sys
import types
from unittest.mock import Mock
import pandas as pd
import pytest

from backtest.engine import (_simulate_trade, _net_pnl, _utc_index, _summary,
                             ReplayCosts, _session_matches)


def bars(*, opens=(100,), highs=(103,), lows=(99.5,), closes=(100,)):
    n = len(opens)
    return pd.DataFrame({'open': opens, 'high': highs, 'low': lows,
                         'close': closes, 'volume': [1000] * n},
                        index=pd.date_range('2025-01-01', periods=n, freq='4h', tz='UTC'))


def test_tp1_closes_the_entire_position_no_fictitious_tp2():
    result = _simulate_trade(bars(), 0, 'LONG', 100, 99, 102, 110)
    assert result['outcome'] == 'win'
    assert result['exit_price'] == 102
    assert result['tp2_hit'] is False


def test_intrabar_ambiguity_is_stop_first():
    data = bars(lows=(98.5,))
    result = _simulate_trade(data, 0, 'LONG', 100, 99, 102)
    assert result['outcome'] == 'loss'
    assert result['exit_price'] == 99


def test_unfilled_limit_is_not_counted_as_a_trade():
    data = bars(opens=(110,), highs=(112,), lows=(109,), closes=(111,))
    assert _simulate_trade(data, 0, 'LONG', 100, 99, 102)['outcome'] == 'no_fill'


def test_short_tp_and_stop():
    data = bars(opens=(100,), highs=(100.5,), lows=(96,), closes=(99,))
    assert _simulate_trade(data, 0, 'SHORT', 100, 101, 98)['outcome'] == 'win'
    assert _simulate_trade(data, 0, 'SHORT', 100, 100.1, 98)['outcome'] == 'loss'


def test_timeout_marks_to_market_instead_of_dropping_loser():
    data = bars(opens=(100, 100), highs=(100.4, 100.4),
                lows=(99.6, 99.6), closes=(99.8, 99.4))
    result = _simulate_trade(data, 0, 'LONG', 100, 99, 105, costs=ReplayCosts(max_holding_bars=2))
    assert result['outcome'] == 'timeout'
    assert result['exit_price'] == 99.4
    assert _net_pnl(direction='LONG', entry=100, exit_price=result['exit_price'],
                    notional=500, costs=ReplayCosts()) < 0


def test_net_pnl_calculates_fee_slippage_and_funding_on_actual_exit():
    costs = ReplayCosts(entry_fee=.0005, exit_fee=.0005,
                        entry_slippage_bps=3, exit_slippage_bps=3)
    win = _net_pnl(direction='LONG', entry=100, exit_price=102,
                   notional=1000, costs=costs, funding_rate_sum=.001)
    assert win == pytest.approx(17.39, abs=0.001)
    loss = _net_pnl(direction='LONG', entry=100, exit_price=99,
                    notional=1000, costs=costs)
    assert loss < -10


def test_summary_uses_pnl_not_tp_label():
    fake = [{'pnl': -10}, {'pnl': 5}]
    s = _summary(fake, 1000)
    assert s['win_rate'] == 50
    assert s['expectancy'] == -2.5
    assert s['profit_factor'] == 0.5


def test_invalid_or_nonchronological_candles_rejected():
    invalid = bars(opens=(100, 100), highs=(103, 103), lows=(99.5, 99.5), closes=(100, 100))
    invalid.iloc[1, invalid.columns.get_loc('high')] = 50
    with pytest.raises(ValueError):
        _utc_index(invalid)
    with pytest.raises(ValueError):
        _utc_index(invalid.sort_index(ascending=False))


def test_session_boundaries_use_utc():
    assert _session_matches('ETH', pd.Timestamp('2025-01-01T04:00:00Z'))
    assert not _session_matches('ETH', pd.Timestamp('2025-01-01T12:00:00Z'))
    assert _session_matches('SOL', pd.Timestamp('2025-01-01T12:00:00Z'))
    assert not _session_matches('SOL', pd.Timestamp('2025-01-01T04:00:00Z'))


def test_replay_uses_coin_specific_live_tp_and_no_trend_side_effect(monkeypatch):
    import engines.core
    fake_indicators = types.ModuleType('engines.core.indicators')
    def indicators(frame, timeframe='4h'):
        if timeframe == '1h':
            return {'rsi': 42.0}
        return {'price': 100.0, 'ema20': 103.0, 'ema50': 101.0,
                'ema200': 95.0, 'adx': 32.0, 'atr': 1.0,
                'vol_ratio': 1.5, 'swing_low': 99.5, 'swing_high': 101.5}
    fake_indicators.get_indicators = indicators
    monkeypatch.setitem(sys.modules, 'engines.core.indicators', fake_indicators)
    from backtest.engine import run_backtest
    idx = pd.date_range('2025-01-01', periods=330, freq='4h', tz='UTC')
    d4 = pd.DataFrame({'open': 100., 'high': 105., 'low': 99.5, 'close': 100., 'volume': 10.}, index=idx)
    idx1 = pd.date_range('2025-01-01', periods=1320, freq='1h', tz='UTC')
    d1 = pd.DataFrame({'open': 100., 'high': 105., 'low': 99.5, 'close': 100., 'volume': 10.}, index=idx1)
    eth = run_backtest('ETH', df_4h=d4, df_1h=d1, persist=False)
    sol = run_backtest('SOL', df_4h=d4, df_1h=d1, persist=False)
    assert eth['total_trades'] > 0
    assert sol['total_trades'] > 0
    # Their per-coin TP multiples must differ for the same swing.
    assert eth['trades'][0]['tp1'] == 102
    assert sol['trades'][0]['tp1'] == 103.5
    assert all(t['tp2_hit'] is False for t in eth['trades'])
    assert eth['funding_modeled'] is False
    assert eth['result_type'] == 'simulated_backtest'
    assert eth['pnl_provenance'] == 'simulated_not_exchange_realized'
    assert eth['exchange_verified'] is False
    assert eth['walk_forward']['method'].startswith('chronological')


def test_adverse_gap_stop_uses_worse_open_price():
    data = bars(opens=(100, 94), highs=(100.4, 98), lows=(99.6, 93),
                closes=(100, 96))
    result = _simulate_trade(data, 0, 'LONG', 100, 99, 105)
    assert result['outcome'] == 'loss'
    assert result['exit_price'] == 94


def test_research_only_lower_score_increases_signal_pool_without_live_change(monkeypatch):
    fake_indicators = types.ModuleType('engines.core.indicators')
    def indicators(frame, timeframe='4h'):
        if timeframe == '1h':
            return {'rsi': 55.0}
        return {'price': 100.0, 'ema20': 103.0, 'ema50': 101.0,
                'ema200': 95.0, 'adx': 22.0, 'atr': 1.0,
                'vol_ratio': 1.0, 'swing_low': 99.5, 'swing_high': 101.5}
    fake_indicators.get_indicators = indicators
    monkeypatch.setitem(sys.modules, 'engines.core.indicators', fake_indicators)
    from backtest.engine import run_backtest
    idx = pd.date_range('2025-01-01', periods=300, freq='4h', tz='UTC')
    idx1 = pd.date_range('2025-01-01', periods=1200, freq='1h', tz='UTC')
    d4 = pd.DataFrame({'open': 100., 'high': 105., 'low': 99.5, 'close': 100., 'volume': 10.}, index=idx)
    d1 = pd.DataFrame({'open': 100., 'high': 105., 'low': 99.5, 'close': 100., 'volume': 10.}, index=idx1)
    baseline = run_backtest('ETH', df_4h=d4, df_1h=d1, persist=False)
    research = run_backtest('ETH', df_4h=d4, df_1h=d1, persist=False, research_min_score=40)
    assert baseline['total_trades'] == 0
    assert research['total_trades'] > 0
    assert research['live_rules_compatible'] is False


def test_graph_risk_node_receives_coin_config(monkeypatch):
    from agents.nodes.risk_node import risk_node
    import engines.risk.calculator as calculator
    captured = {}
    def mocked_calculate(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(valid=False, reason='mock_block')
    monkeypatch.setattr(calculator, 'calculate', mocked_calculate)
    state = {'coin': 'SUI', 'direction': 'LONG', 'd4h': {'price': 10, 'atr': 1,
             'swing_low': 9, 'swing_high': 11}, 'trace_steps': []}
    result = risk_node(state)
    assert captured['coin'] == 'SUI'
    assert result['reason'] == 'mock_block'


def test_limit_entry_bar_target_may_precede_long_fill():
    # High of 103 may occur before the dip to the 100 buy-limit. The old
    # simulator falsely credited a guaranteed take-profit from OHLC alone.
    data = bars(opens=(101, 100), highs=(103, 101),
                lows=(99.5, 99.6), closes=(100, 100))
    result = _simulate_trade(data, 0, 'LONG', 100, 99, 102,
                             costs=ReplayCosts(max_holding_bars=2))
    assert result['outcome'] == 'timeout'
    assert result['tp1_hit'] is False


def test_limit_entry_bar_target_may_precede_short_fill():
    data = bars(opens=(99, 100), highs=(100.5, 100.4),
                lows=(97, 99.5), closes=(100, 100))
    result = _simulate_trade(data, 0, 'SHORT', 100, 101, 98,
                             costs=ReplayCosts(max_holding_bars=2))
    assert result['outcome'] == 'timeout'
    assert result['tp1_hit'] is False


def test_replay_does_not_execute_grade_b_that_live_scanner_drops(monkeypatch):
    import types, sys
    from backtest.engine import run_backtest
    fake_indicators = types.ModuleType('engines.core.indicators')
    def ind(frame, timeframe='4h'):
        if timeframe == '1h':
            return {'rsi': 42.0}
        # ADX 25 -> 30, RSI 42 -> 30, volume 0.8 -> 0 => B (60)
        return {'price': 100., 'ema20': 101., 'ema50': 100., 'ema200': 95.,
                'adx': 25., 'atr': 1., 'vol_ratio': .8,
                'swing_low': 99.5, 'swing_high': 102.}
    fake_indicators.get_indicators = ind
    monkeypatch.setitem(sys.modules, 'engines.core.indicators', fake_indicators)
    idx4 = pd.date_range('2025-01-01', periods=310, freq='4h', tz='UTC')
    idx1 = pd.date_range('2025-01-01', periods=1240, freq='1h', tz='UTC')
    def data(idx):
        return pd.DataFrame({'open': 100., 'high': 104., 'low': 99.5,
                             'close': 100., 'volume': 10.}, index=idx)
    result = run_backtest('ETH', df_4h=data(idx4), df_1h=data(idx1), persist=False)
    assert result['total_trades'] == 0
    assert result['rejections'].get('live_grade_publish_filter', 0) > 0
