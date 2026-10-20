"""Release regression: observable browser routing and fail-closed monitor behavior.

The source functions are executed with synthetic stand-ins, never a broker.
"""
import asyncio
import hashlib
import json
import logging
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
import sys

import pytest
from fastapi import Request
from fastapi.responses import RedirectResponse
from test_security_regression import extracted_function
from scripts.freeze_strategy_baseline import SOURCE_PATHS, calculate, verify


@pytest.mark.asyncio
async def test_ping_updates_are_deduplicated_independently_per_tier():
    admin = SimpleNamespace(send_text=AsyncMock())
    free = SimpleNamespace(send_text=AsyncMock())
    clients = {
        1: {'ws': admin, 'tier': 'admin', 'is_admin': True},
        2: {'ws': free, 'tier': 'free', 'is_admin': False},
    }
    hashes = {}

    async def ticker(tier):
        return {'type': 'ticker', 'summary': {'tier': tier}}

    push = extracted_function('main.py', 'push_event', {
        '_dashboard_clients': clients, '_last_payload_hash': hashes,
        '_build_ticker_payload': ticker, 'json': json, 'hashlib': hashlib,
        'log': logging.getLogger(__name__), '_build_ws_payload': AsyncMock(),
    })
    await push('ping')
    assert admin.send_text.await_count == 1
    assert free.send_text.await_count == 1
    await push('ping')
    assert admin.send_text.await_count == 1
    assert free.send_text.await_count == 1
    assert set(hashes) == {'admin', 'free'}


@pytest.mark.asyncio
async def test_logout_redirects_to_cloudflare_and_clears_backend_cookies(monkeypatch):
    auth = ModuleType('saas.middleware')
    auth.get_current_user = lambda _req: None
    sessions = ModuleType('saas.sessions')
    sessions.revoke_session = lambda _sid: None
    monkeypatch.setitem(sys.modules, 'saas.middleware', auth)
    monkeypatch.setitem(sys.modules, 'saas.sessions', sessions)
    logout = extracted_function('main.py', 'auth_logout', {
        'RedirectResponse': RedirectResponse, 'Request': Request,
        'frontend_location': lambda path: 'https://app.vishalkool.top' + path,
        'cfg': SimpleNamespace(SESSION_COOKIE_NAME='se_oauth'),
    })
    response = await logout(SimpleNamespace())
    assert response.status_code in (302, 307)
    assert response.headers['location'] == 'https://app.vishalkool.top/'
    assert 'se_oauth=' in response.headers['set-cookie']


@pytest.mark.asyncio
async def test_monitor_fails_closed_when_exchange_positions_fail():
    async def broken_exchange():
        raise TimeoutError('exchange timeout')
    snapshot = []
    monitor = extracted_function('trade/monitor.py', 'run_monitor_cycle', {
        '_last_snapshot_time': {},
        '_get_open_trades_from_db': lambda: [{'id': 1, 'coin': 'BTC'}],
        'get_positions': broken_exchange,
        'log': logging.getLogger(__name__),
        '_detect_exchange_closed_trades': AsyncMock(side_effect=lambda *a: snapshot.append(a)),
        '_update_funding_fees': AsyncMock(),
    })
    await monitor()
    assert not snapshot, 'No closure must be inferred from unavailable broker positions'


@pytest.mark.asyncio
async def test_monitor_fails_closed_on_empty_position_response():
    detect = AsyncMock()
    monitor = extracted_function('trade/monitor.py', 'run_monitor_cycle', {
        '_last_snapshot_time': {},
        '_get_open_trades_from_db': lambda: [{'id': 1, 'coin': 'BTC'}],
        'get_positions': AsyncMock(return_value=[]),
        'log': logging.getLogger(__name__),
        '_detect_exchange_closed_trades': detect,
        '_update_funding_fees': AsyncMock(),
    })
    await monitor()
    detect.assert_not_awaited()


def test_research_s0_hashes_detect_any_unreviewed_strategy_change(tmp_path):
    root = tmp_path / 'repo'
    for rel in SOURCE_PATHS:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'frozen: {rel}\n')
    frozen = calculate(root)
    manifest = tmp_path / 'baseline.json'
    manifest.write_text(json.dumps(frozen))
    assert verify(root, manifest) == (True, [])
    drift_file = root / SOURCE_PATHS[0]
    drift_file.write_text('changed!')
    ok, drift = verify(root, manifest)
    assert not ok and drift == [SOURCE_PATHS[0]]
    manifest.write_text(json.dumps({SOURCE_PATHS[0]: frozen[SOURCE_PATHS[0]]}))
    assert not verify(root, manifest)[0], 'Incomplete manifest must be rejected'


def test_real_repo_strategy_baseline_unchanged():
    root = Path(__file__).resolve().parents[1]
    assert verify(root, root / 'docs/engineering/STRATEGY_S0_SHA256.json') == (True, [])
