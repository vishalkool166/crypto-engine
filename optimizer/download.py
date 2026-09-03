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

OUTPUT_DIR  = "/app/optimizer/data"
MAX_RETRIES = 3
RETRY_DELAY = 2

COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP",
    "ADA", "DOGE", "AVAX", "LINK", "UNI",
    "OP", "ARB"
]

TIMEFRAMES = ["4h", "1h"]

CANDLES_PER_TF = {
    "4h": 4380,
    "1h": 17520,
}

TF_MS = {
    "4h": 14_400_000,
    "1h":  3_600_000,
}

SLEEP_BETWEEN_REQUESTS = 0.5


def _get_exchange():
    return ccxt_async.binance({
        "apiKey":  os.getenv("BINANCE_API_KEY", ""),
        "secret":  os.getenv("BINANCE_SECRET",  ""),
        "options": {"defaultType": "future"},
    })


async def _fetch_with_retry(
    exchange,
    symbol:    str,
    timeframe: str,
    since:     int,
    limit:     int = 1000,
) -> list | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = await exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since = since,
                limit = limit,
            )
            return raw
        except Exception as e:
            wait = RETRY_DELAY ** attempt
            log.error(
                "    ❌ Attempt %s/%s failed for %s %s: %s — retrying in %ss",
                attempt, MAX_RETRIES, symbol, timeframe, e, wait,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(wait)
            else:
                log.error(
                    "    ❌ All %s attempts failed for %s %s — skipping",
                    MAX_RETRIES, symbol, timeframe,
                )
                return None


async def _fetch_all_candles(
    exchange,
    coin:      str,
    timeframe: str,
    total:     int,
) -> pd.DataFrame | None:

    symbol      = f"{coin}/USDT"
    all_candles = []
    limit       = 1000
    now_ms      = int(datetime.now(timezone.utc).timestamp() * 1000)
    tf_duration = TF_MS[timeframe]
    since       = now_ms - (total * tf_duration)

    log.info(
        "  📥 %s %s — downloading %s candles from %s",
        coin, timeframe, total,
        datetime.fromtimestamp(since / 1000, tz=timezone.utc).strftime("%Y-%m-%d"),
    )

    page        = 0
    empty_pages = 0

    while True:
        page += 1
        raw   = await _fetch_with_retry(exchange, symbol, timeframe, since, limit)

        if raw is None:
            log.error("  ❌ %s %s — fetch failed after retries — stopping", coin, timeframe)
            break

        if not raw:
            empty_pages += 1
            log.warning(
                "  ⚠️  %s %s — empty page %s at %s",
                coin, timeframe, page,
                datetime.fromtimestamp(since / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
            )
            if empty_pages >= 3:
                log.warning("  ⚠️  %s %s — 3 empty pages in a row — stopping", coin, timeframe)
                break
            since += tf_duration * limit
            continue

        empty_pages = 0
        all_candles.extend(raw)
        last_ts     = raw[-1][0]
        last_dt     = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc)
        pct_done    = round(len(all_candles) / total * 100, 1)

        log.info(
            "  📊 %s %s — page %s | fetched %s | total %s/%s (%.1f%%) | latest %s",
            coin, timeframe, page,
            len(raw),
            len(all_candles), total,
            pct_done,
            last_dt.strftime("%Y-%m-%d %H:%M"),
        )

        if len(raw) < limit:
            log.info("  ✅ %s %s — reached end of data", coin, timeframe)
            break

        if len(all_candles) >= total:
            log.info("  ✅ %s %s — reached target %s candles", coin, timeframe, total)
            break

        since = last_ts + tf_duration
        await asyncio.sleep(SLEEP_BETWEEN_REQUESTS)

    if not all_candles:
        log.warning("  ⚠️  %s %s — no candles downloaded", coin, timeframe)
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
        "  ✅ %s %s — final: %s candles | %s → %s",
        coin, timeframe, len(df),
        df.index[0].strftime("%Y-%m-%d"),
        df.index[-1].strftime("%Y-%m-%d"),
    )

    return df


async def download_coin(exchange, coin: str) -> dict:
    results = {}

    log.info("")
    log.info("  ┌─────────────────────────────────┐")
    log.info("  │  Downloading: %-6s             │", coin)
    log.info("  └─────────────────────────────────┘")

    for tf in TIMEFRAMES:
        tf_start = __import__("time").time()
        try:
            total = CANDLES_PER_TF[tf]
            df    = await _fetch_all_candles(exchange, coin, tf, total)

            if df is None or df.empty:
                log.warning("  ⚠️  %s %s — no data — skipping", coin, tf)
                results[tf] = 0
                continue

            os.makedirs(OUTPUT_DIR, exist_ok=True)
            path = os.path.join(OUTPUT_DIR, f"{coin}_{tf}.csv")
            df.to_csv(path)

            elapsed = round(__import__("time").time() - tf_start, 1)
            size_kb = round(os.path.getsize(path) / 1024, 1)

            log.info(
                "  💾 Saved %s %s → %s | %s candles | %s KB | %.1fs",
                coin, tf, path, len(df), size_kb, elapsed,
            )
            results[tf] = len(df)

        except Exception as e:
            log.error("  ❌ download_coin %s %s: %s", coin, tf, e)
            results[tf] = 0

        await asyncio.sleep(SLEEP_BETWEEN_REQUESTS)

    return results


async def download_all() -> dict:
    exchange = _get_exchange()
    summary  = {}

    try:
        log.info("")
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║              STARTING DATA DOWNLOAD                     ║")
        log.info("╠══════════════════════════════════════════════════════════╣")
        log.info("║  Coins      : %-3s                                       ", len(COINS))
        log.info("║  Timeframes : %s                                        ", TIMEFRAMES)
        log.info("║  History    : 2 years per coin                          ║")
        log.info("║  Output     : %-40s║", OUTPUT_DIR)
        log.info("║  Est. time  : 10-15 minutes                             ║")
        log.info("╚══════════════════════════════════════════════════════════╝")

        total_start = __import__("time").time()

        for i, coin in enumerate(COINS, 1):
            coin_start = __import__("time").time()
            log.info("")
            log.info("▶ Coin %s/%s: %s", i, len(COINS), coin)

            if i > 1:
                elapsed     = __import__("time").time() - total_start
                avg_per     = elapsed / (i - 1)
                remaining   = avg_per * (len(COINS) - i + 1)
                eta_mins    = int(remaining // 60)
                eta_secs    = int(remaining  % 60)
                log.info(
                    "  ⏱️  Elapsed: %.0fs | ETA: %sm %ss",
                    elapsed, eta_mins, eta_secs,
                )

            result        = await download_coin(exchange, coin)
            summary[coin] = result

            coin_elapsed = round(__import__("time").time() - coin_start, 1)
            total_coin   = sum(result.values())
            log.info(
                "  ✅ %s done in %.1fs — %s total candles",
                coin, coin_elapsed, total_coin,
            )

            await asyncio.sleep(1)

        total_elapsed = round(__import__("time").time() - total_start, 1)

        log.info("")
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║              DOWNLOAD COMPLETE                          ║")
        log.info("╠══════════════════════════════════════════════════════════╣")
        log.info("║  Total time : %.0fs (%.1f mins)                          ", total_elapsed, total_elapsed / 60)
        log.info("╚══════════════════════════════════════════════════════════╝")
        log.info("")

        total_candles = 0
        all_ok        = True

        for coin, tfs in summary.items():
            for tf, count in tfs.items():
                status = "✅" if count > 0 else "❌"
                if count == 0:
                    all_ok = False
                log.info("  %s %-6s %-4s : %s candles", status, coin, tf, count)
                total_candles += count

        log.info("")
        log.info("  Total candles downloaded: %s", f"{total_candles:,}")

        missing = [
            f"{coin} {tf}"
            for coin, tfs in summary.items()
            for tf, count in tfs.items()
            if count == 0
        ]

        if missing:
            log.warning("  ⚠️  Missing data: %s", missing)
        else:
            log.info("  ✅ All coins downloaded successfully")

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
                    existing[coin][tf] = {
                        "candles": len(df),
                        "from":    str(df.index[0].date()),
                        "to":      str(df.index[-1].date()),
                        "ok":      len(df) >= 500,
                    }
                except Exception as e:
                    existing[coin][tf] = {"candles": 0, "ok": False, "error": str(e)}
            else:
                existing[coin][tf] = {"candles": 0, "ok": False}
    return existing


if __name__ == "__main__":
    asyncio.run(download_all())