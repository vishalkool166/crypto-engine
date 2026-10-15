import logging
import time
import json
import hashlib
import math
import pandas as pd
from datetime import datetime, timezone, timedelta
from engines.indian.auth import get_api
from engines.indian import quota

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

INTERVAL_MAP = {
    "1m":  "ONE_MINUTE",
    "3m":  "THREE_MINUTE",
    "5m":  "FIVE_MINUTE",
    "10m": "TEN_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "30m": "THIRTY_MINUTE",
    "1h":  "ONE_HOUR",
    "1d":  "ONE_DAY",
}

REDIS_TTL_LTP        = 15
REDIS_TTL_DAY_RANGE  = 360
REDIS_TTL_PRE_RANGE  = 28800
REDIS_TTL_PREV_RANGE = 86400
# Separate local-quota and broker cooldowns protect every network call.
REDIS_TTL_RATE_LIMIT = 120
LTP_RESPONSE_CACHE_SECONDS = 8


def _redis():
    try:
        from redis_client import get_redis
        return get_redis()
    except Exception:
        return None


def _is_rate_limited() -> bool:
    """Legacy status means LTP is blocked; a candle circuit does not block quotes."""
    return quota.blocked("ltp")


def _set_rate_limited(operation: str = "ltp") -> None:
    quota.trip_circuit(operation)


def _is_rate_limit_error(message: str) -> bool:
    msg = (message or "").lower()
    # Generic 'access denied' also means bad credentials or an IP policy.
    return any(phrase in msg for phrase in (
        "exceeding access rate", "rate limit", "too many requests", "ab1021",
    ))


def _is_rate_limit_exception(exc: Exception) -> bool:
    return _is_rate_limit_error(str(exc)) or _is_rate_limit_error(repr(exc))


def _cache_key(kind: str, request: dict) -> str:
    # Never expose tokens or client code in Redis keys.
    data = json.dumps(request, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(data.encode()).hexdigest()
    return f"{quota._namespace()}:cache:{kind}:{fingerprint}"


def _cached_response(key: str):
    try:
        redis = _redis()
        if redis:
            raw = redis.get(key)
            if raw:
                return json.loads(raw)
    except Exception as exc:
        log.warning("SmartAPI response-cache read error: %s", type(exc).__name__)
    return None


def _cache_response(key: str, value, ttl: int) -> None:
    try:
        redis = _redis()
        if redis:
            redis.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        log.warning("SmartAPI response-cache write error: %s", type(exc).__name__)


def _candles_from_rows(candles: list) -> pd.DataFrame | None:
    rows = []
    for candle in candles:
        if not isinstance(candle, (list, tuple)) or len(candle) < 6:
            return None
        try:
            timestamp = pd.Timestamp(candle[0])
            o, h, l, c, v = (float(x) for x in candle[1:6])
            if (pd.isna(timestamp) or not all(math.isfinite(x) for x in (o, h, l, c, v))
                    or min(o, h, l, c) <= 0 or v < 0 or l > min(o, c) or h < max(o, c)):
                return None
        except (ValueError, TypeError):
            return None
        rows.append({"timestamp": timestamp, "open": o, "high": h,
                     "low": l, "close": c, "volume": v})
    return pd.DataFrame(rows).set_index("timestamp").sort_index() if rows else None


def _set_last_refresh():
    try:
        r = _redis()
        if r:
            r.set("indian:last_refresh", str(time.time()))
    except Exception:
        pass


def get_last_refresh_age() -> float:
    try:
        r = _redis()
        if not r:
            return 999.0
        val = r.get("indian:last_refresh")
        if not val:
            return 999.0
        return round(time.time() - float(val), 0)
    except Exception:
        return 999.0


def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def is_orb_ready() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    orb_ready    = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return orb_ready <= now <= market_close


def fetch_candles(
    token: str,
    interval: str,
    from_date: str,
    to_date: str,
) -> pd.DataFrame | None:
    """Historical candles, cached by request, broker-throttled and fail-closed.

    No retry after 403/AB1021. Historical circuit does NOT disable LTP.
    Unknown intervals, bad date ranges, and malformed OHLCV fail locally.
    """
    if interval not in INTERVAL_MAP or not str(token).strip():
        log.warning("Invalid Angel One candle parameters")
        return None
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d %H:%M")
        end = datetime.strptime(to_date, "%Y-%m-%d %H:%M")
        if end < start or (end - start).days > 35:
            return None
    except (TypeError, ValueError):
        return None

    params = {"exchange": "NFO", "symboltoken": str(token),
              "interval": INTERVAL_MAP[interval], "fromdate": from_date, "todate": to_date}
    try:
        key = _cache_key('candles', params)
        stored = _cached_response(key)
        if stored is not None:
            return _candles_from_rows(stored)

        # Fast fail instead of sleeping inside a request/scheduler worker.
        if quota.blocked('candles'):
            log.warning("fetch_candles skipped: historical circuit unavailable")
            return None
        api = get_api()
        if not api:
            log.warning("fetch_candles: Angel One session unavailable")
            return None
        quota.admit('candles')
        response = api.getCandleData(params)
        if not isinstance(response, dict) or not response.get('status'):
            message = response.get('message', '') if isinstance(response, dict) else ''
            error_code = response.get('errorcode', '') if isinstance(response, dict) else ''
            if _is_rate_limit_error(f"{message} {error_code}"):
                _set_rate_limited('candles')
                log.warning("Angel One historical candle broker throttling")
            else:
                log.warning("Angel One historical data failed: %s", str(error_code)[:30])
            return None
        candles = response.get('data')
        if not candles:
            return None
        df = _candles_from_rows(candles)
        if df is None or df.empty:
            log.error('Invalid OHLCV response rejected')
            return None
        # Today's candles can change; completed historical windows are reusable.
        ttl = 86400 if end < datetime.now() - timedelta(days=1) else 90
        _cache_response(key, candles, ttl)
        return df
    except quota.RateLimitBlocked as exc:
        log.info("fetch_candles skipped (%s, retry ~%ds)", exc.reason, exc.retry_after)
        return None
    except Exception as exc:
        if _is_rate_limit_exception(exc):
            _set_rate_limited('candles')
            log.warning("Historical candle broker throttling: %s", type(exc).__name__)
        else:
            log.error("fetch_candles failed: %s", type(exc).__name__)
        return None


def _symbol_for_token(token: str, exchange: str) -> str | None:
    from engines.indian.instruments import get_instruments
    for instrument in get_instruments().values():
        if str(instrument.get('token')) == str(token) and instrument.get('exchange') == exchange:
            return instrument.get('symbol')
    return None


def get_ltp_live(token: str, exchange: str = "NFO", tradingsymbol: str | None = None) -> dict | None:
    """Quotes are independently gated; recent successful responses are reused."""
    try:
        if not str(token).strip() or not exchange:
            return None
        cache_key = _cache_key('ltp', {'exchange': exchange, 'token': str(token)})
        cached = _cached_response(cache_key)
        if cached is not None:
            return cached
        if quota.blocked('ltp'):
            return None
        if not tradingsymbol:
            tradingsymbol = _symbol_for_token(str(token), exchange)
        if not tradingsymbol:
            log.warning('No trading symbol found for LTP token; request not sent')
            return None
        api = get_api()
        if not api:
            return None
        quota.admit('ltp')
        resp = api.ltpData(exchange=exchange, tradingsymbol=tradingsymbol, symboltoken=str(token))
        if not isinstance(resp, dict) or not resp.get('status'):
            msg = (resp.get('message', '') + ' ' + str(resp.get('errorcode', ''))) if isinstance(resp, dict) else ''
            if _is_rate_limit_error(msg):
                _set_rate_limited('ltp')
            else:
                log.warning('get_ltp_live broker returned error')
            return None
        values = resp.get('data') or {}
        if not values:
            return None
        result = {name: float(values.get(name, 0)) for name in ('ltp', 'open', 'high', 'low', 'close')}
        if (not math.isfinite(result['ltp']) or result['ltp'] <= 0
                or not all(math.isfinite(v) and v >= 0 for v in result.values())):
            log.error('Invalid live LTP response rejected')
            return None
        if result['high'] and result['low'] and result['high'] < result['low']:
            return None
        _cache_response(cache_key, result, LTP_RESPONSE_CACHE_SECONDS)
        store_ltp(str(token), result['ltp'])
        if result['high'] and result['low']:
            store_day_range(str(token), result['high'] - result['low'])
        _set_last_refresh()
        return result
    except quota.RateLimitBlocked as exc:
        log.info('get_ltp_live quota blocked: %s (%ds)', exc.reason, exc.retry_after)
        return None
    except Exception as exc:
        if _is_rate_limit_exception(exc):
            _set_rate_limited('ltp')
            log.warning('Angel One LTP broker throttling')
        else:
            log.error('get_ltp_live error: %s', type(exc).__name__)
        return None


def get_ltp_from_redis(token: str) -> float | None:
    try:
        r = _redis()
        if not r:
            return None
        val = r.get(f"indian:ltp:{token}")
        if val:
            return float(val)
        return None
    except Exception:
        return None


def get_day_range_from_redis(token: str) -> float:
    try:
        r = _redis()
        if not r:
            return 0.0
        val = r.get(f"indian:day_range:{token}")
        if val:
            return float(val)
        return 0.0
    except Exception:
        return 0.0


def store_day_range(token: str, day_range: float) -> None:
    try:
        r = _redis()
        if r:
            r.setex(f"indian:day_range:{token}", REDIS_TTL_DAY_RANGE, str(day_range))
    except Exception:
        pass


def store_ltp(token: str, price: float) -> None:
    try:
        r = _redis()
        if r:
            r.setex(f"indian:ltp:{token}", REDIS_TTL_LTP, str(price))
    except Exception:
        pass


def get_pre_range_from_redis(token: str) -> float:
    try:
        r = _redis()
        if not r:
            return 0.0
        val = r.get(f"indian:pre_range:{token}")
        if val:
            return float(val)
        return 0.0
    except Exception:
        return 0.0


def store_pre_range(token: str, pre_range: float) -> None:
    try:
        r = _redis()
        if r:
            r.setex(f"indian:pre_range:{token}", REDIS_TTL_PRE_RANGE, str(pre_range))
            log.info("Pre-range stored: token=%s pre_range=%.2f", token, pre_range)
    except Exception:
        pass


def get_prev_range_from_redis(token: str) -> float:
    try:
        r = _redis()
        if not r:
            return 0.0
        val = r.get(f"indian:prev_range:{token}")
        if val:
            return float(val)
        return 0.0
    except Exception:
        return 0.0


def store_prev_range(token: str, prev_range: float) -> None:
    try:
        r = _redis()
        if r:
            r.setex(f"indian:prev_range:{token}", REDIS_TTL_PREV_RANGE, str(prev_range))
            log.info("Prev-range stored: token=%s prev_range=%.2f", token, prev_range)
    except Exception:
        pass


def fetch_pre_range(token: str) -> float:
    try:
        if quota.blocked('candles'):
            log.warning("fetch_pre_range skipped — historical circuit")
            return get_pre_range_from_redis(token)

        now       = datetime.now(IST)
        today     = now.strftime("%Y-%m-%d")
        from_date = f"{today} 09:15"
        to_date   = f"{today} 10:45"

        df = fetch_candles(token, "15m", from_date, to_date)
        if df is None or df.empty:
            log.warning("fetch_pre_range: no candles returned")
            return get_pre_range_from_redis(token)

        pre_high  = float(df["high"].max())
        pre_low   = float(df["low"].min())
        pre_range = round(pre_high - pre_low, 2)

        store_pre_range(token, pre_range)
        log.info("Pre-range fetched: %.2f pts (%d candles)", pre_range, len(df))
        return pre_range

    except Exception as e:
        log.error("fetch_pre_range error: %s", e)
        return get_pre_range_from_redis(token)


def fetch_prev_day_range(token: str) -> float:
    """Look back over real weekdays, avoiding weekend 403/empty-data bursts."""
    try:
        if quota.blocked('candles'):
            return get_prev_range_from_redis(token)
        from datetime import timedelta
        today = datetime.now(IST).date()
        attempted = 0
        for days_back in range(1, 9):
            day = today - timedelta(days=days_back)
            if day.weekday() >= 5:
                continue
            if attempted:
                # If a market holiday produced no data, pace the next lookup.
                time.sleep(5.3)
            date_str = day.strftime('%Y-%m-%d')
            df = fetch_candles(token, '15m', f'{date_str} 09:15', f'{date_str} 15:30')
            attempted += 1
            if df is not None and not df.empty:
                value = round(float(df['high'].max() - df['low'].min()), 2)
                store_prev_range(token, value)
                return value
            if quota.blocked('candles'):
                break
            # One retry for a likely exchange holiday; further historical
            # probing is deferred to a human rather than hammering an API.
            if attempted >= 2:
                break
        return get_prev_range_from_redis(token)
    except Exception as exc:
        log.error('fetch_prev_day_range failed: %s', type(exc).__name__)
        return get_prev_range_from_redis(token)


def refresh_indian_data(token: str, name: str) -> dict:
    result = {
        "name":         name,
        "token":        token,
        "ltp":          None,
        "day_range":    0.0,
        "success":      False,
        "rate_limited": False,
    }

    if _is_rate_limited():
        result["rate_limited"] = True
        log.warning("refresh_indian_data skipped — rate limited")
        return result

    try:
        from engines.indian.instruments import get_instrument
        instrument = get_instrument(name)
        ltp_data = get_ltp_live(token, tradingsymbol=instrument['symbol'] if instrument else None)

        if ltp_data:
            ltp       = ltp_data["ltp"]
            day_high  = ltp_data["high"]
            day_low   = ltp_data["low"]
            day_range = round(day_high - day_low, 2)

            store_ltp(token, ltp)
            store_day_range(token, day_range)
            _set_last_refresh()

            result["ltp"]       = ltp
            result["day_range"] = day_range
            result["success"]   = True

            log.debug(
                "Indian data refreshed: %s ltp=%.2f day_range=%.2f",
                name, ltp, day_range
            )
        else:
            if _is_rate_limited():
                result["rate_limited"] = True
            log.warning("refresh_indian_data: getLtpData returned no data for %s", name)

    except Exception as e:
        if _is_rate_limit_exception(e):
            _set_rate_limited('ltp')
            result["rate_limited"] = True
            log.error("refresh_indian_data rate limited (exception): %s", e)
        else:
            log.error("refresh_indian_data %s: %s", name, e)

    return result


def get_orb_candle(token: str) -> dict | None:
    try:
        now       = datetime.now(IST)
        today     = now.strftime("%Y-%m-%d")
        from_date = f"{today} 09:15"
        to_date   = f"{today} 09:30"

        df = fetch_candles(token, "15m", from_date, to_date)
        if df is None or df.empty:
            return None

        first = df.iloc[0]
        return {
            "open":   float(first["open"]),
            "high":   float(first["high"]),
            "low":    float(first["low"]),
            "close":  float(first["close"]),
            "volume": float(first["volume"]),
            "date":   today,
        }

    except Exception as e:
        log.error("get_orb_candle error: %s", e)
        return None


def get_avg_volume(token: str, days: int = 10) -> float:
    try:
        now       = datetime.now(IST)
        from_date = (now - timedelta(days=days + 5)).strftime("%Y-%m-%d 09:15")
        to_date   = now.strftime("%Y-%m-%d 15:30")

        df = fetch_candles(token, "15m", from_date, to_date)
        if df is None or df.empty:
            return 0.0

        return float(df["volume"].tail(days).mean())

    except Exception as e:
        log.error("get_avg_volume error: %s", e)
        return 0.0