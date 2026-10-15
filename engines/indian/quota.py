"""Fail-closed, client-code-wide SmartAPI call admission and breaker.

Atomic Redis Lua uses Redis server time to enforce minimum request spacing,
minute and hour quotas across independent processes. It does NOT retry an
ambiguous order. Angel One requests made outside this gateway are NOT covered.
"""
import hashlib
import logging
import math
from dataclasses import dataclass

from engines.indian.api_limits import RATE_LIMIT_COOLDOWNS, SAFE_BUDGETS

log = logging.getLogger(__name__)

# Acquire is atomic: neither the spacing timestamp nor the counters are written
# when a request is refused. Uses Redis TIME, not skewed application clocks.
_ADMIT = """
local cooldown_ttl = redis.call('TTL', KEYS[4])
if cooldown_ttl > 0 then
  return {0, cooldown_ttl}
end
local clock = redis.call('TIME')
local now_us = tonumber(clock[1]) * 1000000 + tonumber(clock[2])
local earliest = tonumber(redis.call('GET', KEYS[1]) or '0')
if now_us < earliest then
  return {0, math.ceil((earliest - now_us) / 1000000)}
end
local minute = math.floor(tonumber(clock[1]) / 60)
local hour = math.floor(tonumber(clock[1]) / 3600)
local minute_key = KEYS[2] .. ':' .. minute
local hour_key = KEYS[3] .. ':' .. hour
if tonumber(redis.call('GET', minute_key) or '0') >= tonumber(ARGV[2]) then
  return {0, 60 - (tonumber(clock[1]) % 60)}
end
if tonumber(redis.call('GET', hour_key) or '0') >= tonumber(ARGV[3]) then
  return {0, 3600 - (tonumber(clock[1]) % 3600)}
end
redis.call('SET', KEYS[1], now_us + tonumber(ARGV[1]), 'PX', math.max(1000, math.ceil(tonumber(ARGV[1]) / 1000) + 1000))
redis.call('INCR', minute_key)
redis.call('EXPIRE', minute_key, 121)
redis.call('INCR', hour_key)
redis.call('EXPIRE', hour_key, 7201)
return {1, 0}
"""


@dataclass(frozen=True)
class RateLimitBlocked(Exception):
    operation: str
    retry_after: int
    reason: str

    def __str__(self):
        return f"Angel One {self.operation} unavailable ({self.reason}); retry in {self.retry_after}s"


def _redis():
    from redis_client import get_redis
    return get_redis()


def _namespace():
    from config import cfg
    client_code = str(cfg.ANGELONE_CLIENT_ID or '').strip()
    if not client_code:
        # Never share a rate namespace with some other unconfigured client.
        raise RateLimitBlocked('all', 300, 'client code not configured')
    return 'angelone:quota:' + hashlib.sha256(client_code.encode('utf-8')).hexdigest()[:24]


def _keys(operation):
    base = _namespace() + ':' + operation
    return [base + ':next', base + ':minute', base + ':hour', base + ':cooldown']


def blocked(operation: str) -> bool:
    """Report whether the endpoint circuit is open; Redis outage = blocked."""
    if operation not in SAFE_BUDGETS:
        raise ValueError('unknown SmartAPI operation')
    try:
        store = _redis()
        return not store or bool(store.exists(_namespace() + ':' + operation + ':cooldown'))
    except Exception:
        return True


def admit(operation: str) -> None:
    """Reserve one API call or raise; caller must NOT make an HTTP call on fail.

    Intended for all SmartAPI endpoint calls, including logins. Redis is
    REQUIRED in multi-instance deployments. Fail closed when unavailable.
    """
    if operation not in SAFE_BUDGETS:
        raise ValueError('unknown SmartAPI operation')
    try:
        store = _redis()
        if not store:
            raise RateLimitBlocked(operation, 30, 'Redis unavailable')
        keys = _keys(operation)
        budget = SAFE_BUDGETS[operation]
        admitted, delay = store.eval(
            _ADMIT, len(keys), *keys,
            int(budget['spacing'] * 1_000_000), budget['minute'], budget['hour'],
        )
        if not int(admitted):
            raise RateLimitBlocked(operation, max(1, int(delay)), 'local quota or broker cooldown')
    except RateLimitBlocked:
        raise
    except Exception as exc:
        log.error('SmartAPI quota storage failed for %s: %s', operation, type(exc).__name__)
        raise RateLimitBlocked(operation, 30, 'quota service unavailable') from exc


def trip_circuit(operation: str, *, retry_after: int | None = None) -> None:
    """Broker-side rate rejection opens only this endpoint's circuit."""
    if operation not in SAFE_BUDGETS:
        raise ValueError('unknown SmartAPI operation')
    seconds = max(RATE_LIMIT_COOLDOWNS[operation], int(retry_after or 0))
    try:
        store = _redis()
        if not store:
            raise RuntimeError('no Redis')
        store.set(_namespace() + ':' + operation + ':cooldown', '1', ex=seconds)
    except Exception as exc:
        # A Redis outage already makes admit() fail closed.
        log.error('Could not persist Angel One %s circuit: %s', operation, type(exc).__name__)
    log.warning('Angel One %s circuit opened for %ds after broker rate rejection', operation, seconds)


def status() -> dict:
    """Operator diagnostics, no account identifiers, credentials, or API tokens."""
    try:
        store = _redis()
        configured = bool(_namespace())
        if not store:
            return {'backend': 'unavailable', 'configured': configured,
                    'operations': {name: {'blocked': True} for name in SAFE_BUDGETS}}
        operations = {}
        for name, budget in SAFE_BUDGETS.items():
            seconds = store.ttl(_namespace() + ':' + name + ':cooldown')
            operations[name] = {
                'broker_cooldown_seconds': max(0, int(seconds or 0)),
                'minimum_spacing_seconds': budget['spacing'],
                'minute_budget': budget['minute'], 'hour_budget': budget['hour'],
            }
        return {'backend': 'available', 'configured': configured, 'operations': operations}
    except Exception:
        return {'backend': 'unavailable', 'configured': False,
                'operations': {name: {'blocked': True} for name in SAFE_BUDGETS}}
