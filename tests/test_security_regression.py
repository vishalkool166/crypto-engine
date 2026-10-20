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


def test_admin_authentication_and_authorization(monkeypatch):
    fake_auth = ModuleType('auth')
    fake_auth.is_admin_user = lambda user: bool(user.get('is_admin'))
    fake_auth.password_is_set = lambda: True
    fake_middleware = ModuleType('saas.middleware')
    user_state = {'user': None}
    fake_middleware.get_current_user = lambda request: user_state['user']
    module = load_module_from_source(monkeypatch, 'security_under_test', 'saas/security.py', {
        'auth': fake_auth, 'saas.middleware': fake_middleware,
    })
    request = SimpleNamespace(headers={})
    with pytest.raises(HTTPException) as err:
        module.require_admin_access(request)
    assert err.value.status_code == 401
    user_state['user'] = {'is_admin': False}
    with pytest.raises(HTTPException) as err:
        module.require_admin_access(request)
    assert err.value.status_code == 403
    user_state['user'] = {'is_admin': True}
    assert module.require_admin_access(request)['is_admin']


def test_initial_setup_requires_operator_secret(monkeypatch):
    auth = ModuleType('auth')
    auth.is_admin_user = lambda user: True
    password = {'set': False}
    auth.password_is_set = lambda: password['set']
    mw = ModuleType('saas.middleware')
    mw.get_current_user = lambda request: None
    module = load_module_from_source(monkeypatch, 'security_bootstrap_test', 'saas/security.py', {
        'auth': auth, 'saas.middleware': mw,
    })
    monkeypatch.delenv('SIGNAL_ENGINE_SETUP_TOKEN', raising=False)
    with pytest.raises(HTTPException):
        module.require_setup_access(SimpleNamespace(headers={'X-Setup-Token': 'abc'}))
    monkeypatch.setenv('SIGNAL_ENGINE_SETUP_TOKEN', 'valid-secret')
    with pytest.raises(HTTPException):
        module.require_setup_access(SimpleNamespace(headers={'X-Setup-Token': 'wrong'}))
    module.require_setup_access(SimpleNamespace(headers={'X-Setup-Token': 'valid-secret'}))
    password['set'] = True
    with pytest.raises(HTTPException):
        module.require_setup_access(SimpleNamespace(headers={'X-Setup-Token': 'valid-secret'}))


def test_revoked_sessions_fail_closed(monkeypatch):
    config = ModuleType('config')
    config.cfg = SimpleNamespace()
    config.tier_meets_minimum = lambda a,b: True
    for name in ('TIER_FREE','TIER_PRO','TIER_ELITE','TIER_ADMIN'):
        setattr(config, name, name.lower())
    auth = ModuleType('auth')
    token = {'sub':'7', 'type':'oauth', 'session_id':'session-1', 'tier':'admin', 'is_admin': True}
    auth.get_current_user_any = lambda request: token.copy()
    auth.is_admin_user = lambda user: bool(user['is_admin'])
    sessions = ModuleType('saas.sessions')
    sessions.validate_session = lambda _: None
    mw = load_module_from_source(monkeypatch, 'middleware_under_test', 'saas/middleware.py', {
        'config': config, 'auth': auth, 'saas.sessions': sessions,
    })
    assert mw.get_current_user(SimpleNamespace()) is None
    sessions.validate_session = lambda _: {'user_id':8,'tier':'admin','is_admin':True,'email':'x'}
    assert mw.get_current_user(SimpleNamespace()) is None
    sessions.validate_session = lambda _: {'user_id':7,'tier':'free','is_admin':False,'email':'real@example.test'}
    user = mw.get_current_user(SimpleNamespace())
    assert user['is_admin'] is False and user['tier'] == 'free'
    sessions.validate_session = lambda _: (_ for _ in ()).throw(RuntimeError('db offline'))
    assert mw.get_current_user(SimpleNamespace()) is None


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


def ws_function(user):
    import json
    auth = ModuleType('auth')
    auth.is_admin_user = lambda u: bool(u.get('is_admin',False))
    old = sys.modules.get('auth')
    sys.modules['auth'] = auth
    clients = {}
    fn = extracted_function('main.py', 'dashboard_websocket', {
        'allowed_origins':['https://example.test'],
        '_get_ws_user': lambda ws: user,
        '_dashboard_clients': clients,
        '_build_ws_payload': AsyncMock(return_value={'type':'dashboard'}),
        'log': logging.getLogger(__name__), 'json':json,
        'WebSocketDisconnect': WebSocketDisconnect, 'WebSocket': WebSocket,
    })
    if old is None:
        del sys.modules['auth']
    else:
        sys.modules['auth'] = old
    return fn, clients, auth


@pytest.mark.asyncio
async def test_ws_rejects_unauthenticated(monkeypatch):
    fn, clients, auth = ws_function(None)
    monkeypatch.setitem(sys.modules, 'auth', auth)
    ws = WS(origin='https://example.test')
    await fn(ws)
    assert ws.closed == 1008 and not ws.accepted and not clients


@pytest.mark.asyncio
async def test_ws_rejects_cross_site_origin(monkeypatch):
    fn, clients, auth = ws_function({'tier':'admin','is_admin':True})
    monkeypatch.setitem(sys.modules, 'auth', auth)
    ws = WS(origin='https://evil.test')
    await fn(ws)
    assert ws.closed == 1008 and not ws.accepted and not clients


@pytest.mark.asyncio
async def test_ws_accepts_authenticated_user(monkeypatch):
    fn, clients, auth = ws_function({'tier':'free','is_admin':False})
    monkeypatch.setitem(sys.modules, 'auth', auth)
    ws = WS(origin='https://example.test')
    await fn(ws)
    assert ws.accepted and len(ws.sent)==1 and not clients
