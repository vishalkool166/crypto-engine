import asyncio
import os
import logging
import pandas as pd
import ccxt.async_support as ccxt_async
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s — %(levelname)s — %(message)s"
)
log = logging.getLogger(__name__)

OUTPUT_DIR = "/app/optimizer/data"

COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP",
    "ADA", "DOGE", "AVAX", "LINK", "UNI",
    "OP", "ARB"
]

TIMEFRAMES = ["4h", "1h"]

CANDLES_PER_TF = {
    "4h": 4380,   # 2 years × 365 days × 6 candles/day
    "1h": 17520,  # 2 years × 365 days × 24 candles/day
}

SLEEP_BETWEEN_REQUESTS = 0.5


def _get_exchange():
    return ccxt_async.binance({
        "apiKey":  os.getenv("BINANCE_API_KEY", ""),
        "secret":  os.getenv("BINANCE_SECRET",  ""),
        "options": {"defaultType": "future"},
    })


async def _fetch_all_candles(
    exchange,
    coin:      str,
    timeframe: str,
    total:     int,
) -> pd.DataFrame:

    symbol     = f"{coin}/USDT"
    all_candles= []
    limit      = 1000
    now_ms     = int(datetime.now(timezone.utc).timestamp() * 1000)

    tf_ms = {
        "1h": 3_600_000,
        "4h": 14_400_000,
    }

    tf_duration = tf_ms[timeframe]
    since       = now_ms - (total * tf_duration)

    log.info("Downloading %s %s — %s candles from %s",
        coin, timeframe, total,
        datetime.fromtimestamp(since / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    )

    while True:
        try:
            raw = await exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since = since,
                limit = limit,
            )
        except Exception as e:
            log.error("Fetch error %s %s: %s", coin, timeframe, e)
            await asyncio.sleep(2)
            continue

        if not raw:
            break

        all_candles.extend(raw)
        last_ts = raw[-1][0]

        log.info(
            "%s %s — fetched %s candles — latest: %s — total so far: %s",
            coin, timeframe, len(raw),
            datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
            len(all_candles),
        )

        if len(raw) < limit:
            break

        since = last_ts + tf_duration
        await asyncio.sleep(SLEEP_BETWEEN_REQUESTS)

    if not all_candles:
        log.warning("No candles downloaded for %s %s", coin, timeframe)
        return None

    df = pd.DataFrame(
        all_candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["timestamp"])
    df = df.sort_values("timestamp")
    df = df.set_index("timestamp")

    log.info(
        "%s %s — total: %s candles | %s → %s",
        coin, timeframe, len(df),
        df.index[0].strftime("%Y-%m-%d"),
        df.index[-1].strftime("%Y-%m-%d"),
    )

    return df


async def download_coin(exchange, coin: str) -> dict:
    results = {}
    for tf in TIMEFRAMES:
        try:
            total = CANDLES_PER_TF[tf]
            df    = await _fetch_all_candles(exchange, coin, tf, total)

            if df is None or df.empty:
                log.warning("No data for %s %s — skipping", coin, tf)
                results[tf] = 0
                continue

            os.makedirs(OUTPUT_DIR, exist_ok=True)
            path = os.path.join(OUTPUT_DIR, f"{coin}_{tf}.csv")
            df.to_csv(path)

            log.info("Saved %s %s → %s (%s candles)", coin, tf, path, len(df))
            results[tf] = len(df)

        except Exception as e:
            log.error("download_coin %s %s: %s", coin, tf, e)
            results[tf] = 0

        await asyncio.sleep(SLEEP_BETWEEN_REQUESTS)

    return results


async def download_all() -> dict:
    exchange = _get_exchange()
    summary  = {}

    try:
        log.info("=" * 60)
        log.info("STARTING DOWNLOAD")
        log.info("Coins:      %s", COINS)
        log.info("Timeframes: %s", TIMEFRAMES)
        log.info("History:    2 years")
        log.info("Output:     %s", OUTPUT_DIR)
        log.info("=" * 60)

        for i, coin in enumerate(COINS, 1):
            log.info("--- Coin %s/%s: %s ---", i, len(COINS), coin)
            result       = await download_coin(exchange, coin)
            summary[coin]= result
            await asyncio.sleep(1)

        log.info("=" * 60)
        log.info("DOWNLOAD COMPLETE")
        log.info("=" * 60)

        total_candles = 0
        for coin, tfs in summary.items():
            for tf, count in tfs.items():
                status = "✅" if count > 0 else "❌"
                log.info("%s %s %s: %s candles", status, coin, tf, count)
                total_candles += count

        log.info("Total candles downloaded: %s", total_candles)

        missing = [
            f"{coin} {tf}"
            for coin, tfs in summary.items()
            for tf, count in tfs.items()
            if count == 0
        ]

        if missing:
            log.warning("Missing data: %s", missing)
        else:
            log.info("All coins downloaded successfully ✅")

        return summary

    finally:
        await exchange.close()


def check_existing() -> dict:
    if not os.path.exists(OUTPUT_DIR):
        return {}

    existing = {}
    for coin in COINS:
        existing[coin] = {}
        for tf in TIMEFRAMES:
            path = os.path.join(OUTPUT_DIR, f"{coin}_{tf}.csv")
            if os.path.exists(path):
                try:
                    df = pd.read_csv(path, index_col=0, parse_dates=True)
                    existing[coin][tf] = len(df)
                except Exception:
                    existing[coin][tf] = 0
            else:
                existing[coin][tf] = 0
    return existing


if __name__ == "__main__":
    existing = check_existing()
    if existing:
        log.info("Existing data found:")
        for coin, tfs in existing.items():
            for tf, count in tfs.items():
                if count > 0:
                    log.info("  %s %s: %s candles", coin, tf, count)

    asyncio.run(download_all())