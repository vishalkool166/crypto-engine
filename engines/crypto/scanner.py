import asyncio
import logging
import time
from data.fetcher import fetch_and_store
from data.cache import cache
from config import cfg

log = logging.getLogger(__name__)

_scan_semaphore = asyncio.Semaphore(3)


async def scan_coin(coin: str, balance: float) -> dict | None:
    async with _scan_semaphore:
        try:
            df_4h = await fetch_and_store(coin, "4h", limit=300)
            df_1h = await fetch_and_store(coin, "1h", limit=300)

            if df_4h is None or len(df_4h) < 200:
                return None
            if df_1h is None or len(df_1h) < 50:
                return None

            from engines.crypto.strategy import analyze
            result = analyze(coin, df_4h, df_1h, balance)

            ticker = _get_ticker(coin)
            funding = _get_funding(coin)

            from trade.ws import get_mark_price
            price = get_mark_price(coin) or float(df_4h["close"].iloc[-1])

            cache_entry = {
                "coin":      coin,
                "grade":     result.grade if result.signal else "--",
                "direction": result.direction,
                "score":     result.score,
                "signal":    result.__dict__ if result.signal else {},
                "state":     "watching" if result.signal else "idle",
                "regime":    result.regime,
                "adx":       result.adx,
                "rsi":       result.rsi,
                "reason":    result.reason,
                "market": {
                    "price":      price,
                    "change24":   ticker.get("change24", 0),
                    "change_pos": ticker.get("change_pos", True),
                    "funding":    funding,
                },
                "cached_at": time.time(),
            }

            cache.set(f"signal_{coin}", cache_entry, ttl=1800)
            return cache_entry

        except Exception as e:
            log.error("scan_coin %s: %s", coin, e)
            return None


async def scan_all(coins: list, balance: float) -> list:
    log.info("Crypto scan started — %s coins", len(coins))
    start = time.time()

    results = await asyncio.gather(
        *[scan_coin(coin, balance) for coin in coins],
        return_exceptions=True,
    )

    valid = [r for r in results if r and not isinstance(r, Exception)]
    valid.sort(key=lambda x: x.get("score", 0), reverse=True)

    elapsed = round((time.time() - start) * 1000, 1)
    signals = [r for r in valid if r.get("grade") in ("A+", "A", "B")]
    log.info("Crypto scan complete — %s results %s signals %sms", len(valid), len(signals), elapsed)

    return valid


def _get_ticker(coin: str) -> dict:
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            return {"change24": 0.0, "change_pos": True}
        raw = r.get(f"ticker:{coin}USDT")
        if not raw:
            return {"change24": 0.0, "change_pos": True}
        data = json.loads(raw)
        change_pct = float(data.get("percentage", 0))
        return {
            "change24":   round(change_pct, 4),
            "change_pos": change_pct >= 0,
        }
    except Exception:
        return {"change24": 0.0, "change_pos": True}


def _get_funding(coin: str) -> float:
    try:
        from redis_client import get_redis
        r = get_redis()
        if not r:
            return 0.0
        raw = r.get(f"funding:{coin}USDT")
        if not raw:
            return 0.0
        return float(raw)
    except Exception:
        return 0.0