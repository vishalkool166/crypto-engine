"""Safety-focused invariants: no real orders, network or exchanges."""
import sys
import types

import pytest

from engines.sizing import adaptive
from trade.safety import validate_symbol_notional


@pytest.fixture
def isolated_sizing(monkeypatch):
    monkeypatch.setattr(adaptive, "_get_today_pnl", lambda: 0.0)
    monkeypatch.setattr(adaptive, "_get_open_counts", lambda: {"total": 0, "long": 0, "short": 0})
    monkeypatch.setattr(adaptive, "_get_performance", lambda: {"total": 0, "win_rate": None, "streak": 0, "streak_type": None})
    monkeypatch.setattr(adaptive, "_get_drawdown", lambda balance: 0.0)
    monkeypatch.setattr(adaptive, "_get_total_trades", lambda: 0)
    monkeypatch.setattr(adaptive, "_get_circuit_breaker_multiplier", lambda: 1.0)
    monkeypatch.setattr(adaptive, "_get_current_session", lambda: "London")
    monkeypatch.setattr(adaptive, "_session_matches", lambda setting: True)
    fake_state = types.ModuleType("engines.state")
    fake_state.should_skip_after_loss = lambda coin: False
    monkeypatch.setitem(sys.modules, "engines.state", fake_state)


def calculate(**overrides):
    params = dict(balance=2000, sl_pct=1, sl_dist=1, grade="B",
                  direction="LONG", coin="ETH", regime_mult=1)
    params.update(overrides)
    return adaptive.calculate(**params)


def test_correlation_and_regime_mult_really_reduce_risk(isolated_sizing):
    normal = calculate(balance=20000)
    reduced = calculate(balance=20000, regime_mult=.2)
    assert not normal.skip
    assert not reduced.skip
    assert reduced.position_size < normal.position_size * .25
    assert reduced.risk_amt <= normal.risk_amt * .25
    assert reduced.risk_pct < normal.risk_pct


def test_small_balance_skips_instead_of_increasing_stake(isolated_sizing):
    result = calculate(balance=50, regime_mult=.2)
    assert result.skip and result.reason == 'risk_budget_below_minimum_stake'
    assert result.stake == 0 and result.risk_amt == 0


def test_zero_and_invalid_multiplier_blocks_entries(isolated_sizing):
    for value in (0, -1, float('nan'), float('inf')):
        assert calculate(regime_mult=value).skip


def test_missing_pnl_and_open_positions_fail_closed(isolated_sizing, monkeypatch):
    monkeypatch.setattr(adaptive, "_get_today_pnl", lambda: None)
    assert calculate().reason == 'risk_state_unavailable:daily_pnl'
    monkeypatch.setattr(adaptive, "_get_today_pnl", lambda: 0)
    monkeypatch.setattr(adaptive, "_get_open_counts", lambda: None)
    assert calculate().reason == 'risk_state_unavailable:open_positions'


def test_missing_performance_and_portfolio_circuit_breaker_fail_closed(isolated_sizing, monkeypatch):
    monkeypatch.setattr(adaptive, "_get_performance", lambda: None)
    assert calculate().reason == 'risk_state_unavailable:performance'
    monkeypatch.setattr(adaptive, "_get_performance", lambda: {"total": 0, "win_rate": None, "streak": 0, "streak_type": None})
    monkeypatch.setattr(adaptive, "_get_circuit_breaker_multiplier", lambda: 0.0)
    assert calculate().reason == 'circuit_breaker_halt'


def test_loss_limit_is_inclusive(isolated_sizing, monkeypatch):
    monkeypatch.setattr(adaptive, "_get_today_pnl", lambda: -40.0)
    assert calculate(balance=2000).reason.startswith('daily_loss_limit')


def test_symbol_notional_respects_coin_specific_floor():
    validate_symbol_notional(2500, .01, 20)  # ETH: $25 > $20
    validate_symbol_notional(100, .05, 5)    # example $5 minimum
    with pytest.raises(ValueError, match='below exchange minimum'):
        validate_symbol_notional(2500, .005, 20)
    for invalid in (0, -1, float('nan'), float('inf')):
        with pytest.raises(ValueError):
            validate_symbol_notional(2500, .01, invalid)


@pytest.mark.asyncio
async def test_futures_exchange_info_returns_symbol_min_notional(monkeypatch):
    from trade import exchange

    async def fake_get(url, params):
        return {"symbols": [{"symbol": "ETHUSDT", "status": "TRADING", "contractType": "PERPETUAL", "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001"},
            {"filterType": "PRICE_FILTER", "tickSize": "0.01", "minPrice": "1"},
            {"filterType": "MIN_NOTIONAL", "notional": "20"},
        ]}]}

    monkeypatch.setattr(exchange, "_get", fake_get)
    rules = await exchange.get_symbol_precision("ETH")
    assert rules['min_notional'] == 20
    assert rules['step_size'] == .001


def test_graph_sizing_node_preserves_coin(monkeypatch):
    from agents.nodes.sizing_node import sizing_node
    import types
    received = {}

    def stub(**kwargs):
        received.update(kwargs)
        return types.SimpleNamespace(skip=True, reason='blocked')
    monkeypatch.setattr(adaptive, 'calculate', stub)
    state = dict(coin='SOL', balance=500, direction='LONG', grade='A', session='London',
                 risk_result=types.SimpleNamespace(sl_pct=1, sl_dist=1),
                 regime_result=types.SimpleNamespace(size_mult=1), trace_steps=[])
    result = sizing_node(state)
    assert result['reason'] == 'blocked'
    assert received['coin'] == 'SOL'
