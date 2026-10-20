"""Entry-time fields needed by ML are copied from durable signal snapshots."""
from types import ModuleType, SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_outcome_recorder_copies_signal_features_without_exit_fields_as_features(monkeypatch):
    from ml import outcome_recorder

    trade = SimpleNamespace(
        id=3, signal_id=8, outcome='win', binance_net_pnl=4.0, net_pnl=4.0, pnl=3.0,
        entry_price=100.0, sl_price=98.0, tp1_price=104.0, exit_price=104.0, total_commission=0.1,
        funding_fees_paid=0.0, slippage_entry_pct=0.0, slippage_exit_pct=0.0,
        mae=0.5, mfe=4.0, duration_hours=2.0, tp1_hit=True,
        system_version='test', coin='BTC', direction='LONG', grade='A',
        close_reason='target', session_at_entry='Asia', regime_at_entry='trending',
        score_at_entry=80.0, balance_at_open=1000.0, drawdown_at_entry=2.0,
        win_rate_at_entry=55.0, binance_realized_pnl=4.0,
        binance_commission_total=0.1, binance_funding_total=0.0,
        binance_entry_price=100.0, binance_exit_price=104.0,
    )
    signal = SimpleNamespace(
        id=8, factor_scores='{"sweep": 12, "zone": 10, "trigger": 8}',
        sweep_score=1, retest_score=2, disp_score=3, day_of_week=2, hour_of_day=9,
    )
    captured = []

    class Query:
        def __init__(self, model): self.model = model
        def filter(self, *_): return self
        def first(self): return trade if self.model.__name__ == 'Trade' else (signal if self.model.__name__ == 'Signal' else None)

    class Session:
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def query(self, model): return Query(model)
        def add(self, row): captured.append(row)

    class Trade:
        id = 'id'
    class TradeOutcome:
        trade_id = 'trade_id'
        def __init__(self, **kwargs): self.values = kwargs
    class Signal:
        id = 'id'

    fake_db = ModuleType('database')
    fake_db.get_session = Session
    fake_db.Trade = Trade
    fake_db.TradeOutcome = TradeOutcome
    fake_db.Signal = Signal
    monkeypatch.setitem(__import__('sys').modules, 'database', fake_db)

    await outcome_recorder.record(3)

    row = captured[0].values
    assert (row['sweep_score'], row['zone_score'], row['trigger_score']) == (12, 10, 8)
    assert (row['day_of_week'], row['hour_of_day']) == (2, 9)
    assert row['binance_net_pnl'] == 4.0
