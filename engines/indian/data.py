import logging
import time
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from engines.indian.auth import get_api

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

REDIS_TTL_LTP       = 360
REDIS_TTL_DAY_RANGE = 360
REDIS_TTL_RATE_LIMIT= 120


def _redis():
    try:
        from redis_client import get_redis
        return get_redis()
    except Exception:
        return None


def _is_rate_limited() -> bool:
    try:
        r = _redis()
        if not r:
            return False
        return bool(r.get("indian:rate_limited"))
    except Exception:
        return False


def _set_rate_limited():
    try:
        r = _redis()
        if r:
            r.setex("indian:rate_limited", REDIS_TTL_RATE_LIMIT, "1")
            log.warning("AngelOne rate limit detected — pausing for %ss", REDIS_TTL_RATE_LIMIT)
    except Exception:
        pass


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
    token:     str,
    interval:  str,
    from_date: str,
    to_date:   str,
) -> pd.DataFrame | None:
    try:
        if _is_rate_limited():
            log.warning("fetch_candles skipped — rate limited")
            return None

        time.sleep(1)

        api = get_api()
        if not api:
            log.error("AngelOne API not available")
            return None

        angel_interval = INTERVAL_MAP.get(interval, "FIFTEEN_MINUTE")

        data = api.getCandleData({
            "exchange":    "NFO",
            "symboltoken": token,
            "interval":    angel_interval,
            "fromdate":    from_date,
            "todate":      to_date,
        })

        if not data.get("status") or not data.get("data"):
            msg = data.get("message", "")
            if "rate" in msg.lower() or "access" in msg.lower():
                _set_rate_limited()
            log.warning("No candle data: %s", msg)
            return None

        rows = []
        for c in data["data"]:
            ts = pd.Timestamp(c[0])
            rows.append({
                "timestamp": ts,
                "open":      float(c[1]),
                "high":      float(c[2]),
                "low":       float(c[3]),
                "close":     float(c[4]),
                "volume":    float(c[5]),
            })

        if not rows:
            return None

        df = pd.DataFrame(rows).set_index("timestamp")
        return df

    except Exception as e:
        log.error("fetch_candles error: %s", e)
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


def get_ltp(token: str) -> float | None:
    cached = get_ltp_from_redis(token)
    if cached:
        return cached

    try:
        if _is_rate_limited():
            log.warning("get_ltp skipped — rate limited")
            return None

        time.sleep(0.5)

        api = get_api()
        if not api:
            return None

        now       = datetime.now(IST)
        from_date = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        to_date   = now.strftime("%Y-%m-%d %H:%M")

        data = api.getCandleData({
            "exchange":    "NFO",
            "symboltoken": token,
            "interval":    "ONE_MINUTE",
            "fromdate":    from_date,
            "todate":      to_date,
        })

        if data.get("status") and data.get("data"):
            price = float(data["data"][-1][4])
            try:
                r = _redis()
                if r:
                    r.setex(f"indian:ltp:{token}", REDIS_TTL_LTP, str(price))
            except Exception:
                pass
            return price

        msg = data.get("message", "")
        if "rate" in msg.lower() or "access" in msg.lower():
            _set_rate_limited()
        return None

    except Exception as e:
        log.error("get_ltp error: %s", e)
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


def refresh_indian_data(token: str, name: str) -> dict:
    result = {
        "name":       name,
        "token":      token,
        "ltp":        None,
        "day_range":  0.0,
        "success":    False,
        "rate_limited": False,
    }

    if _is_rate_limited():
        result["rate_limited"] = True
        log.warning("refresh_indian_data skipped — rate limited")
        return result

    try:
        now       = datetime.now(IST)
        today     = now.strftime("%Y-%m-%d")
        from_date = f"{today} 09:15"
        to_date   = now.strftime("%Y-%m-%d %H:%M")

        df = fetch_candles(token, "15m", from_date, to_date)

        if df is not None and not df.empty:
            ltp       = float(df["close"].iloc[-1])
            day_high  = float(df["high"].max())
            day_low   = float(df["low"].min())
            day_range = round(day_high - day_low, 2)

            store_ltp(token, ltp)
            store_day_range(token, day_range)
            _set_last_refresh()

            result["ltp"]       = ltp
            result["day_range"] = day_range
            result["success"]   = True

            log.info(
                "Indian data refreshed: %s ltp=%.2f day_range=%.2f",
                name, ltp, day_range
            )
        else:
            log.warning("refresh_indian_data: no candle data for %s", name)

    except Exception as e:
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

        df = fetch_candles(token, "1d", from_date, to_date)
        if df is None or df.empty:
            return 0.0

        return float(df["volume"].tail(days).mean())

    except Exception as e:
        log.error("get_avg_volume error: %s", e)
        return 0.0