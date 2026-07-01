import hmac
import hashlib
import time
import logging
import httpx
from config import cfg

log = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None
_listen_key: str = ""
_listen_key_created_at: float = 0.0

LISTEN_KEY_TTL = 1800.0


def _base_url() -> str:
    if cfg.TRADING_MODE == "live":
        return "https://fapi.binance.com"
    return cfg.BINANCE_DEMO_BASE_URL or "https://testnet.binancefuture.com"


def _ws_base_url() -> str:
    if cfg.TRADING_MODE == "live":
        return "wss://fstream.binancefuture.com"
    return "wss://stream.binancefuture.com"


def _api_key() -> str:
    if cfg.TRADING_MODE == "live":
        return cfg.BINANCE_API_KEY or ""
    return cfg.BINANCE_DEMO_API_KEY or ""


def _secret() -> str:
    if cfg.TRADING_MODE == "live":
        return cfg.BINANCE_SECRET or ""
    return cfg.BINANCE_DEMO_SECRET or ""


def _sign(params: dict) -> str:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return hmac.new(_secret().encode(), query.encode(), hashlib.sha256).hexdigest()


def _ts() -> int:
    return int(time.time() * 1000)


def _signed(params: dict) -> dict:
    p = dict(params)
    p["timestamp"]  = _ts()
    p["recvWindow"] = 5000
    p["signature"]  = _sign(p)
    return p


def _clean(symbol: str) -> str:
    s = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")
    return s if s.endswith("USDT") else s + "USDT"


async def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout = httpx.Timeout(10.0),
            headers = {"X-MBX-APIKEY": _api_key()}
        )
    return _client


async def close_exchange() -> None:
    global _client, _listen_key
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
    _listen_key = ""
    log.info("Exchange connection closed")


async def _get(path: str, params: dict | None = None, signed: bool = False) -> dict:
    client = await _http()
    p      = _signed(dict(params or {})) if signed else dict(params or {})
    try:
        r = await client.get(f"{_base_url()}{path}", params=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.error("GET %s %s %s", path, e.response.status_code, e.response.text)
        raise


async def _post(path: str, params: dict | None = None, signed: bool = False) -> dict:
    client = await _http()
    p      = _signed(dict(params or {})) if signed else dict(params or {})
    try:
        r = await client.post(f"{_base_url()}{path}", data=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.error("POST %s %s %s", path, e.response.status_code, e.response.text)
        raise


async def _put(path: str, params: dict | None = None, signed: bool = False) -> dict:
    client = await _http()
    p      = _signed(dict(params or {})) if signed else dict(params or {})
    try:
        r = await client.put(f"{_base_url()}{path}", data=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.error("PUT %s %s %s", path, e.response.status_code, e.response.text)
        raise


async def _delete(path: str, params: dict | None = None, signed: bool = False) -> dict:
    client = await _http()
    p      = _signed(dict(params or {})) if signed else dict(params or {})
    try:
        r = await client.delete(f"{_base_url()}{path}", params=p)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.error("DELETE %s %s %s", path, e.response.status_code, e.response.text)
        raise


async def get_balance() -> dict:
    try:
        data = await _get("/fapi/v2/balance", signed=True)
        usdt = next((a for a in data if a.get("asset") == "USDT"), None)
        if not usdt:
            return {"total": 0.0, "free": 0.0, "used": 0.0, "unrealized": 0.0}
        total = float(usdt.get("balance",          0))
        free  = float(usdt.get("availableBalance", 0))
        return {
            "total":      total,
            "free":       free,
            "used":       round(total - free, 4),
            "unrealized": float(usdt.get("crossUnPnl", 0)),
        }
    except Exception as e:
        log.error("get_balance error: %s", e)
        return {"total": 0.0, "free": 0.0, "used": 0.0, "unrealized": 0.0}


async def get_positions() -> list:
    try:
        data = await _get("/fapi/v2/positionRisk", signed=True)
        return [p for p in data if float(p.get("positionAmt", 0)) != 0]
    except Exception as e:
        log.error("get_positions error: %s", e)
        return []


async def get_ticker_price(symbol: str) -> float:
    try:
        data = await _get("/fapi/v1/ticker/price", {"symbol": _clean(symbol)})
        return float(data.get("price", 0))
    except Exception as e:
        log.error("get_ticker_price %s: %s", symbol, e)
        return 0.0


async def get_symbol_precision(symbol: str) -> dict:
    try:
        clean = _clean(symbol)
        info  = await _get("/fapi/v1/exchangeInfo", {"symbol": clean})
        for s in info.get("symbols", []):
            if s["symbol"] != clean:
                continue
            min_qty = step_size = 0.0
            for f in s.get("filters", []):
                if f["filterType"] == "LOT_SIZE":
                    min_qty   = float(f.get("minQty",   0))
                    step_size = float(f.get("stepSize", 0))
            return {
                "qty_precision":   int(s.get("quantityPrecision", 0)),
                "price_precision": int(s.get("pricePrecision",    0)),
                "min_qty":         min_qty,
                "step_size":       step_size,
            }
    except Exception as e:
        log.error("get_symbol_precision %s: %s", symbol, e)
    return {"qty_precision": 3, "price_precision": 2, "min_qty": 0.001, "step_size": 0.001}


async def set_leverage(symbol: str, leverage: int) -> dict:
    try:
        return await _post("/fapi/v1/leverage", {
            "symbol": _clean(symbol), "leverage": leverage
        }, signed=True)
    except Exception as e:
        log.error("set_leverage %s: %s", symbol, e)
        return {}


async def set_margin_mode(symbol: str, mode: str = "ISOLATED") -> dict:
    try:
        return await _post("/fapi/v1/marginType", {
            "symbol": _clean(symbol), "marginType": mode.upper()
        }, signed=True)
    except httpx.HTTPStatusError as e:
        if "No need to change margin type" in e.response.text:
            return {"msg": "already set"}
        log.error("set_margin_mode %s: %s", symbol, e.response.text)
        return {}
    except Exception as e:
        log.error("set_margin_mode %s: %s", symbol, e)
        return {}


async def place_order(
    symbol:       str,
    side:         str,
    order_type:   str,
    quantity:     float,
    price:        float | None = None,
    stop_price:   float | None = None,
    reduce_only:  bool         = False,
    working_type: str          = "MARK_PRICE",
) -> dict:
    params: dict = {
        "symbol":   _clean(symbol),
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
        return await _delete("/fapi/v1/order", {
            "symbol": _clean(symbol), "orderId": order_id
        }, signed=True)
    except httpx.HTTPStatusError as e:
        if "Unknown order" in e.response.text:
            return {"status": "already_gone"}
        raise


async def get_order(symbol: str, order_id: str) -> dict:
    return await _get("/fapi/v1/order", {
        "symbol": _clean(symbol), "orderId": order_id
    }, signed=True)


async def cancel_all_orders(symbol: str) -> dict:
    try:
        return await _delete("/fapi/v1/allOpenOrders", {
            "symbol": _clean(symbol)
        }, signed=True)
    except Exception as e:
        log.error("cancel_all_orders %s: %s", symbol, e)
        return {}

async def place_algo_order(
    symbol:         str,
    side:           str,
    order_type:     str,
    trigger_price:  float,
    price_precision:int  = 2,
    quantity:       float | None = None,
    close_position: bool = True,
    working_type:   str  = "MARK_PRICE",
) -> dict:
    params: dict = {
        "symbol":       _clean(symbol),
        "side":         side.upper(),
        "type":         order_type.upper(),
        "algoType":     "CONDITIONAL",
        "triggerPrice": round(trigger_price, price_precision),
        "workingType":  working_type,
        "priceProtect": "false",
    }
    if close_position:
        params["closePosition"] = "true"
    else:
        if quantity is not None:
            params["quantity"]   = quantity
        params["reduceOnly"] = "true"
    log.info("Algo order payload: %s", params)
    return await _post("/fapi/v1/algoOrder", params, signed=True)


async def cancel_algo_order(symbol: str, algo_id: int) -> dict:
    try:
        return await _delete("/fapi/v1/algoOrder", {
            "symbol":  _clean(symbol),
            "algoId":  algo_id,
        }, signed=True)
    except Exception as e:
        log.error("cancel_algo_order %s: %s", symbol, e)
        return {}


async def cancel_all_algo_orders(symbol: str) -> dict:
    try:
        return await _delete("/fapi/v1/algoOrder/all", {
            "symbol": _clean(symbol),
        }, signed=True)
    except Exception as e:
        log.error("cancel_all_algo_orders %s: %s", symbol, e)
        return {}


async def get_open_orders(symbol: str) -> list:
    try:
        return await _get("/fapi/v1/openOrders", {
            "symbol": _clean(symbol)
        }, signed=True) or []
    except Exception as e:
        log.error("get_open_orders %s: %s", symbol, e)
        return []


async def get_user_trades(symbol: str, limit: int = 10) -> list:
    try:
        return await _get("/fapi/v1/userTrades", {
            "symbol": _clean(symbol), "limit": limit
        }, signed=True) or []
    except Exception as e:
        log.error("get_user_trades %s: %s", symbol, e)
        return []


async def get_order_trades(symbol: str, order_id: str) -> list:
    try:
        return await _get("/fapi/v1/userTrades", {
            "symbol": _clean(symbol), "orderId": order_id
        }, signed=True) or []
    except Exception as e:
        log.error("get_order_trades %s order:%s: %s", symbol, order_id, e)
        return []


async def get_commission_from_order(symbol: str, order_id: str) -> dict:
    trades = await get_order_trades(symbol, order_id)
    if not trades:
        return {"commission": 0.0, "commission_asset": "USDT", "role": "taker", "realized_pnl": 0.0}
    return {
        "commission":       round(sum(float(t.get("commission",   0)) for t in trades), 8),
        "commission_asset": trades[0].get("commissionAsset", "USDT"),
        "role":             "maker" if any(t.get("maker") for t in trades) else "taker",
        "realized_pnl":     round(sum(float(t.get("realizedPnl", 0)) for t in trades), 8),
    }


async def get_funding_fees(symbol: str, start_time: int | None = None) -> float:
    try:
        params: dict = {
            "symbol":     _clean(symbol),
            "incomeType": "FUNDING_FEE",
            "limit":      100,
        }
        if start_time:
            params["startTime"] = start_time
        data = await _get("/fapi/v1/income", params, signed=True)
        return round(sum(float(i.get("income", 0)) for i in data), 8) if isinstance(data, list) else 0.0
    except Exception as e:
        log.error("get_funding_fees %s: %s", symbol, e)
        return 0.0


async def get_listen_key() -> str:
    global _listen_key, _listen_key_created_at
    try:
        now = time.time()
        if _listen_key and (now - _listen_key_created_at) < LISTEN_KEY_TTL:
            return _listen_key
        data                   = await _post("/fapi/v1/listenKey")
        _listen_key            = data.get("listenKey", "")
        _listen_key_created_at = now
        log.info("Listen key obtained: %s...", _listen_key[:16])
        return _listen_key
    except Exception as e:
        log.error("get_listen_key error: %s", e)
        return ""


async def refresh_listen_key() -> bool:
    global _listen_key, _listen_key_created_at
    try:
        if not _listen_key:
            await get_listen_key()
            return True
        await _put("/fapi/v1/listenKey", {"listenKey": _listen_key})
        _listen_key_created_at = time.time()
        return True
    except Exception as e:
        log.error("refresh_listen_key error: %s", e)
        _listen_key = ""
        return False


async def invalidate_listen_key() -> None:
    global _listen_key
    try:
        if _listen_key:
            await _delete("/fapi/v1/listenKey", {"listenKey": _listen_key})
            _listen_key = ""
            log.info("Listen key invalidated")
    except Exception as e:
        log.error("invalidate_listen_key error: %s", e)


async def ping() -> bool:
    try:
        await _get("/fapi/v1/ping")
        return True
    except Exception:
        return False


def get_ws_base_url() -> str:
    return _ws_base_url()