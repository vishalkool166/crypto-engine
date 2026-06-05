import ccxt
import httpx
import pandas as pd
from datetime import datetime, timezone
from config import cfg
from data.store import (
    save_candles, load_candles,
    get_last_timestamp, has_enough_data
)
from data.cache import cache
import logging

log = logging.getLogger(__name__)

exchange = ccxt.binance({
    "apiKey": cfg.BINANCE_API_KEY,
    "secret": cfg.BINANCE_SECRET,
    "options": {"defaultType": "future"}
})

# ── ADD 15m TO TIMEFRAME MAP ──
TF_MAP = {
    "1w":  "1w",
    "1d":  "1d",
    "4h":  "4h",
    "1h":  "1h",
    "15m": "15m"   # ← NEW
}


# ═══════════════════════════════════════════════════════
# FETCH AND STORE
# ═══════════════════════════════════════════════════════
def fetch_and_store(
    coin:  str,
    tf:    str,
    limit: int = 1000
) -> pd.DataFrame:
    sym     = f"{coin}/USDT"
    last_ts = get_last_timestamp(coin, tf)

    if last_ts is None:
        log.info(
            f"First fetch: {coin} {tf} "
            f"— downloading {limit} candles"
        )
        raw = exchange.fetch_ohlcv(
            sym, TF_MAP[tf], limit=limit
        )
    else:
        log.debug(
            f"Incremental fetch: {coin} {tf} "
            f"since {last_ts}"
        )
        raw = exchange.fetch_ohlcv(
            sym, TF_MAP[tf],
            since=last_ts,
            limit=100
        )

    if raw:
        df_new = pd.DataFrame(
            raw,
            columns=[
                "timestamp", "open", "high",
                "low", "close", "volume"
            ]
        )
        df_new["timestamp"] = pd.to_datetime(
            df_new["timestamp"], unit="ms"
        )
        df_new = df_new.set_index("timestamp")

        if cfg.REQUIRE_CANDLE_CLOSE:
            df_new = df_new.iloc[:-1]

        save_candles(coin, tf, df_new)

    df = load_candles(coin, tf, limit=limit)

    if df is None or df.empty:
        raise Exception(
            f"No candle data available: {coin} {tf}"
        )

    return df


# ═══════════════════════════════════════════════════════
# GET OHLCV
# ═══════════════════════════════════════════════════════
def get_ohlcv(
    coin:  str,
    tf:    str,
    limit: int = 200
) -> pd.DataFrame:
    return fetch_and_store(coin, tf, limit=limit)


# ═══════════════════════════════════════════════════════
# TICKER
# ═══════════════════════════════════════════════════════
def get_ticker(coin: str) -> dict:
    return exchange.fetch_ticker(f"{coin}/USDT")


# ═══════════════════════════════════════════════════════
# FUNDING RATE
# ═══════════════════════════════════════════════════════
def get_funding_rate(coin: str) -> float:
    try:
        data = exchange.fetch_funding_rate(
            f"{coin}/USDT"
        )
        return float(data.get("fundingRate", 0))
    except Exception as e:
        log.warning(
            f"Funding rate failed {coin}: {e}"
        )
        return 0.0


# ═══════════════════════════════════════════════════════
# OPEN INTEREST
# ═══════════════════════════════════════════════════════
def get_open_interest(coin: str) -> float:
    try:
        data = exchange.fetch_open_interest(
            f"{coin}/USDT"
        )
        return float(
            data.get("openInterestAmount", 0)
        )
    except Exception as e:
        log.warning(f"OI failed {coin}: {e}")
        return 0.0


# ═══════════════════════════════════════════════════════
# OI CHANGE
# ═══════════════════════════════════════════════════════
def get_oi_change(coin: str) -> float:
    try:
        hist = exchange.fetch_open_interest_history(
            f"{coin}/USDT", "1d", limit=2
        )
        if len(hist) >= 2:
            cur  = float(
                hist[-1]["openInterestAmount"]
            )
            prev = float(
                hist[-2]["openInterestAmount"]
            )
            return (
                (cur - prev) / prev * 100
            ) if prev > 0 else 0.0
        return 0.0
    except Exception as e:
        log.warning(f"OI change failed {coin}: {e}")
        return 0.0


# ═══════════════════════════════════════════════════════
# LONG SHORT RATIO
# ═══════════════════════════════════════════════════════
def get_ls_ratio(coin: str) -> dict:
    try:
        import requests
        url = (
            "https://fapi.binance.com/futures/data/"
            f"globalLongShortAccountRatio"
            f"?symbol={coin}USDT&period=1h&limit=1"
        )
        r = requests.get(url, timeout=5)
        d = r.json()
        return {
            "long":  float(
                d[0]["longAccount"]
            ) * 100,
            "short": float(
                d[0]["shortAccount"]
            ) * 100
        }
    except Exception as e:
        log.warning(f"LS ratio failed {coin}: {e}")
        return {"long": 50.0, "short": 50.0}


# ═══════════════════════════════════════════════════════
# FEAR AND GREED
# ═══════════════════════════════════════════════════════
async def get_fear_greed() -> dict:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.alternative.me"
                "/fng/?limit=1",
                timeout=5
            )
            d = r.json()
            return {
                "value": int(
                    d["data"][0]["value"]
                ),
                "label": d["data"][0][
                    "value_classification"
                ]
            }
    except Exception as e:
        log.warning(f"Fear greed failed: {e}")
        return {"value": 50, "label": "Neutral"}


# ═══════════════════════════════════════════════════════
# FINNHUB NEWS FILTER
# ═══════════════════════════════════════════════════════
async def get_news_filter() -> dict:
    try:
        async with httpx.AsyncClient() as client:
            today = datetime.now(
                timezone.utc
            ).strftime("%Y-%m-%d")
            r = await client.get(
                f"https://finnhub.io/api/v1/"
                f"calendar/economic"
                f"?from={today}"
                f"&token={cfg.FINNHUB_KEY}",
                timeout=5
            )
            events = r.json().get(
                "economicCalendar", []
            )

        high_impact = [
            e for e in events
            if e.get("impact") == "high"
        ]

        if not high_impact:
            return {
                "clear":   True,
                "blocked": False,
                "warning": False,
                "alerts":  []
            }

        now     = datetime.now(timezone.utc)
        alerts  = []
        blocked = False
        warning = False

        for e in high_impact:
            try:
                event_time = datetime.strptime(
                    f"{e['date']} "
                    f"{e.get('time','00:00')}",
                    "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)

                diff_min = (
                    event_time - now
                ).total_seconds() / 60

                is_active  = -15 <= diff_min <= 15
                is_warning = 0 < diff_min <= 60

                if is_active:  blocked = True
                if is_warning: warning = True

                alerts.append({
                    "name":     e["event"],
                    "date":     e["date"],
                    "time":     e.get(
                        "time", "00:00"
                    ),
                    "impact":   "high",
                    "diff_min": round(diff_min),
                    "active":   is_active,
                    "warning":  is_warning
                })

            except Exception:
                continue

        return {
            "clear":   not blocked and not warning,
            "blocked": blocked,
            "warning": warning,
            "alerts":  alerts
        }

    except Exception as e:
        log.warning(f"Finnhub failed: {e}")
        return {
            "clear":   True,
            "blocked": False,
            "warning": False,
            "alerts":  []
        }


# ═══════════════════════════════════════════════════════
# GET 15M DATA — separate function
# cached aggressively — changes every 15 min
# ═══════════════════════════════════════════════════════
def get_15m_data(coin: str) -> pd.DataFrame:
    """
    Fetches last 200 x 15m candles.
    Used for entry refinement only.
    Cached for 5 minutes.
    """
    cache_key = f"15m_{coin}"
    cached    = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        df = fetch_and_store(
            coin  = coin,
            tf    = "15m",
            limit = 200
        )
        cache.set(cache_key, df, ttl=300)
        return df
    except Exception as e:
        log.warning(
            f"15m fetch failed {coin}: {e}"
        )
        return None


# ═══════════════════════════════════════════════════════
# GET ALL DATA
# ═══════════════════════════════════════════════════════
async def get_all_data(coin: str) -> dict:
    ticker  = get_ticker(coin)
    funding = get_funding_rate(coin)
    oi      = get_open_interest(coin)
    oi_chg  = get_oi_change(coin)
    ls      = get_ls_ratio(coin)

    # ── CACHE NEWS FILTER ──
    news_filter = cache.get("news_filter")
    if not news_filter:
        news_filter = await get_news_filter()
        cache.set(
            "news_filter", news_filter, ttl=300
        )
        log.debug("News filter fetched and cached")
    else:
        log.debug("News filter from cache")

    # ── FETCH 15M ──
    df_15m = get_15m_data(coin)

    return {
        "price":       float(ticker["last"]),
        "change24":    float(
            ticker["percentage"] or 0
        ),
        "high24":      float(ticker["high"] or 0),
        "low24":       float(ticker["low"] or 0),
        "vol24":       float(
            ticker["quoteVolume"] or 0
        ),
        "funding":     funding,
        "oi":          oi,
        "oi_change":   oi_chg,
        "long_ratio":  ls["long"],
        "short_ratio": ls["short"],
        "news_filter": news_filter,
        "klines": {
            tf: get_ohlcv(coin, tf)
            for tf in cfg.TIMEFRAMES
        },
        "klines_15m":  df_15m
    }