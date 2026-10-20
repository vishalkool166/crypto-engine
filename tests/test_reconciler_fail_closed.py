"""Startup reconciliation must preserve uncertain trades and block fresh entries."""
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_exchange_flat_but_local_active_trade_enters_manual_reconciliation(monkeypatch, tmp_path):
    import runtime_state
    from trade import reconciler

    monkeypatch.setattr(runtime_state, 'STATE_FILE', str(tmp_path / 'runtime_state.json'))
    monkeypatch.setattr(runtime_state, '_state', {})
    trade = SimpleNamespace(id=17, coin='ETH', direction='LONG', is_active=True, state='open')

    class Query:
        def __init__(self, db): self.db = db
        def filter(self, *args): return self
        def all(self):
            self.db.query_count += 1
            return [] if self.db.query_count == 1 else [trade]

    class Session:
        def __init__(self): self.query_count = 0; self.committed = False
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def query(self, _): return Query(self)
        def commit(self): self.committed = True

    session = Session()
    database = ModuleType('database')
    database.SessionLocal = lambda: session
    database.Trade = type('Trade', (), {'state': 'state', 'outcome': 'outcome', 'is_active': 'is_active'})
    monkeypatch.setitem(__import__('sys').modules, 'database', database)
    exchange = ModuleType('trade.exchange')
    exchange.get_positions = AsyncMock(return_value=[])
    exchange.get_symbol_precision = AsyncMock()
    exchange.place_algo_order = AsyncMock()
    monkeypatch.setitem(__import__('sys').modules, 'trade.exchange', exchange)

    await reconciler.reconcile_on_startup()

    assert trade.state == 'reconciliation_required'
    assert trade.is_active is True
    assert runtime_state.get_new_exposure_halt()['enabled'] is True
    assert runtime_state.get_new_exposure_halt()['reason'] == 'startup_trade_state_requires_reconciliation'
    assert session.committed is True


@pytest.mark.asyncio
async def test_unavailable_exchange_snapshot_halts_new_entries(monkeypatch, tmp_path):
    import runtime_state
    from trade import reconciler

    monkeypatch.setattr(runtime_state, 'STATE_FILE', str(tmp_path / 'runtime_state.json'))
    monkeypatch.setattr(runtime_state, '_state', {})
    exchange = ModuleType('trade.exchange')
    exchange.get_positions = AsyncMock(side_effect=ConnectionError('offline'))
    monkeypatch.setitem(__import__('sys').modules, 'trade.exchange', exchange)

    await reconciler.reconcile_on_startup()

    assert runtime_state.get_new_exposure_halt()['enabled'] is True
