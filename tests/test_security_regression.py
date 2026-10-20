"""Dependency-light regression tests for security-critical code paths.

Tests exercise the real source functions with isolated fake integrations so they
can run without exchange credentials, a database, or the heavy ML stack.
"""
import ast
import asyncio
import importlib.util
import logging
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException, WebSocket, WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[1]


def load_module_from_source(monkeypatch, name, relative, stubs):
    for module_name, module in stubs.items():
        monkeypatch.setitem(sys.modules, module_name, module)
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extracted_function(relative, name, globals_):
    tree = ast.parse((ROOT / relative).read_text())
    target = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    target.decorator_list = []
    namespace = dict(globals_)
    exec(compile(ast.Module(body=[target], type_ignores=[]), str(ROOT / relative), "exec"), namespace)
    return namespace[name]








@pytest.mark.asyncio
async def test_ambiguous_order_submitted_only_once(monkeypatch, tmp_path):
    monkeypatch.setenv('SIGNAL_ENGINE_DB_PATH', str(tmp_path / 'signals.db'))
    exchange = ModuleType('trade.exchange')
    seen = []
    async def lookup(symbol, client_id):
        seen.append(('lookup', symbol, client_id))
        return {'orderId': 105, 'status': 'NEW'}
    exchange.get_order_by_client_id = lookup
    monkeypatch.setitem(sys.modules, 'trade.exchange', exchange)
    submissions = []
    async def submit(**kwargs):
        submissions.append(kwargs)
        raise httpx.ReadTimeout('request timed out')
    func = extracted_function('trade/executor.py', '_place_with_retry', {
        'place_order': submit, 'httpx': httpx, 'log': logging.getLogger(__name__),
    })
    result = await func(symbol='ETHUSDT', side='BUY', order_type='MARKET', quantity=1)
    assert result['orderId'] == 105
    assert len(submissions) == 1
    assert seen[0][2] == submissions[0]['client_order_id']


@pytest.mark.asyncio
async def test_unresolved_order_never_retried(monkeypatch, tmp_path):
    monkeypatch.setenv('SIGNAL_ENGINE_DB_PATH', str(tmp_path / 'signals.db'))
    exchange = ModuleType('trade.exchange')
    async def lookup(symbol, client_id):
        raise RuntimeError('exchange unavailable')
    exchange.get_order_by_client_id = lookup
    monkeypatch.setitem(sys.modules, 'trade.exchange', exchange)
    submit = AsyncMock(side_effect=httpx.ConnectError('network down'))
    func = extracted_function('trade/executor.py', '_place_with_retry', {
        'place_order': submit, 'httpx': httpx, 'log': logging.getLogger(__name__),
    })
    with pytest.raises(RuntimeError, match='verify exchange state'):
        await func(symbol='ETHUSDT', side='BUY', order_type='MARKET', quantity=1)
    assert submit.await_count == 1


@pytest.mark.asyncio
async def test_client_order_id_sent_to_exchange():
    capture = AsyncMock(return_value={'orderId': 22})
    func = extracted_function('trade/exchange.py', 'place_order', {
        '_clean': lambda s: s, '_post': capture,
        'cfg': SimpleNamespace(TRADING_MODE='paper'),
    })
    await func('ETHUSDT','BUY','MARKET',2, client_order_id='se_fixed_123')
    assert capture.await_args.args[1]['newClientOrderId'] == 'se_fixed_123'


class WS:
    def __init__(self, origin=None):
        self.headers = {'origin':origin} if origin else {}
        self.accepted = False
        self.closed = None
        self.sent = []
    async def accept(self):
        self.accepted = True
    async def close(self, code):
        self.closed = code
    async def send_text(self, value):
        self.sent.append(value)
    async def receive_text(self):
        raise WebSocketDisconnect()








