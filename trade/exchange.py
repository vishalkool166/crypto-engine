import hmac
import hashlib
import time
import logging
import httpx
from config import cfg

log = logging.getLogger(__name__)

_client: httpx.AsyncClient = None
_listen_key: str = None
_listen_key_created_at: float = 0.0
_LISTEN_KEY_TTL = 1800.0


def _get_base_url() -> str:
    if cfg.TRADING_MODE == "live":
        return "https://fapi.binance.com"
    return cfg.BINANCE_DEMO_BASE_URL or "https://testnet.binancefuture.com"


def _get_ws_base_url() -> str:
    if cfg.TRADING_MODE == "live":
        return "wss://fstream.binancefuture.com"
    return "wss://stream.binancefuture.com"


def _get_api_key() -> str:
    if cfg.TRADING_MODE == "live":
        return cfg.BINANCE_API_KEY or ""
    return cfg.BINANCE_DEMO_API_KEY or ""


def _get_secret() -> str:
    if cfg.TRADING_MODE == "live":
        return cfg.BINANCE_SECRET or ""
    return cfg.BINANCE_DEMO_SECRET or ""


def _sign(params: dict) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return hmac.new(
        _get_secret().encode(),
        query.encode(),
        hashlib.sha256
    ).hexdigest()


def _timestamp() -> int:
    return int(time.time() * 1000)


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout = httpx.Timeout(10.0),
            headers = {"X-MBX-APIKEY": _get_api_key()}
        )
    return _client


async def close_exchange():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
    log.info("Exchange connection closed")


async def _get(path: str, params: dict = None, signed: bool = False) -> dict:
    client   = await _get_client()
    base_url = _get_base_url()
    p        = dict(params or {})

    if signed:
        p["timestamp"]  = _timestamp()
        p["recvWindow"] = 5000
        p["signature"]  = _sign(p)

    try:
        r = await client.get(f"{base_url}{path}", params=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.error(f"GET {path} error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        log.error(f"GET {path} error: {e}")
        raise


async def _post(path: str, params: dict = None, signed: bool = False) -> dict:
    client   = await _get_client()
    base_url = _get_base_url()
    p        = dict(params or {})

    if signed:
        p["timestamp"]  = _timestamp()
        p["recvWindow"] = 5000
        p["signature"]  = _sign(p)

    try:
        r = await client.post(f"{base_url}{path}", data=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.error(f"POST {path} error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        log.error(f"POST {path} error: {e}")
        raise


async def _put(path: str, params: dict = None, signed: bool = False) -> dict:
    client   = await _get_client()
    base_url = _get_base_url()
    p        = dict(params or {})

    if signed:
        p["timestamp"]  = _timestamp()
        p["recvWindow"] = 5000
        p["signature"]  = _sign(p)

    try:
        r = await client.put(f"{base_url}{path}", data=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.error(f"PUT {path} error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        log.error(f"PUT {path} error: {e}")
        raise


async def _delete(path: str, params: dict = None, signed: bool = False) -> dict:
    client   = await _get_client()
    base_url = _get_base_url()
    p        = dict(params or {})

    if signed:
        p["timestamp"]  = _timestamp()
        p["recvWindow"] = 5000
        p["signature"]  = _sign(p)

    try:
        r = await client.delete(f"{base_url}{path}", params=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.error(f"DELETE {path} error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        log.error(f"DELETE {path} error: {e}")
        raise


async def get_balance() -> dict:
    try:
        data = await _get("/fapi/v2/balance", signed=True)
        usdt = next(
            (a for a in data if a.get("asset") == "USDT"),
            None
        )
        if not usdt:
            return {"total": 0.0, "free": 0.0, "used": 0.0}
        total      = float(usdt.get("balance",          0))
        free       = float(usdt.get("availableBalance", 0))
        unrealized = float(usdt.get("crossUnPnl",       0))
        used       = round(total - free, 4)
        return {
            "total":      total,
            "free":       free,
            "used":       used,
            "unrealized": unrealized,
        }
    except Exception as e:
        log.error(f"get_balance error: {e}")
        return {"total": 0.0, "free": 0.0, "used": 0.0}


async def get_positions() -> list:
    try:
        data = await _get("/fapi/v2/positionRisk", signed=True)
        return [
            p for p in data
            if float(p.get("positionAmt", 0)) != 0
        ]
    except Exception as e:
        log.error(f"get_positions error: {e}")
        return []


async def get_ticker_price(symbol: str) -> float:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        data  = await _get("/fapi/v1/ticker/price", {"symbol": clean})
        return float(data.get("price", 0))
    except Exception as e:
        log.error(f"get_ticker_price error {symbol}: {e}")
        return 0.0


async def get_exchange_info(symbol: str = None) -> dict:
    try:
        params = {}
        if symbol:
            clean            = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
            params["symbol"] = clean
        return await _get("/fapi/v1/exchangeInfo", params)
    except Exception as e:
        log.error(f"get_exchange_info error: {e}")
        return {}


async def get_symbol_precision(symbol: str) -> dict:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        info  = await get_exchange_info(clean)
        for s in info.get("symbols", []):
            if s["symbol"] == clean:
                qty_precision   = int(s.get("quantityPrecision",  0))
                price_precision = int(s.get("pricePrecision",     0))
                min_qty         = 0.0
                step_size       = 0.0
                for f in s.get("filters", []):
                    if f["filterType"] == "LOT_SIZE":
                        min_qty   = float(f.get("minQty",   0))
                        step_size = float(f.get("stepSize", 0))
                return {
                    "qty_precision":   qty_precision,
                    "price_precision": price_precision,
                    "min_qty":         min_qty,
                    "step_size":       step_size,
                }
        return {"qty_precision": 3, "price_precision": 2, "min_qty": 0.001, "step_size": 0.001}
    except Exception as e:
        log.error(f"get_symbol_precision error {symbol}: {e}")
        return {"qty_precision": 3, "price_precision": 2, "min_qty": 0.001, "step_size": 0.001}


async def set_leverage(symbol: str, leverage: int) -> dict:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        return await _post("/fapi/v1/leverage", {
            "symbol":   clean,
            "leverage": leverage,
        }, signed=True)
    except Exception as e:
        log.error(f"set_leverage error {symbol}: {e}")
        return {}


async def set_margin_mode(symbol: str, mode: str = "ISOLATED") -> dict:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        return await _post("/fapi/v1/marginType", {
            "symbol":     clean,
            "marginType": mode.upper(),
        }, signed=True)
    except httpx.HTTPStatusError as e:
        if "No need to change margin type" in e.response.text:
            return {"msg": "already set"}
        log.error(f"set_margin_mode error {symbol}: {e.response.text}")
        return {}
    except Exception as e:
        log.error(f"set_margin_mode error {symbol}: {e}")
        return {}


async def place_order(
    symbol:       str,
    side:         str,
    order_type:   str,
    quantity:     float,
    price:        float = None,
    stop_price:   float = None,
    reduce_only:  bool  = False,
    working_type: str   = "MARK_PRICE",
) -> dict:
    clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
    if not clean.endswith("USDT"):
        clean = clean + "USDT"

    params = {
        "symbol":   clean,
        "side":     side.upper(),
        "type":     order_type.upper(),
        "quantity": quantity,
    }

    if price:
        params["price"]       = price
        params["timeInForce"] = "GTC"

    if stop_price:
        params["stopPrice"]    = stop_price
        params["workingType"]  = working_type
        params["priceProtect"] = "FALSE"

    if reduce_only:
        params["reduceOnly"] = "true"

    return await _post("/fapi/v1/order", params, signed=True)


async def cancel_order(symbol: str, order_id: str) -> dict:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        return await _delete("/fapi/v1/order", {
            "symbol":  clean,
            "orderId": order_id,
        }, signed=True)
    except httpx.HTTPStatusError as e:
        if "Unknown order" in e.response.text:
            log.debug(f"Order {order_id} already gone")
            return {"status": "already_gone"}
        raise


async def get_order(symbol: str, order_id: str) -> dict:
    clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
    if not clean.endswith("USDT"):
        clean = clean + "USDT"
    return await _get("/fapi/v1/order", {
        "symbol":  clean,
        "orderId": order_id,
    }, signed=True)


async def cancel_all_orders(symbol: str) -> dict:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        return await _delete("/fapi/v1/allOpenOrders", {
            "symbol": clean,
        }, signed=True)
    except Exception as e:
        log.error(f"cancel_all_orders error {symbol}: {e}")
        return {}


async def get_user_trades(symbol: str, limit: int = 10) -> list:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        params = {
            "symbol":    clean,
            "limit":     limit,
            "timestamp": _timestamp(),
            "recvWindow": 5000,
        }
        params["signature"] = _sign(params)
        data = await _get("/fapi/v1/userTrades", params)
        return data if isinstance(data, list) else []
    except Exception as e:
        log.error(f"get_user_trades error {symbol}: {e}")
        return []


async def get_order_trades(symbol: str, order_id: str) -> list:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        params = {
            "symbol":    clean,
            "orderId":   order_id,
            "timestamp": _timestamp(),
            "recvWindow": 5000,
        }
        params["signature"] = _sign(params)
        data = await _get("/fapi/v1/userTrades", params)
        return data if isinstance(data, list) else []
    except Exception as e:
        log.error(f"get_order_trades error {symbol} order:{order_id}: {e}")
        return []


async def get_funding_fees(symbol: str, start_time: int = None) -> float:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        if not clean.endswith("USDT"):
            clean = clean + "USDT"

        params = {
            "symbol":     clean,
            "incomeType": "FUNDING_FEE",
            "limit":      100,
            "timestamp":  _timestamp(),
            "recvWindow": 5000,
        }

        if start_time:
            params["startTime"] = start_time

        params["signature"] = _sign(params)
        data = await _get("/fapi/v1/income", params)

        if not isinstance(data, list):
            return 0.0

        total = sum(float(item.get("income", 0)) for item in data)
        return round(total, 8)

    except Exception as e:
        log.error(f"get_funding_fees error {symbol}: {e}")
        return 0.0


async def get_commission_from_order(symbol: str, order_id: str) -> dict:
    try:
        trades = await get_order_trades(symbol, order_id)
        if not trades:
            return {
                "commission":      0.0,
                "commission_asset": "USDT",
                "role":            "taker",
                "realized_pnl":    0.0,
            }

        total_commission = sum(float(t.get("commission", 0)) for t in trades)
        realized_pnl     = sum(float(t.get("realizedPnl", 0)) for t in trades)
        is_maker         = any(t.get("maker", False) for t in trades)
        commission_asset = trades[0].get("commissionAsset", "USDT") if trades else "USDT"

        return {
            "commission":       round(total_commission, 8),
            "commission_asset": commission_asset,
            "role":             "maker" if is_maker else "taker",
            "realized_pnl":     round(realized_pnl, 8),
        }

    except Exception as e:
        log.error(f"get_commission_from_order error {symbol} order:{order_id}: {e}")
        return {
            "commission":       0.0,
            "commission_asset": "USDT",
            "role":             "taker",
            "realized_pnl":     0.0,
        }


async def get_listen_key() -> str:
    global _listen_key, _listen_key_created_at
    try:
        now = time.time()
        if _listen_key and (now - _listen_key_created_at) < _LISTEN_KEY_TTL:
            return _listen_key

        data = await _post("/fapi/v1/listenKey", signed=False)
        _listen_key            = data.get("listenKey", "")
        _listen_key_created_at = now
        log.info(f"Listen key obtained: {_listen_key[:16]}...")
        return _listen_key
    except Exception as e:
        log.error(f"get_listen_key error: {e}")
        return ""


async def refresh_listen_key() -> bool:
    global _listen_key, _listen_key_created_at
    try:
        if not _listen_key:
            await get_listen_key()
            return True
        await _put("/fapi/v1/listenKey", {"listenKey": _listen_key})
        _listen_key_created_at = time.time()
        log.debug("Listen key refreshed")
        return True
    except Exception as e:
        log.error(f"refresh_listen_key error: {e}")
        _listen_key = None
        return False


async def invalidate_listen_key():
    global _listen_key
    try:
        if _listen_key:
            await _delete("/fapi/v1/listenKey", {"listenKey": _listen_key})
            _listen_key = None
            log.info("Listen key invalidated")
    except Exception as e:
        log.error(f"invalidate_listen_key error: {e}")


async def ping() -> bool:
    try:
        await _get("/fapi/v1/ping")
        return True
    except Exception:
        return False


def get_ws_base_url() -> str:
    return _get_ws_base_url()