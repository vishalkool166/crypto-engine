"""Isolated deterministic checks. No exchange API calls and no real orders."""
import asyncio
import importlib
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import httpx
import pytest

from trade import order_journal, safety
from test_security_regression import extracted_function


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
