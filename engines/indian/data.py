import logging
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
    orb_ready = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return orb_ready <= now <= market_close


def fetch_candles(
    token:     str,
    interval:  str,
    from_date: str,
    to_date:   str,
) -> pd.DataFrame | None:
    try:
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
            log.warning("No candle data: %s", data.get("message"))
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


def get_ltp(token: str) -> float | None:
    try:
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
            return float(data["data"][-1][4])
        return None

    except Exception as e:
        log.error("get_ltp error: %s", e)
        return None


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