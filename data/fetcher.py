import ccxt.async_support as ccxt_async
import httpx
import pandas as pd
from datetime import datetime, timezone
from config import cfg
from data.store import save_candles, load_candles, get_last_timestamp
from data.cache import cache
import asyncio
import logging

log = logging.getLogger(__name__)

exchange = ccxt_async.binance({
    "apiKey": cfg.BINANCE_API_KEY,
    "secret": cfg.BINANCE_SECRET,
    "options": {"defaultType": "future"}
})

TF_MAP = {
    "1w":  "1w",
    "1d":  "1d",
    "4h":  "4h",
    "1h":  "1h",
    "15m": "15m"
}

TF_LIMITS = {
    "1w":  500,
    "1d":  1000,
    "4h":  2000,
    "1h":  1000,
    "15m": 200
}

_api_fail_count   = 0
_api_fail_alerted = False

_last_fg: dict = {"value": 50, "label": "Neutral", "stale": False}


async def _alert_api_failure(coin: str, error: str):
    global _api_fail_count, _api_fail_alerted
    _api_fail_count += 1
    if _api_fail_count >= 3 and not _api_fail_alerted:
        _api_fail_alerted = True
        try:
            from alerts.telegram import send
            await send(
                f"🚨 *Binance API Failures*\n\n"
                f"Repeated failures fetching data.\n"
                f"Last coin: `{coin}`\n"
                f"Error: `{error}`\n\n"
                f"Check API keys and connectivity."
            )
        except Exception:
            pass


def _reset_api_fail():
    global _api_fail_count, _api_fail_alerted
    _api_fail_count   = 0
    _api_fail_alerted = False


async def fetch_and_store(coin: str, tf: str, limit: int = None) -> pd.DataFrame:
    sym     = f"{coin}/USDT"
    limit   = limit or TF_LIMITS.get(tf, 1000)
    last_ts = get_last_timestamp(coin, tf)

    try:
        if last_ts is None:
            log.info(f"First fetch: {coin} {tf} — downloading {limit} candles")
            raw = await exchange.fetch_ohlcv(sym, TF_MAP[tf], limit=limit)
        else:
            log.debug(f"Incremental fetch: {coin} {tf} since {last_ts}")
            raw = await exchange.fetch_ohlcv(sym, TF_MAP[tf], since=last_ts, limit=100)
        _reset_api_fail()
    except Exception as e:
        await _alert_api_failure(coin, str(e))
        raise

    if raw:
        df_new = pd.DataFrame(
            raw,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df_new["timestamp"] = pd.to_datetime(df_new["timestamp"], unit="ms")
        df_new = df_new.set_index("timestamp")
        if cfg.REQUIRE_CANDLE_CLOSE:
            df_new = df_new.iloc[:-1]
        save_candles(coin, tf, df_new)

    df = load_candles(coin, tf, limit=limit)
    if df is None or df.empty:
        raise Exception(f"No candle data available: {coin} {tf}")

    if tf == "1w" and len(df) < 200:
        log.warning(f"Weekly candles for {coin}: {len(df)} — EMA200 needs 200+.")

    return df


async def get_ohlcv(coin: str, tf: str, limit: int = None) -> pd.DataFrame:
    return await fetch_and_store(coin, tf, limit=limit)


async def get_ticker(coin: str) -> dict:
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            key  = f"ticker:{coin}USDT"
            data = r.get(key)
            if data:
                import json
                parsed = json.loads(data)
                log.debug(f"Redis ticker hit: {key}")
                return {"last": parsed["last"], "percentage": parsed["percentage"]}
    except Exception as e:
        log.warning(f"Redis ticker read failed {coin}: {e}")
    return await exchange.fetch_ticker(f"{coin}/USDT")


async def get_funding_rate(coin: str) -> float:
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            key  = f"funding:{coin}USDT"
            data = r.get(key)
            if data:
                log.debug(f"Redis funding hit: {key}")
                return float(data)
    except Exception as e:
        log.warning(f"Redis funding read failed {coin}: {e}")
    try:
        data = await exchange.fetch_funding_rate(f"{coin}/USDT")
        return float(data.get("fundingRate", 0))
    except Exception as e:
        log.warning(f"Funding rate failed {coin}: {e}")
        return 0.0


async def get_open_interest(coin: str) -> float:
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            key  = f"oi:{coin}USDT"
            data = r.get(key)
            if data:
                log.debug(f"Redis OI hit: {key}")
                return float(data)
    except Exception as e:
        log.warning(f"Redis OI read failed {coin}: {e}")
    try:
        data = await exchange.fetch_open_interest(f"{coin}/USDT")
        return float(data.get("openInterestAmount", 0))
    except Exception as e:
        log.warning(f"OI failed {coin}: {e}")
        return 0.0


async def get_oi_change(coin: str) -> float:
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            key  = f"oi_change:{coin}USDT"
            data = r.get(key)
            if data:
                log.debug(f"Redis OI change hit: {key}")
                return float(data)
    except Exception as e:
        log.warning(f"Redis OI change read failed {coin}: {e}")
    try:
        hist = await exchange.fetch_open_interest_history(
            f"{coin}/USDT", "1d", limit=2
        )
        if len(hist) >= 2:
            cur  = float(hist[-1]["openInterestAmount"])
            prev = float(hist[-2]["openInterestAmount"])
            return ((cur - prev) / prev * 100) if prev > 0 else 0.0
        return 0.0
    except Exception as e:
        log.warning(f"OI change failed {coin}: {e}")
        return 0.0


async def get_ls_ratio(coin: str) -> dict:
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            key  = f"ls_ratio:{coin}USDT"
            data = r.get(key)
            if data:
                import json
                parsed = json.loads(data)
                log.debug(f"Redis LS ratio hit: {key}")
                return {"long": parsed["long"], "short": parsed["short"]}
    except Exception as e:
        log.warning(f"Redis LS ratio read failed {coin}: {e}")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                params={"symbol": f"{coin}USDT", "period": "1h", "limit": 1},
                timeout=5
            )
            d = r.json()
            return {
                "long":  float(d[0]["longAccount"]) * 100,
                "short": float(d[0]["shortAccount"]) * 100
            }
    except Exception as e:
        log.warning(f"LS ratio failed {coin}: {e}")
        return {"long": 50.0, "short": 50.0}


async def get_fear_greed() -> dict:
    global _last_fg
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.alternative.me/fng/?limit=1",
                timeout=5
            )
            d = r.json()
            _last_fg = {
                "value": int(d["data"][0]["value"]),
                "label": d["data"][0]["value_classification"],
                "stale": False
            }
            return _last_fg
    except Exception as e:
        log.warning(f"Fear greed failed: {e}")
        return {**_last_fg, "stale": True}


async def get_news_filter() -> dict:
    try:
        async with httpx.AsyncClient() as client:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            r = await client.get(
                f"https://finnhub.io/api/v1/calendar/economic"
                f"?from={today}&token={cfg.FINNHUB_KEY}",
                timeout=5
            )
            events = r.json().get("economicCalendar", [])

        high_impact = [e for e in events if e.get("impact") == "high"]
        if not high_impact:
            return {"clear": True, "blocked": False, "warning": False, "alerts": [], "finnhub_ok": True}

        now     = datetime.now(timezone.utc)
        alerts  = []
        blocked = False
        warning = False

        for e in high_impact:
            try:
                event_time = datetime.strptime(
                    f"{e['date']} {e.get('time','00:00')}",
                    "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)

                diff_min   = (event_time - now).total_seconds() / 60
                is_active  = -15 <= diff_min <= 15
                is_warning = 0 < diff_min <= 60

                if is_active:  blocked = True
                if is_warning: warning = True

                alerts.append({
                    "name":     e["event"],
                    "date":     e["date"],
                    "time":     e.get("time", "00:00"),
                    "impact":   "high",
                    "diff_min": round(diff_min),
                    "active":   is_active,
                    "warning":  is_warning
                })
            except Exception:
                continue

        return {
            "clear":      not blocked and not warning,
            "blocked":    blocked,
            "warning":    warning,
            "alerts":     alerts,
            "finnhub_ok": True
        }

    except Exception as e:
        log.warning(f"Finnhub failed: {e}")
        try:
            from alerts.telegram import send
            await send(
                f"⚠️ *Finnhub Unavailable*\n\n"
                f"News filter degraded.\n"
                f"Error: `{str(e)[:100]}`"
            )
        except Exception:
            pass
        return {"clear": True, "blocked": False, "warning": False, "alerts": [], "finnhub_ok": False}


async def get_15m_data(coin: str) -> pd.DataFrame:
    cache_key = f"15m_{coin}"
    cached    = cache.get_raw(cache_key)
    if cached is not None:
        return cached

    try:
        df = await fetch_and_store(coin, "15m", limit=200)
        cache.set(cache_key, df, ttl=300)
        return df
    except Exception as e:
        log.warning(f"15m fetch failed {coin}: {e}")
        return None


async def get_all_data(coin: str) -> dict:
    news_filter = cache.get_raw("news_filter")

    if news_filter:
        ticker, funding, oi, oi_chg, ls = await asyncio.gather(
            get_ticker(coin),
            get_funding_rate(coin),
            get_open_interest(coin),
            get_oi_change(coin),
            get_ls_ratio(coin)
        )
    else:
        ticker, funding, oi, oi_chg, ls, news_filter = await asyncio.gather(
            get_ticker(coin),
            get_funding_rate(coin),
            get_open_interest(coin),
            get_oi_change(coin),
            get_ls_ratio(coin),
            get_news_filter()
        )
        cache.set("news_filter", news_filter, ttl=300)

    klines = {}
    for tf in cfg.TIMEFRAMES:
        klines[tf] = await get_ohlcv(coin, tf)

    df_15m = await get_15m_data(coin)

    return {
        "price":       float(ticker["last"]),
        "change24":    float(ticker["percentage"] or 0),
        "funding":     funding,
        "oi":          oi,
        "oi_change":   oi_chg,
        "long_ratio":  ls["long"],
        "short_ratio": ls["short"],
        "news_filter": news_filter,
        "klines":      klines,
        "klines_15m":  df_15m
    }