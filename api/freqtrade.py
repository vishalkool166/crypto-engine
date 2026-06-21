import logging
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from config import cfg
from auth import is_authenticated

log    = logging.getLogger(__name__)
router = APIRouter()

_ft_token: str = None


def _auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


async def _get_ft_token() -> str:
    global _ft_token
    if _ft_token:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{cfg.FREQTRADE_URL}/api/v1/ping",
                    headers={"Authorization": f"Bearer {_ft_token}"},
                    timeout=5
                )
                if r.status_code == 200:
                    return _ft_token
        except Exception:
            pass

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{cfg.FREQTRADE_URL}/api/v1/token/login",
                json={
                    "username": cfg.FREQTRADE_USERNAME,
                    "password": cfg.FREQTRADE_PASSWORD
                },
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
        return None


async def _ft_get(path: str) -> dict:
    token = await _get_ft_token()
    if not token:
        raise HTTPException(503, "Freqtrade unavailable")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{cfg.FREQTRADE_URL}/api/v1{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            if r.status_code == 401:
                global _ft_token
                _ft_token = None
                raise HTTPException(503, "Freqtrade auth failed")
            return r.json()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Freqtrade GET {path} error: {e}")
        raise HTTPException(503, f"Freqtrade unavailable: {e}")


async def _ft_post(path: str, body: dict = None) -> dict:
    token = await _get_ft_token()
    if not token:
        raise HTTPException(503, "Freqtrade unavailable")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{cfg.FREQTRADE_URL}/api/v1{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=body or {},
                timeout=10
            )
            if r.status_code == 401:
                global _ft_token
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
        async with httpx.AsyncClient() as client:
            r = await client.delete(
                f"{cfg.FREQTRADE_URL}/api/v1{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            return r.json()
    except Exception as e:
        log.error(f"Freqtrade DELETE {path} error: {e}")
        raise HTTPException(503, f"Freqtrade unavailable: {e}")


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
        body    = await request.json()
        tradeid = body.get("tradeid")
        if not tradeid:
            raise HTTPException(400, "tradeid required")
        data = await _ft_post(f"/forcesell", {"tradeid": str(tradeid)})
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
    """Single endpoint that returns everything needed for dashboard."""
    _auth(request)
    try:
        import asyncio
        status, profit, balance, daily = await asyncio.gather(
            _ft_get("/status"),
            _ft_get("/profit"),
            _ft_get("/balance"),
            _ft_get("/daily?timescale=7"),
            return_exceptions=True
        )

        return JSONResponse(content={
            "status":  status  if not isinstance(status,  Exception) else [],
            "profit":  profit  if not isinstance(profit,  Exception) else {},
            "balance": balance if not isinstance(balance, Exception) else {},
            "daily":   daily   if not isinstance(daily,   Exception) else [],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))