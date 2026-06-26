import asyncio
import json
import logging
import httpx
import websockets
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from config import cfg
from auth import is_authenticated, verify_totp

log    = logging.getLogger(__name__)
router = APIRouter()

_ft_token:        str                = None
_http_client:     httpx.AsyncClient  = None
_ft_ws_task:      asyncio.Task       = None
_ft_ws_connected: bool               = False

_trade_event_callbacks = []


def on_ft_event(callback):
    _trade_event_callbacks.append(callback)


def _auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=10)
    return _http_client


async def _get_ft_token() -> str:
    global _ft_token, _http_client
    if _ft_token:
        try:
            client = await _get_http_client()
            r = await client.get(
                f"{cfg.FREQTRADE_URL}/api/v1/ping",
                headers={"Authorization": f"Bearer {_ft_token}"},
                timeout=5
            )
            if r.status_code == 200:
                return _ft_token
        except Exception:
            _http_client = None

    try:
        client = await _get_http_client()
        r = await client.post(
            f"{cfg.FREQTRADE_URL}/api/v1/token/login",
            auth=(cfg.FREQTRADE_USERNAME, cfg.FREQTRADE_PASSWORD),
            timeout=5
        )
        if r.status_code == 200:
            _ft_token = r.json().get("access_token")
            log.info("Freqtrade token refreshed")
            return _ft_token
        else:
            log.error(f"Freqtrade login failed: {r.text}")
            return None
    except Exception as e:
        log.error(f"Freqtrade token error: {e}")
        _http_client = None
        return None


async def _ft_get(path: str) -> dict:
    global _ft_token
    token = await _get_ft_token()
    if not token:
        raise HTTPException(503, "Freqtrade unavailable")
    try:
        client = await _get_http_client()
        r = await client.get(
            f"{cfg.FREQTRADE_URL}/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 401:
            _ft_token = None
            raise HTTPException(503, "Freqtrade auth failed")
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Freqtrade GET {path} error: {e}")
        raise HTTPException(503, f"Freqtrade unavailable: {e}")


async def _ft_get_safe(path: str) -> dict | None:
    try:
        token = await _get_ft_token()
        if not token:
            return None
        client = await _get_http_client()
        r = await client.get(
            f"{cfg.FREQTRADE_URL}/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 401:
            global _ft_token
            _ft_token = None
            return None
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        log.warning(f"Freqtrade safe GET {path} error: {e}")
        return None


async def _ft_post(path: str, body: dict = None) -> dict:
    global _ft_token
    token = await _get_ft_token()
    if not token:
        raise HTTPException(503, "Freqtrade unavailable")
    try:
        client = await _get_http_client()
        r = await client.post(
            f"{cfg.FREQTRADE_URL}/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            json=body or {},
            timeout=10
        )
        if r.status_code == 401:
            _ft_token = None
            raise HTTPException(503, "Freqtrade auth failed")
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Freqtrade POST {path} error: {e}")
        raise HTTPException(503, f"Freqtrade unavailable: {e}")


async def _ft_delete(path: str) -> dict:
    token = await _get_ft_token()
    if not token:
        raise HTTPException(503, "Freqtrade unavailable")
    try:
        client = await _get_http_client()
        r = await client.delete(
            f"{cfg.FREQTRADE_URL}/api/v1{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        return r.json()
    except Exception as e:
        log.error(f"Freqtrade DELETE {path} error: {e}")
        raise HTTPException(503, f"Freqtrade unavailable: {e}")


async def ft_force_enter(
    coin:      str,
    side:      str,
    entry:     float,
    sl:        float,
    tp:        float,
    leverage:  int,
    stake:     float,
    signal_id: int = None,
    grade:     str = ""
) -> dict:
    try:
        pair = f"{coin}/USDT:USDT"

        body = {
            "pair":         pair,
            "side":         side,
            "price":        entry,
            "stake_amount": round(stake, 2),
            "leverage":     leverage,
        }

        if signal_id:
            body["enter_tag"] = f"SE_{grade}_{signal_id}"

        log.info(
            f"Freqtrade forceenter: {coin} {side} "
            f"entry:{entry} sl:{sl} tp:{tp} "
            f"stake:{stake:.2f} leverage:{leverage} "
            f"tag:{body.get('enter_tag', '--')}"
        )

        result = await _ft_post("/forceenter", body)

        log.info(f"Freqtrade forceenter response: {result}")

        if result and result.get("trade_id"):
            log.info(
                f"Trade opened: {coin} {side} "
                f"trade_id:{result['trade_id']}"
            )
            return {"success": True, "trade_id": result["trade_id"], "result": result}
        else:
            log.error(f"Freqtrade forceenter failed: {coin} {side} response:{result}")
            return {"success": False, "error": str(result)}

    except Exception as e:
        log.error(f"ft_force_enter error {coin}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def ft_has_open_trade(coin: str) -> bool:
    try:
        status = await _ft_get_safe("/status")
        if not status or not isinstance(status, list):
            return False
        for t in status:
            pair = t.get("pair", "")
            c    = pair.replace("/USDT:USDT", "").replace("/USDT", "")
            if c == coin:
                return True
        return False
    except Exception:
        return False


async def ft_open_trade_count() -> int:
    try:
        status = await _ft_get_safe("/status")
        if not status or not isinstance(status, list):
            return 0
        return len(status)
    except Exception:
        return 0


def _parse_signal_id_from_tag(enter_tag: str) -> int | None:
    try:
        if not enter_tag or not enter_tag.startswith("SE_"):
            return None
        parts = enter_tag.split("_")
        if len(parts) >= 3:
            return int(parts[-1])
        return None
    except Exception:
        return None


async def _ft_ws_listener():
    global _ft_ws_connected, _ft_token
    while True:
        try:
            token = await _get_ft_token()
            if not token:
                log.warning("FT WS: no token — retrying in 10s")
                await asyncio.sleep(10)
                continue

            ws_url = cfg.FREQTRADE_URL.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = f"{ws_url}/api/v1/message/ws?token={token}"

            log.info(f"FT WS: connecting to {ws_url[:60]}...")

            async with websockets.connect(
                ws_url,
                ping_interval = 20,
                ping_timeout  = 10,
                close_timeout = 5,
                open_timeout  = 10
            ) as ws:
                _ft_ws_connected = True
                log.info("FT WS: connected ✅")

                await ws.send(json.dumps({
                    "type": "subscribe",
                    "data": ["trade", "entry_fill", "exit_fill", "status"]
                }))

                async for message in ws:
                    try:
                        data     = json.loads(message)
                        msg_type = data.get("type", "")

                        log.debug(f"FT WS event: {msg_type}")

                        for cb in _trade_event_callbacks:
                            try:
                                await cb(msg_type, data.get("data", {}))
                            except Exception as e:
                                log.error(f"FT WS callback error: {e}")

                    except Exception as e:
                        log.error(f"FT WS message parse error: {e}")

        except websockets.exceptions.ConnectionClosedError as e:
            _ft_ws_connected = False
            log.warning(f"FT WS connection closed: {e} — retrying in 5s")
            await asyncio.sleep(5)
        except websockets.exceptions.InvalidStatusCode as e:
            _ft_ws_connected = False
            _ft_token = None
            log.warning(f"FT WS invalid status (token expired?): {e} — retrying in 10s")
            await asyncio.sleep(10)
        except Exception as e:
            _ft_ws_connected = False
            log.warning(f"FT WS disconnected: {e} — retrying in 5s")
            await asyncio.sleep(5)


async def start_ft_ws():
    global _ft_ws_task
    if _ft_ws_task and not _ft_ws_task.done():
        return
    _ft_ws_task = asyncio.create_task(_ft_ws_listener())
    log.info("FT WS listener started")


async def stop_ft_ws():
    global _ft_ws_task, _http_client, _ft_ws_connected
    if _ft_ws_task:
        _ft_ws_task.cancel()
        try:
            await _ft_ws_task
        except asyncio.CancelledError:
            pass
        _ft_ws_task = None
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
    _ft_ws_connected = False
    log.info("FT WS listener stopped")


@router.get("/ft/status")
async def ft_status(request: Request):
    _auth(request)
    try:
        data = await _ft_get("/status")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/profit")
async def ft_profit(request: Request):
    _auth(request)
    try:
        data = await _ft_get("/profit")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/balance")
async def ft_balance(request: Request):
    _auth(request)
    try:
        data = await _ft_get("/balance")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/trades")
async def ft_trades(request: Request, limit: int = 20):
    _auth(request)
    try:
        data = await _ft_get(f"/trades?limit={limit}")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/daily")
async def ft_daily(request: Request, days: int = 7):
    _auth(request)
    try:
        data = await _ft_get(f"/daily?timescale={days}")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/whitelist")
async def ft_whitelist(request: Request):
    _auth(request)
    try:
        data = await _ft_get("/whitelist")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/config")
async def ft_config(request: Request):
    _auth(request)
    try:
        data = await _ft_get("/show_config")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/performance")
async def ft_performance(request: Request):
    _auth(request)
    try:
        data = await _ft_get("/performance")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/ping")
async def ft_ping(request: Request):
    _auth(request)
    try:
        data = await _ft_get("/ping")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/ft/start")
async def ft_start(request: Request):
    _auth(request)
    try:
        data = await _ft_post("/start")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/ft/stop")
async def ft_stop(request: Request):
    _auth(request)
    try:
        data = await _ft_post("/stop")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/ft/forcesell")
async def ft_forcesell(request: Request):
    _auth(request)
    try:
        body      = await request.json()
        tradeid   = body.get("tradeid")
        totp_code = body.get("totp_code", "")

        if not tradeid:
            raise HTTPException(400, "tradeid required")

        if not verify_totp(totp_code):
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid TOTP code"}
            )

        data = await _ft_post("/forcesell", {"tradeid": str(tradeid)})
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/ft/trades/{tradeid}")
async def ft_delete_trade(request: Request, tradeid: int):
    _auth(request)
    try:
        data = await _ft_delete(f"/trades/{tradeid}")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/summary")
async def ft_summary(request: Request):
    _auth(request)
    try:
        from database import SessionLocal, Signal as SignalModel

        status, profit, balance, daily, config = await asyncio.gather(
            _ft_get("/status"),
            _ft_get("/profit"),
            _ft_get("/balance"),
            _ft_get("/daily?timescale=7"),
            _ft_get("/show_config"),
            return_exceptions=True
        )

        bot_state = "unknown"
        if not isinstance(config, Exception) and config:
            bot_state = config.get("state", "unknown")

        trades_with_health = []
        if not isinstance(status, Exception) and status and isinstance(status, list):

            tp1_map = {}
            sl_map  = {}

            try:
                with SessionLocal() as db:
                    for trade in status:
                        pair      = trade.get("pair", "")
                        coin      = pair.replace("/USDT:USDT", "").replace("/USDT", "")
                        enter_tag = trade.get("enter_tag", "")
                        signal_id = _parse_signal_id_from_tag(enter_tag)

                        signal = None

                        if signal_id:
                            signal = db.query(SignalModel).filter(
                                SignalModel.id == signal_id
                            ).first()

                        if not signal:
                            is_short  = trade.get("is_short", False)
                            direction = "SHORT" if is_short else "LONG"
                            signal = db.query(SignalModel).filter(
                                SignalModel.coin      == coin,
                                SignalModel.direction == direction,
                                SignalModel.outcome   == "pending"
                            ).order_by(SignalModel.timestamp.asc()).first()

                        if signal:
                            if signal.tp1: tp1_map[coin] = float(signal.tp1)
                            if signal.sl:  sl_map[coin]  = float(signal.sl)

            except Exception as e:
                log.warning(f"tp1/sl fetch error: {e}")

            for trade in status:
                pair = trade.get("pair", "")
                coin = pair.replace("/USDT:USDT", "").replace("/USDT", "")

                health = None
                try:
                    from trade.health_monitor import get_health_from_redis
                    health = get_health_from_redis(coin)
                except Exception:
                    pass

                trade_copy              = dict(trade)
                trade_copy["health"]    = health
                trade_copy["tp1"]       = tp1_map.get(coin, None)
                trade_copy["sl_signal"] = sl_map.get(coin, None)
                trades_with_health.append(trade_copy)

        return JSONResponse(content={
            "status":    trades_with_health,
            "profit":    profit    if not isinstance(profit,    Exception) else {},
            "balance":   balance   if not isinstance(balance,   Exception) else {},
            "daily":     daily     if not isinstance(daily,     Exception) else [],
            "bot_state": bot_state
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/ws_status")
async def ft_ws_status(request: Request):
    _auth(request)
    return JSONResponse(content={"connected": _ft_ws_connected})