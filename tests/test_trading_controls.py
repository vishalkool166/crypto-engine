"""Step-up and audit requirements for controls that can alter execution flow."""
import asyncio
import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException


@pytest.fixture
def trading_api(monkeypatch):
    module = importlib.import_module('api.trading')
    monkeypatch.setattr(module, '_auth', lambda request: None)
    return module


def request_with_totp(code):
    return SimpleNamespace(
        json=AsyncMock(return_value={'totp_code': code}),
        client=SimpleNamespace(host='127.0.0.1'),
    )


def close_request(trade_id, code, **extra):
    request = request_with_totp(code)
    request.json = AsyncMock(return_value={'trade_id': trade_id, 'totp_code': code, **extra})
    return request


def body_request(body):
    return SimpleNamespace(json=AsyncMock(return_value=body), client=SimpleNamespace(host='127.0.0.1'))


@pytest.mark.asyncio
@pytest.mark.parametrize('route_name,audit_action', [
    ('trades_start', 'scanner_start'),
    ('trades_stop', 'monitor_stop'),
])
async def test_scanner_and_monitor_controls_reject_invalid_totp(trading_api, monkeypatch, route_name, audit_action):
    audit_rows = []
    monkeypatch.setattr(trading_api, 'verify_totp', lambda code: False)
    monkeypatch.setattr('auth.audit', lambda *args, **kwargs: audit_rows.append((args, kwargs)))

    response = await getattr(trading_api, route_name)(request_with_totp('000000'))

    assert response.status_code == 401
    assert audit_rows[0][0][0] == audit_action
    assert audit_rows[0][1]['success'] is False


@pytest.mark.asyncio
async def test_scanner_start_requires_valid_step_up_and_audits(monkeypatch, trading_api):
    monkeypatch.setattr(trading_api, 'verify_totp', lambda code: code == '123456')
    events = []
    scanner = ModuleType('alerts.scanner')

    async def scan_all_coins():
        events.append('scan')

    scanner.scan_all_coins = scan_all_coins
    monkeypatch.setitem(sys.modules, 'alerts.scanner', scanner)
    monkeypatch.setattr('auth.audit', lambda action, *args, **kwargs: events.append(action))
    tasks = []

    def schedule(coroutine):
        tasks.append(coroutine)
        coroutine.close()

    monkeypatch.setattr(asyncio, 'create_task', schedule)
    response = await trading_api.trades_start(request_with_totp('123456'))

    assert response.status_code == 200
    assert len(tasks) == 1
    assert events == ['scanner_start']


@pytest.mark.asyncio
async def test_monitor_stop_requires_valid_step_up_and_audits(monkeypatch, trading_api):
    monkeypatch.setattr(trading_api, 'verify_totp', lambda code: code == '654321')
    events = []
    monitor = ModuleType('trade.monitor')
    monitor.stop_monitor = lambda: events.append('stopped')
    monkeypatch.setitem(sys.modules, 'trade.monitor', monitor)
    monkeypatch.setattr('auth.audit', lambda action, *args, **kwargs: events.append(action))

    response = await trading_api.trades_stop(request_with_totp('654321'))

    assert response.status_code == 200
    assert events == ['stopped', 'monitor_stop']


@pytest.mark.asyncio
async def test_manual_close_uses_trade_record_instead_of_caller_symbol(monkeypatch, trading_api):
    import database
    import trade.executor as executor

    stored = SimpleNamespace(id=7, coin='ETH', direction='LONG', is_active=True, state='open')

    class Query:
        def filter(self, *_):
            return self

        def first(self):
            return stored

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def query(self, _):
            return Query()

    monkeypatch.setattr(database, 'get_session', lambda: Session())
    monkeypatch.setattr(trading_api, 'verify_totp', lambda code: code == '123456')
    calls = []

    async def close_position(**kwargs):
        calls.append(kwargs)
        return {'success': True}

    monkeypatch.setattr(executor, 'close_position', close_position)
    audit_rows = []
    monkeypatch.setattr('auth.audit', lambda *args, **kwargs: audit_rows.append((args, kwargs)))

    response = await trading_api.trades_close(
        close_request(7, '123456', coin='BTC', direction='SHORT'))

    assert response.status_code == 200
    assert calls == [{'coin': 'ETH', 'direction': 'LONG', 'trade_id': 7, 'reason': 'manual_close'}]
    assert audit_rows[-1][0][0] == 'manual_trade_close'
    assert audit_rows[-1][1]['success'] is True


@pytest.mark.asyncio
async def test_manual_close_rejects_non_active_trade_and_audits_failure(monkeypatch, trading_api):
    import database
    import trade.executor as executor

    stored = SimpleNamespace(id=9, coin='SOL', direction='SHORT', is_active=False, state='closed')

    class Query:
        def filter(self, *_):
            return self

        def first(self):
            return stored

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def query(self, _):
            return Query()

    monkeypatch.setattr(database, 'get_session', lambda: Session())
    monkeypatch.setattr(trading_api, 'verify_totp', lambda code: True)
    monkeypatch.setattr(executor, 'close_position', AsyncMock(side_effect=AssertionError('must not execute')))
    audit_rows = []
    monkeypatch.setattr('auth.audit', lambda *args, **kwargs: audit_rows.append((args, kwargs)))

    with pytest.raises(HTTPException) as exc:
        await trading_api.trades_close(close_request(9, '123456'))
    assert exc.value.status_code == 409
    assert audit_rows[-1][0][0] == 'manual_trade_close'
    assert audit_rows[-1][1]['success'] is False


def test_new_exposure_halt_persists_and_malformed_state_fails_closed(monkeypatch, tmp_path):
    import runtime_state as rs
    from trade.safety import ensure_new_exposure_allowed

    state_file = tmp_path / 'runtime_state.json'
    monkeypatch.setattr(rs, 'STATE_FILE', str(state_file))
    monkeypatch.setattr(rs, '_state', {})
    halted = rs.set_new_exposure_halt(True, 'operator incident response')
    assert halted['enabled'] is True
    assert rs.get_new_exposure_halt()['reason'] == 'operator incident response'
    with pytest.raises(PermissionError, match='operator incident response'):
        ensure_new_exposure_allowed()

    rs._state['new_exposure_halt'] = {'unexpected': 'shape'}
    assert rs.get_new_exposure_halt()['enabled'] is True
    with pytest.raises(PermissionError, match='invalid_persisted_state'):
        ensure_new_exposure_allowed()


@pytest.mark.asyncio
async def test_kill_switch_halt_is_audited_and_reset_requires_live_reconciliation(
    monkeypatch, tmp_path, trading_api
):
    import runtime_state as rs
    import trade.exchange as exchange
    import database
    import trade.order_journal as journal

    monkeypatch.setattr(rs, 'STATE_FILE', str(tmp_path / 'runtime_state.json'))
    monkeypatch.setattr(rs, '_state', {})
    monkeypatch.setattr(trading_api, 'verify_totp', lambda code: code == '123456')
    audits = []
    monkeypatch.setattr('auth.audit', lambda *args, **kwargs: audits.append((args, kwargs)))

    response = await trading_api.trades_kill_switch(body_request({
        'action': 'halt', 'reason': 'manual incident', 'totp_code': '123456'}))
    assert response.status_code == 200
    assert rs.get_new_exposure_halt()['enabled'] is True
    assert audits[-1][0][0] == 'entry_kill_switch'

    monkeypatch.setattr(exchange, 'get_positions', AsyncMock(return_value=[{'symbol': 'ETHUSDT'}]))
    with pytest.raises(HTTPException) as exc:
        await trading_api.trades_kill_switch(body_request({
            'action': 'reset', 'confirmation': 'I_HAVE_RECONCILED', 'totp_code': '123456'}))
    assert exc.value.status_code == 409
    assert rs.get_new_exposure_halt()['enabled'] is True
    assert audits[-1][1]['success'] is False

    monkeypatch.setattr(exchange, 'get_positions', AsyncMock(return_value=[]))
    monkeypatch.setattr(database, 'get_session', lambda: _CountSession(0))
    monkeypatch.setattr(journal, 'unresolved', lambda: [])
    # A reset has to follow an active halt, even if current account state is clear.
    response = await trading_api.trades_kill_switch(body_request({
        'action': 'reset', 'confirmation': 'I_HAVE_RECONCILED', 'totp_code': '123456'}))
    assert response.status_code == 200
    assert rs.get_new_exposure_halt()['enabled'] is False

    with pytest.raises(HTTPException) as exc:
        await trading_api.trades_kill_switch(body_request({
            'action': 'reset', 'confirmation': 'I_HAVE_RECONCILED', 'totp_code': '123456'}))
    assert exc.value.status_code == 409


class _CountQuery:
    def __init__(self, count):
        self.value = count

    def filter(self, *_):
        return self

    def count(self):
        return self.value


class _CountSession:
    def __init__(self, count):
        self.value = count

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def query(self, _):
        return _CountQuery(self.value)
