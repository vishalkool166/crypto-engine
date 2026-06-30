import logging
import ccxt.async_support as ccxt_async
from config import cfg

log = logging.getLogger(__name__)

_exchange = None


def get_exchange() -> ccxt_async.binance:
    global _exchange

    if _exchange is not None:
        return _exchange

    is_live = cfg.TRADING_MODE == "live"

    if is_live:
        _exchange = ccxt_async.binance({
            "apiKey": cfg.BINANCE_API_KEY,
            "secret": cfg.BINANCE_SECRET,
            "options": {
                "defaultType": "future",
            },
            "enableRateLimit": True,
        })
        log.info("Exchange: Binance LIVE futures")
    else:
        _exchange = ccxt_async.binance({
            "apiKey": cfg.BINANCE_DEMO_API_KEY,
            "secret": cfg.BINANCE_DEMO_SECRET,
            "options": {
                "defaultType":  "future",
                "hostname":     "demo.binance.com",
            },
            "enableRateLimit": True,
        })
        log.info("Exchange: Binance DEMO futures")

    return _exchange


async def close_exchange():
    global _exchange
    if _exchange:
        await _exchange.close()
        _exchange = None
        log.info("Exchange connection closed")


async def get_balance() -> dict:
    exchange = get_exchange()
    try:
        balance = await exchange.fetch_balance()
        usdt    = balance.get("USDT", {})
        return {
            "total":  float(usdt.get("total", 0)),
            "free":   float(usdt.get("free",  0)),
            "used":   float(usdt.get("used",  0)),
        }
    except Exception as e:
        log.error(f"fetch_balance error: {e}")
        return {"total": 0.0, "free": 0.0, "used": 0.0}


async def get_positions() -> list:
    exchange = get_exchange()
    try:
        positions = await exchange.fetch_positions()
        return [
            p for p in positions
            if float(p.get("contracts", 0)) > 0
        ]
    except Exception as e:
        log.error(f"fetch_positions error: {e}")
        return []


async def get_ticker_price(symbol: str) -> float:
    exchange = get_exchange()
    try:
        ticker = await exchange.fetch_ticker(symbol)
        return float(ticker.get("last", 0))
    except Exception as e:
        log.error(f"fetch_ticker error {symbol}: {e}")
        return 0.0