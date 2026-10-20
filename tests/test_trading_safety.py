"""Isolated deterministic checks. No exchange API calls and no real orders."""
import asyncio
import importlib
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import httpx
import pytest

from trade import order_journal, safety
from test_security_regression import extracted_function


def _reserve_across_processes(_):
    return order_journal.reserve('entry:multi-process', 'paper', 'ADAUSDT', 'BUY', 'LIMIT', {'quantity': '2'})


@pytest.fixture
def durable_db(monkeypatch, tmp_path):
    monkeypatch.setenv('SIGNAL_ENGINE_DB_PATH', str(tmp_path / 'journal.db'))
    return tmp_path / 'journal.db'


def test_order_intent_committed_before_network(durable_db):
    client_id, is_new = order_journal.reserve('entry:100', 'paper', 'ETHUSDT', 'BUY', 'LIMIT', {'quantity': '1', 'price': '120'})
    assert is_new and client_id.startswith('se_') and len(client_id) <= 36
    assert durable_db.exists()
    assert order_journal.unresolved('ETHUSDT')[0]['client_order_id'] == client_id
    assert order_journal.reserve('entry:100', 'paper', 'ETHUSDT', 'BUY', 'LIMIT', {'quantity': '1', 'price': '120'}) == (client_id, False)
    assert len(order_journal.unresolved()) == 1
    import sqlite3
    with sqlite3.connect(durable_db) as db:
        assert db.execute('SELECT version FROM order_journal_schema WHERE singleton=1').fetchone() == (1,)


def test_order_journal_schema_version_backfill_preserves_existing_intents(durable_db):
    import sqlite3
    original = order_journal.reserve('entry:legacy', 'paper', 'ETHUSDT', 'BUY', 'LIMIT', {'quantity': '1'})
    with sqlite3.connect(durable_db) as db:
        db.execute('DROP TABLE order_journal_schema')
    order_journal._INITIALIZED_PATHS.clear()
    assert order_journal.reserve('entry:legacy', 'paper', 'ETHUSDT', 'BUY', 'LIMIT', {'quantity': '1'}) == (original[0], False)
    assert order_journal.unresolved('ETHUSDT')[0]['client_order_id'] == original[0]
    with sqlite3.connect(durable_db) as db:
        assert db.execute('SELECT version FROM order_journal_schema WHERE singleton=1').fetchone() == (1,)


def test_order_journal_refuses_unknown_future_schema_without_deleting_evidence(durable_db):
    import sqlite3
    original = order_journal.reserve('entry:versioned', 'paper', 'BTCUSDT', 'BUY', 'LIMIT', {'quantity': '2'})
    with sqlite3.connect(durable_db) as db:
        db.execute('UPDATE order_journal_schema SET version=99 WHERE singleton=1')
    order_journal._INITIALIZED_PATHS.clear()
    with pytest.raises(RuntimeError, match='Unsupported order journal schema version'):
        order_journal.reserve('entry:next', 'paper', 'ETHUSDT', 'BUY', 'LIMIT', {'quantity': '1'})
    with sqlite3.connect(durable_db) as db:
        assert db.execute('SELECT client_order_id FROM exchange_order_intents WHERE intent_key=?',
                          ('entry:versioned',)).fetchone() == (original[0],)


def test_order_intent_survives_reload(durable_db):
    original = order_journal.reserve('entry:234', 'live', 'BTCUSDT', 'SELL', 'LIMIT', {'quantity': 1})
    reloaded = importlib.reload(order_journal)
    assert reloaded.reserve('entry:234', 'live', 'BTCUSDT', 'SELL', 'LIMIT', {'quantity': 1}) == (original[0], False)


def test_conflicting_intent_never_overwritten(durable_db):
    order_journal.reserve('close:7', 'paper', 'ETHUSDT', 'SELL', 'MARKET', {'quantity': 3})
    for mode, payload in [('paper', {'quantity': 4}), ('live', {'quantity': 3})]:
        with pytest.raises(order_journal.OrderIntentConflict):
            order_journal.reserve('close:7', mode, 'ETHUSDT', 'SELL', 'MARKET', payload)


def test_atomic_reservation_concurrency(durable_db):
    def task(_):
        return order_journal.reserve('entry:singleton', 'paper', 'SOLUSDT', 'BUY', 'LIMIT', {'quantity': 1})
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(task, range(16)))
    assert len(set(key for key, _ in outcomes)) == 1
    assert sum(created for _, created in outcomes) == 1


def test_atomic_reservation_across_processes(durable_db):
    with ProcessPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(_reserve_across_processes, range(8)))
    assert len({client_id for client_id, _ in outcomes}) == 1
    assert sum(created for _, created in outcomes) == 1
    assert len(order_journal.unresolved('ADAUSDT')) == 1


def test_uncertain_orders_block_new_entries(durable_db):
    order_journal.reserve('entry:50', 'paper', 'BNBUSDT', 'BUY', 'LIMIT')
    order_journal.mark('entry:50', 'uncertain')
    assert len(order_journal.unresolved('BNBUSDT')) == 1
    order_journal.mark('entry:50', 'acknowledged', '72343')
    assert len(order_journal.unresolved('BNBUSDT')) == 1
    order_journal.mark('entry:50', 'finished')
    assert not order_journal.unresolved('BNBUSDT')


def test_live_guard_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv('SIGNAL_ENGINE_ALLOW_LIVE_TRADING', raising=False)
    with pytest.raises(PermissionError):
        safety.ensure_live_opt_in('live')
    safety.ensure_live_opt_in('paper')
    monkeypatch.setenv('SIGNAL_ENGINE_ALLOW_LIVE_TRADING', 'true')
    with pytest.raises(PermissionError):
        safety.ensure_live_opt_in('live')
    monkeypatch.setenv('SIGNAL_ENGINE_ALLOW_LIVE_TRADING', safety.LIVE_OPT_IN)
    safety.ensure_live_opt_in('live')


@pytest.mark.asyncio
async def test_mode_change_does_not_mutate_configuration_if_exchange_close_fails(monkeypatch):
    import config
    import trade.exchange as exchange
    original = (config.cfg.TRADING_MODE, config.cfg.PAPER_TRADING)
    persisted = []
    monkeypatch.setattr(config, '_ensure', lambda key, value: persisted.append((key, value)))

    async def fail_close():
        raise RuntimeError('client still active')

    monkeypatch.setattr(exchange, 'close_exchange', fail_close)
    with pytest.raises(RuntimeError, match='client still active'):
        await safety.apply_trading_mode('live')
    assert persisted == []
    assert (config.cfg.TRADING_MODE, config.cfg.PAPER_TRADING) == original


@pytest.mark.asyncio
async def test_mode_change_closes_exchange_before_persisting_and_updating(monkeypatch):
    import config
    import trade.exchange as exchange
    original = (config.cfg.TRADING_MODE, config.cfg.PAPER_TRADING)
    events = []
    monkeypatch.setattr(config, '_ensure', lambda key, value: events.append(('persist', key, value)))

    async def close():
        events.append(('close',))

    monkeypatch.setattr(exchange, 'close_exchange', close)
    try:
        await safety.apply_trading_mode('live')
        assert events == [('close',), ('persist', 'TRADING_MODE', 'live')]
        assert (config.cfg.TRADING_MODE, config.cfg.PAPER_TRADING) == ('live', False)
    finally:
        config.cfg.TRADING_MODE, config.cfg.PAPER_TRADING = original


def test_both_mode_routes_use_the_shared_safe_transition():
    from pathlib import Path
    for path in (Path('api/trading.py'), Path('api/routes.py')):
        source = path.read_text()
        assert 'apply_trading_mode(new_mode)' in source
        assert '_ensure("TRADING_MODE", new_mode)' not in source


@pytest.mark.asyncio
@pytest.mark.parametrize('order', [
    {'status': 'PARTIALLY_FILLED', 'executedQty': '0.25'},
    {'status': 'NEW', 'executedQty': '0.25'},
    {'status': 'PARTIALLY_FILLED', 'executedQty': '0'},
])
async def test_limit_entry_partial_fill_requires_manual_reconciliation(order):
    waiter = extracted_function('trade/executor.py', '_wait_for_limit_fill', {
        'asyncio': asyncio,
        '_fetch_order': AsyncMock(return_value=order),
    })
    with pytest.raises(RuntimeError, match='partially executed'):
        await waiter('ETHUSDT', 'entry-1', 1)


@pytest.mark.asyncio
async def test_limit_entry_waiter_accepts_filled_and_returns_none_when_cancelled():
    filled_order = {'status': 'FILLED', 'executedQty': '1'}
    filled_waiter = extracted_function('trade/executor.py', '_wait_for_limit_fill', {
        'asyncio': asyncio,
        '_fetch_order': AsyncMock(return_value=filled_order),
    })
    assert await filled_waiter('ETHUSDT', 'entry-2', 1) == filled_order

    cancelled_waiter = extracted_function('trade/executor.py', '_wait_for_limit_fill', {
        'asyncio': asyncio,
        '_fetch_order': AsyncMock(return_value={'status': 'CANCELED', 'executedQty': '0'}),
    })
    assert await cancelled_waiter('ETHUSDT', 'entry-3', 1) is None


@pytest.mark.parametrize('args', [
    ('LONG',100,110,115,10,5),
    ('LONG',100,95,90,10,5),
    ('SHORT',100,95,90,10,5),
    ('SHORT',100,110,120,10,5),
    ('LONG',100,90,120,float('nan'),5),
    ('LONG',100,90,120,10,0),
    ('LONG',100,90,120,10,21),
    ('LONG',100,90,120,1,5),
])
def test_reject_invalid_risk_inputs(args):
    with pytest.raises(ValueError):
        safety.validate_entry(*args, minimum_stake=5.0)


def test_accept_valid_risk_and_step_precision():
    safety.validate_entry('LONG', 100, 95, 120, 10, 5, 5)
    safety.validate_entry('SHORT', 100, 105, 95, 10, 3, 5)
    safety.require_precision({'tick_size': 0.25, 'step_size': 0.005, 'min_qty': 0.01})
    with pytest.raises(ValueError):
        safety.require_precision({'tick_size': 0, 'step_size': 0.005, 'min_qty': 0.01})


def test_decimal_rounding_handles_non_power_ten_steps():
    import math
    from decimal import Decimal, ROUND_FLOOR
    floor = extracted_function('trade/executor.py', '_floor_to_increment', {
        'math': math, 'Decimal': Decimal, 'ROUND_FLOOR': ROUND_FLOOR,
    })
    for value, increment, expected in [(2.74, .25, 2.5), (2.74, .05, 2.7), (2.74, 2.5, 2.5)]:
        assert floor(value, increment) == expected
    with pytest.raises(ValueError):
        floor(float('nan'), .01)
    precision = extracted_function('trade/exchange.py', '_precision_from_step', {})
    assert precision(.25) == 2
    assert precision(.005) == 3
    assert precision(2.5) == 1


@pytest.mark.asyncio
async def test_reused_order_intent_never_resubmits(monkeypatch, durable_db):
    exchange = ModuleType('trade.exchange')
    exchange.get_order_by_client_id = AsyncMock(return_value={'orderId': 42, 'status': 'NEW'})
    monkeypatch.setitem(sys.modules, 'trade.exchange', exchange)
    submit = AsyncMock(return_value={'orderId': 42, 'status': 'NEW'})
    execute = extracted_function('trade/executor.py', '_place_with_retry', {
        'place_order': submit, 'log': logging.getLogger(__name__), 'asyncio': asyncio,
    })
    kwargs = {'intent_key': 'entry:19', 'symbol': 'ETHUSDT', 'side': 'BUY', 'order_type': 'LIMIT', 'quantity': 1, 'price': 100}
    assert (await execute(**kwargs))['orderId'] == 42
    assert (await execute(**kwargs))['orderId'] == 42
    assert submit.await_count == 1
    assert exchange.get_order_by_client_id.await_count == 1


@pytest.mark.asyncio
async def test_new_exposure_halt_blocks_entries_but_allows_reduce_only_exits(monkeypatch, durable_db, tmp_path):
    import runtime_state

    monkeypatch.setattr(runtime_state, 'STATE_FILE', str(tmp_path / 'runtime_state.json'))
    monkeypatch.setattr(runtime_state, '_state', {})
    runtime_state.set_new_exposure_halt(True, 'incident')

    exchange = ModuleType('trade.exchange')
    exchange.place_order = AsyncMock(return_value={'orderId': 7, 'status': 'NEW'})
    exchange.get_order_by_client_id = AsyncMock(return_value=None)
    monkeypatch.setitem(sys.modules, 'trade.exchange', exchange)

    from trade import order_journal
    reserve = order_journal.reserve
    monkeypatch.setattr(order_journal, 'reserve', lambda *args, **kwargs: ('se_exit', True))
    monkeypatch.setattr(order_journal, 'mark', lambda *args, **kwargs: None)
    execute = extracted_function('trade/executor.py', '_place_with_retry', {
        'place_order': exchange.place_order, 'log': logging.getLogger(__name__), 'asyncio': asyncio,
    })

    with pytest.raises(PermissionError, match='incident'):
        await execute(intent_key='entry:halted', symbol='ETHUSDT', side='BUY',
                      order_type='MARKET', quantity=1)
    assert exchange.place_order.await_count == 0

    result = await execute(intent_key='close:7', symbol='ETHUSDT', side='SELL',
                           order_type='MARKET', quantity=1, reduce_only=True)
    assert result['orderId'] == 7
    assert exchange.place_order.await_count == 1
    monkeypatch.setattr(order_journal, 'reserve', reserve)


@pytest.mark.asyncio
async def test_process_restart_after_transport_error_does_not_resubmit(monkeypatch, durable_db):
    exchange = ModuleType('trade.exchange')
    exchange.get_order_by_client_id = AsyncMock(side_effect=httpx.ReadTimeout('unknown exchange state'))
    monkeypatch.setitem(sys.modules, 'trade.exchange', exchange)
    submit = AsyncMock(side_effect=httpx.ReadTimeout('submission lost'))
    execute = extracted_function('trade/executor.py', '_place_with_retry', {
        'place_order': submit, 'log': logging.getLogger(__name__), 'asyncio': asyncio,
    })
    kwargs = {'intent_key': 'entry:99', 'symbol': 'BTCUSDT', 'side': 'SELL', 'order_type': 'LIMIT', 'quantity': 1, 'price': 100}
    with pytest.raises(RuntimeError, match='verify exchange state'):
        await execute(**kwargs)
    assert len(order_journal.unresolved()) == 1
    importlib.reload(order_journal)
    with pytest.raises(RuntimeError, match='verify exchange state'):
        await execute(**kwargs)
    assert submit.await_count == 1
