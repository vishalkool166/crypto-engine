import asyncio
import logging
import time
import pandas as pd
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(levelname)s — %(message)s")
log = logging.getLogger(__name__)

TIMEFRAMES = ["4h", "1h"]

TARGET_CANDLES = {
    "4h": 5000,
    "1h": 5000,
}

SLEEP_BETWEEN = 0.5


def get_coins_from_db() -> list:
    try:
        from database import SessionLocal, CoinConfig
        with SessionLocal() as db:
            rows = db.query(CoinConfig).filter(CoinConfig.enabled == True).all()
            coins = [r.coin for r in rows]
            log.info(f"Loaded {len(coins)} coins from DB: {coins}")
            return coins
    except Exception as e:
        log.error(f"Failed to load coins from DB: {e}")
        return []


async def fetch_page(exchange, coin: str, tf: str, since: int, limit: int = 1000) -> list:
    try:
        raw = await exchange.fetch_ohlcv(
            f"{coin}/USDT",
            tf,
            since=since,
            limit=limit
        )
        return raw
    except Exception as e:
        log.error(f"Fetch error {coin} {tf}: {e}")
        return []


async def backfill_coin(exchange, coin: str, tf: str, target: int):
    from data.store import save_candles, get_candle_count
    from database import SessionLocal, Candle
    from sqlalchemy import and_

    current_count = get_candle_count(coin, tf)
    log.info(f"{coin} {tf}: currently {current_count} candles")

    if current_count >= target:
        log.info(f"{coin} {tf}: already has {current_count} candles — skipping")
        return

    try:
        with SessionLocal() as db:
            oldest = db.query(Candle).filter(
                and_(
                    Candle.coin      == coin,
                    Candle.timeframe == tf,
                    Candle.timestamp >= 1000000000000
                )
            ).order_by(Candle.timestamp.asc()).first()

            oldest_ts = oldest.timestamp if oldest else int(datetime.now(timezone.utc).timestamp() * 1000)
    except Exception as e:
        log.error(f"DB query error {coin} {tf}: {e}")
        return

    needed   = target - current_count
    pages    = (needed // 1000) + 2
    fetch_ts = oldest_ts

    log.info(f"{coin} {tf}: fetching {needed} more candles ({pages} pages)")

    total_saved = 0

    for page in range(pages):
        page_since = fetch_ts - (1000 * _tf_ms(tf))

        if page_since < 0:
            break

        raw = await fetch_page(exchange, coin, tf, since=page_since)

        if not raw:
            log.warning(f"{coin} {tf}: empty page at {page_since} — stopping")
            break

        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")

        save_candles(coin, tf, df)
        total_saved += len(df)

        fetch_ts = page_since
        log.info(f"{coin} {tf}: page {page+1}/{pages} — saved {len(df)} candles — oldest: {df.index[0]}")

        await asyncio.sleep(SLEEP_BETWEEN)

        new_count = get_candle_count(coin, tf)
        if new_count >= target:
            log.info(f"{coin} {tf}: reached target {target} candles")
            break

    log.info(f"{coin} {tf}: backfill complete — total saved: {total_saved}")


def _tf_ms(tf: str) -> int:
    mapping = {
        "1h":  3600000,
        "4h":  14400000,
        "1d":  86400000,
        "1w":  604800000,
    }
    return mapping.get(tf, 3600000)


async def run_backfill(coins: list = None):
    import ccxt.async_support as ccxt_async
    from dotenv import load_dotenv
    import os

    load_dotenv()

    exchange = ccxt_async.binance({
        "apiKey":  os.getenv("BINANCE_API_KEY"),
        "secret":  os.getenv("BINANCE_SECRET"),
        "options": {"defaultType": "future"}
    })

    try:
        if not coins:
            coins = get_coins_from_db()

        if not coins:
            log.error("No coins found — aborting")
            return

        log.info(f"Starting backfill — {len(coins)} coins × {len(TIMEFRAMES)} timeframes")

        for coin in coins:
            for tf in TIMEFRAMES:
                target = TARGET_CANDLES.get(tf, 3000)
                try:
                    await backfill_coin(exchange, coin, tf, target)
                except Exception as e:
                    log.error(f"Backfill failed {coin} {tf}: {e}")
                await asyncio.sleep(1)

        log.info("Backfill complete")

    finally:
        await exchange.close()


if __name__ == "__main__":
    asyncio.run(run_backfill())