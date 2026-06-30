import hmac
import hashlib
import time
import logging
import httpx
from config import cfg

log = logging.getLogger(__name__)

_client: httpx.AsyncClient = None


def _get_base_url() -> str:
    if cfg.TRADING_MODE == "live":
        return "https://fapi.binance.com"
    return "https://demo.binance.com"


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
        total     = float(usdt.get("balance",            0))
        free      = float(usdt.get("availableBalance",   0))
        unrealized= float(usdt.get("crossUnPnl",         0))
        used      = round(total - free, 4)
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
        clean  = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        data   = await _get("/fapi/v1/ticker/price", {"symbol": clean})
        return float(data.get("price", 0))
    except Exception as e:
        log.error(f"get_ticker_price error {symbol}: {e}")
        return 0.0


async def get_exchange_info(symbol: str = None) -> dict:
    try:
        params = {}
        if symbol:
            clean          = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
            params["symbol"] = clean
        return await _get("/fapi/v1/exchangeInfo", params)
    except Exception as e:
        log.error(f"get_exchange_info error: {e}")
        return {}


async def get_symbol_precision(symbol: str) -> dict:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        info  = await get_exchange_info(clean)
        for s in info.get("symbols", []):
            if s["symbol"] == clean:
                qty_precision   = int(s.get("quantityPrecision",  0))
                price_precision = int(s.get("pricePrecision",     0))
                min_qty         = 0.0
                step_size       = 0.0
                for f in s.get("filters", []):
                    if f["filterType"] == "LOT_SIZE":
                        min_qty   = float(f.get("minQty",  0))
                        step_size = float(f.get("stepSize",0))
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
    symbol:     str,
    side:       str,
    order_type: str,
    quantity:   float,
    price:      float = None,
    stop_price: float = None,
    reduce_only: bool = False,
    working_type: str = "MARK_PRICE",
) -> dict:
    clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")

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
        params["stopPrice"]   = stop_price
        params["workingType"] = working_type

    if reduce_only:
        params["reduceOnly"] = "true"

    return await _post("/fapi/v1/order", params, signed=True)


async def cancel_order(symbol: str, order_id: str) -> dict:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
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
    return await _get("/fapi/v1/order", {
        "symbol":  clean,
        "orderId": order_id,
    }, signed=True)


async def cancel_all_orders(symbol: str) -> dict:
    try:
        clean = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
        return await _delete("/fapi/v1/allOpenOrders", {
            "symbol": clean,
        }, signed=True)
    except Exception as e:
        log.error(f"cancel_all_orders error {symbol}: {e}")
        return {}


async def ping() -> bool:
    try:
        await _get("/fapi/v1/ping")
        return True
    except Exception:
        return False