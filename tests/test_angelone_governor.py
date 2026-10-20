"""Offline Angel One regression tests. No market-data API or live orders.

FakeRedis models the atomic Lua decision; deploy validation MUST also execute
_ADMIT against a real Redis service (not available in this isolated harness).
"""
import importlib
import math
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from types import ModuleType, SimpleNamespace

import pytest

# Minimal test-only shim: production pyotp is installed from requirements.txt.
try:
    import pyotp  # noqa: F401
except ImportError:
    pyotp_shim = ModuleType('pyotp')
    pyotp_shim.TOTP = lambda secret: SimpleNamespace(now=lambda: '000000')
    sys.modules['pyotp'] = pyotp_shim

from engines.indian import api_limits, quota, data


class FakeRedis:
    def __init__(self, clock=10000.0):
        self.clock = clock
        self.values = {}
        self._lock = threading.RLock()
        self.fail_eval = False
        self.calls = 0

    def _get(self, key):
        entry = self.values.get(key)
        if entry and entry[1] is not None and self.clock >= entry[1]:
            self.values.pop(key, None)
            return None
        return entry[0] if entry else None

    def get(self, key):
        with self._lock:
            return self._get(key)

    def set(self, key, value, ex=None, nx=False):
        with self._lock:
            if nx and self._get(key) is not None:
                return False
            self.values[key] = (str(value), self.clock + ex if ex else None)
            return True

    def delete(self, key):
        with self._lock:
            self.values.pop(key, None)

    def setex(self, key, ttl, value):
        self.set(key, value, ex=ttl)

    def ttl(self, key):
        with self._lock:
            value = self._get(key)
            if value is None:
                return -2
            expiry = self.values[key][1]
            return math.ceil(expiry - self.clock) if expiry is not None else -1

    def exists(self, key):
        return bool(self.get(key) is not None)

    def eval(self, lua, count, *args):
        if self.fail_eval:
            raise ConnectionError('simulated outage')
        assert 'TIME' in lua and 'TTL' in lua and count == 4
        keys = args[:count]
        spacing_us, limit_minute, limit_hour = args[count:]
        with self._lock:
            self.calls += 1
            if self.ttl(keys[3]) > 0:
                return (0, self.ttl(keys[3]))
            earliest = int(self._get(keys[0]) or 0)
            now_us = int(self.clock * 1_000_000)
            if now_us < earliest:
                return 0, math.ceil((earliest - now_us) / 1_000_000)
            minute = f'{keys[1]}:{int(self.clock) // 60}'
            hour = f'{keys[2]}:{int(self.clock) // 3600}'
            if int(self._get(minute) or 0) >= int(limit_minute):
                return 0, 60 - (int(self.clock) % 60)
            if int(self._get(hour) or 0) >= int(limit_hour):
                return 0, 3600 - (int(self.clock) % 3600)
            self.set(keys[0], now_us + int(spacing_us), ex=max(1, int(math.ceil(spacing_us / 1_000_000)) + 1))
            self.set(minute, int(self._get(minute) or 0) + 1, ex=121)
            self.set(hour, int(self._get(hour) or 0) + 1, ex=7201)
            return 1, 0


@pytest.fixture
def fake_store(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(quota, '_redis', lambda: fake)
    monkeypatch.setattr(quota, '_namespace', lambda: 'test:account:hash')
    monkeypatch.setattr(data, '_redis', lambda: fake)
    return fake


def test_documented_ceilings_and_order_group():
    assert api_limits.ANGELONE_API_LIMITS['candles']['per_minute'] == 150
    assert api_limits.ANGELONE_API_LIMITS['order']['per_second'] == 9
    for name, budget in api_limits.SAFE_BUDGETS.items():
        official = api_limits.ANGELONE_API_LIMITS[name]
        assert 1 / budget['spacing'] <= official['per_second']
        for window, official_window in [('minute', 'per_minute'), ('hour', 'per_hour')]:
            if official[official_window] is not None:
                assert budget[window] <= official[official_window]
    assert 'order' in api_limits.SAFE_BUDGETS  # shared across all 3 order actions


def test_spacing_enforced_and_different_operations_independent(fake_store):
    quota.admit('candles')
    with pytest.raises(quota.RateLimitBlocked) as err:
        quota.admit('candles')
    assert err.value.retry_after >= 1
    quota.admit('ltp')
    fake_store.clock += 5.1
    quota.admit('candles')


def test_concurrent_admission_has_only_one_winner(fake_store):
    def reserve(_):
        try:
            quota.admit('candles')
            return True
        except quota.RateLimitBlocked:
            return False
    with ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = list(pool.map(reserve, range(30)))
    assert sum(outcomes) == 1


def test_broker_circuit_is_per_endpoint(fake_store):
    quota.trip_circuit('candles')
    assert quota.blocked('candles')
    assert not quota.blocked('ltp')
    with pytest.raises(quota.RateLimitBlocked):
        quota.admit('candles')
    quota.admit('ltp')
    fake_store.clock += 601
    assert not quota.blocked('candles')


def test_storage_outage_fails_closed(monkeypatch, fake_store):
    monkeypatch.setattr(quota, '_redis', lambda: None)
    assert quota.blocked('candles')
    with pytest.raises(quota.RateLimitBlocked, match='Redis unavailable'):
        quota.admit('candles')
    monkeypatch.setattr(quota, '_redis', lambda: fake_store)
    fake_store.fail_eval = True
    with pytest.raises(quota.RateLimitBlocked, match='quota service unavailable'):
        quota.admit('ltp')


def test_limits_on_broker_side_are_reported_without_secrets(fake_store):
    quota.trip_circuit('candles')
    result = quota.status()
    assert result['backend'] == 'available'
    assert result['operations']['candles']['broker_cooldown_seconds'] == 600
    assert 'client' not in str(result).lower()


class FakeAPI:
    def __init__(self):
        self.candle_calls = 0
        self.ltp_calls = 0
        self.candles_response = {'status': True, 'data': [
            ['2026-10-01 09:15', 100, 111, 95, 105, 50],
            ['2026-10-01 09:30', 105, 112, 100, 110, 70],
        ]}
        self.ltp_response = {'status': True, 'data': {
            'ltp': 108, 'open': 102, 'high': 115, 'low': 99, 'close': 107,
        }}
        self.last_symbol = None

    def getCandleData(self, params):
        self.candle_calls += 1
        return self.candles_response

    def ltpData(self, **params):
        self.ltp_calls += 1
        self.last_symbol = params['tradingsymbol']
        return self.ltp_response


@pytest.fixture
def mock_smartapi(fake_store, monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(data, 'get_api', lambda: api)
    return api


def test_candle_request_is_cached_before_quota(mock_smartapi, fake_store):
    params = ('101', '15m', '2026-10-01 09:15', '2026-10-01 09:30')
    first = data.fetch_candles(*params)
    second = data.fetch_candles(*params)
    assert first is not None and first.equals(second)
    assert mock_smartapi.candle_calls == 1
    assert len(first) == 2


def test_historical_rate_rejection_leaves_ltp_available(mock_smartapi, fake_store):
    mock_smartapi.candles_response = {'status': False, 'message': 'Too many requests', 'errorcode': 'AB1021'}
    assert data.fetch_candles('101', '15m', '2026-10-01 09:15', '2026-10-01 09:30') is None
    assert quota.blocked('candles')
    assert not quota.blocked('ltp')
    assert data.get_ltp_live('101', tradingsymbol='BANKNIFTYFUT') is not None
    assert mock_smartapi.ltp_calls == 1
    assert data.fetch_candles('101', '15m', '2026-10-01 09:15', '2026-10-01 09:30') is None
    assert mock_smartapi.candle_calls == 1


def test_quote_cache_and_correct_trading_symbol(mock_smartapi, fake_store):
    price = data.get_ltp_live('987', tradingsymbol='BANKNIFTY26OCTFUT')
    assert price['ltp'] == 108
    assert mock_smartapi.last_symbol == 'BANKNIFTY26OCTFUT'
    second = data.get_ltp_live('987', tradingsymbol='BANKNIFTY26OCTFUT')
    assert second == price and mock_smartapi.ltp_calls == 1
    assert data.get_ltp_from_redis('987') == 108


def test_ltp_cache_expires_and_stale_quote_is_not_reused(fake_store):
    data.store_ltp('987', 108.0)
    assert data.get_ltp_from_redis('987') == 108.0
    fake_store.clock += data.REDIS_TTL_LTP + 1
    assert data.get_ltp_from_redis('987') is None


def test_no_broker_call_for_invalid_candle_request(mock_smartapi):
    assert data.fetch_candles('101', 'INVALID', '2026-10-01 09:15', '2026-10-01 09:30') is None
    assert data.fetch_candles('101', '15m', '2026-10-02 09:15', '2026-10-01 09:30') is None
    assert mock_smartapi.candle_calls == 0


@pytest.mark.parametrize(('instant', 'market_open', 'orb_ready'), [
    (datetime(2026, 10, 19, 9, 14, 59, tzinfo=timezone(timedelta(hours=5, minutes=30))), False, False),
    (datetime(2026, 10, 19, 9, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))), True, False),
    (datetime(2026, 10, 19, 9, 29, 59, tzinfo=timezone(timedelta(hours=5, minutes=30))), True, False),
    (datetime(2026, 10, 19, 9, 30, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))), True, True),
    (datetime(2026, 10, 19, 15, 30, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))), True, True),
    (datetime(2026, 10, 19, 15, 30, 1, tzinfo=timezone(timedelta(hours=5, minutes=30))), False, False),
    (datetime(2026, 10, 18, 10, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))), False, False),
])
def test_market_and_orb_session_boundaries(monkeypatch, instant, market_open, orb_ready):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    monkeypatch.setattr(data, 'datetime', FixedDateTime)
    assert data.is_market_open() is market_open
    assert data.is_orb_ready() is orb_ready


def test_bad_price_or_candle_data_rejected(mock_smartapi, fake_store):
    mock_smartapi.ltp_response['data']['ltp'] = float('nan')
    assert data.get_ltp_live('102', tradingsymbol='FOOFUT') is None
    mock_smartapi.candles_response['data'][0][2] = 90  # high below open
    assert data.fetch_candles('102', '15m', '2026-10-01 09:15', '2026-10-01 09:30') is None


def test_broker_exception_trip_only_its_circuit(mock_smartapi, fake_store, monkeypatch):
    def fail(**kwargs):
        raise ValueError('DataException: exceeding access rate')
    monkeypatch.setattr(mock_smartapi, 'ltpData', fail)
    assert data.get_ltp_live('103', tradingsymbol='FOOFUT') is None
    assert quota.blocked('ltp') and not quota.blocked('candles')


def test_auth_get_api_attempts_login_once(monkeypatch):
    pyotp = ModuleType('pyotp')
    pyotp.TOTP = lambda secret: SimpleNamespace(now=lambda: '000000')
    monkeypatch.setitem(sys.modules, 'pyotp', pyotp)
    auth = importlib.import_module('engines.indian.auth')
    monkeypatch.setattr(auth, '_api', None)
    monkeypatch.setattr(auth, '_session_at', 0)
    calls = []
    monkeypatch.setattr(auth, '_login', lambda: calls.append(1) or False)
    assert auth.get_api() is None
    assert len(calls) == 1


def test_failed_session_refresh_preserves_current_session(monkeypatch):
    auth = importlib.import_module('engines.indian.auth')
    existing = object()
    monkeypatch.setattr(auth, '_api', existing)
    monkeypatch.setattr(auth, '_session_at', 1234.0)
    monkeypatch.setattr(auth, '_login', lambda: False)
    assert auth.refresh_session() is None
    assert auth._api is existing
    assert auth._session_at == 1234.0


def test_minute_and_hour_budgets_are_enforced(fake_store, monkeypatch):
    # Force tiny test quotas without modifying production configuration.
    from engines.indian import api_limits
    monkeypatch.setitem(api_limits.SAFE_BUDGETS, 'candles', {
        'spacing': 0.1, 'minute': 2, 'hour': 3,
    })
    quota.admit('candles')
    fake_store.clock += 0.5
    quota.admit('candles')
    fake_store.clock += 0.5
    with pytest.raises(quota.RateLimitBlocked):
        quota.admit('candles')  # 2/minute
    fake_store.clock += 60
    quota.admit('candles')
    fake_store.clock += 0.5
    with pytest.raises(quota.RateLimitBlocked):
        quota.admit('candles')  # 3/hour
    fake_store.clock += 3600
    quota.admit('candles')


def test_403_access_denied_without_rate_context_does_not_open_breaker(mock_smartapi, fake_store):
    mock_smartapi.candles_response = {'status': False, 'message': 'Access denied: incorrect IP'}
    assert data.fetch_candles('902', '15m', '2026-10-01 09:15', '2026-10-01 09:30') is None
    assert not quota.blocked('candles')


def test_login_quota_blocks_repeated_login_network_calls(fake_store, monkeypatch):
    auth = importlib.import_module('engines.indian.auth')
    # No actual TOTP secrets, SDK or Angel One requests are used.
    monkeypatch.setattr(auth.pyotp, 'TOTP', lambda _secret: SimpleNamespace(now=lambda: '000000'))
    monkeypatch.setattr(auth, 'cfg', SimpleNamespace(
        ANGELONE_CLIENT_ID='FAKE', ANGELONE_API_KEY='FAKE',
        ANGELONE_PASSWORD='FAKE', ANGELONE_TOTP_SECRET='FAKE',
    ))
    session_attempts = []
    sdk = ModuleType('SmartApi')

    class Client:
        def __init__(self, api_key):
            pass

        def generateSession(self, *args):
            session_attempts.append(1)
            return {'status': False, 'message': 'Invalid credentials'}

    sdk.SmartConnect = Client
    monkeypatch.setitem(sys.modules, 'SmartApi', sdk)
    assert not auth._login()
    assert not auth._login()
    assert len(session_attempts) == 1



def test_stale_orb_is_not_reused_after_restart(monkeypatch, fake_store):
    from engines.indian import scanner
    from types import ModuleType
    old = {'date': '2026-10-14', 'high': 200, 'low': 100}
    monkeypatch.setattr(scanner, '_today_ist', lambda: '2026-10-15')
    monkeypatch.setattr(scanner, '_orb_levels', {'BANKNIFTY': old})
    fake_store.set('indian:orb:BANKNIFTY', __import__('json').dumps(old))
    redis_client_stub = ModuleType('redis_client')
    redis_client_stub.get_redis = lambda: fake_store
    monkeypatch.setitem(sys.modules, 'redis_client', redis_client_stub)
    assert scanner.get_orb_levels('BANKNIFTY') is None
    fresh = dict(old, date='2026-10-15')
    fake_store.set('indian:orb:BANKNIFTY', __import__('json').dumps(fresh))
    assert scanner.get_orb_levels('BANKNIFTY') == fresh


def test_indian_signal_claim_prevents_restart_duplicates(monkeypatch, fake_store):
    from engines.indian import scanner
    monkeypatch.setattr(scanner, '_today_ist', lambda: '2026-10-15')
    redis_client_stub = ModuleType('redis_client')
    redis_client_stub.get_redis = lambda: fake_store
    monkeypatch.setitem(sys.modules, 'redis_client', redis_client_stub)
    assert scanner._claim_signal('BANKNIFTY')
    monkeypatch.setattr(scanner, '_signals_today', {})
    assert not scanner._claim_signal('BANKNIFTY')
    scanner._release_signal_claim('BANKNIFTY')
    assert scanner._claim_signal('BANKNIFTY')
