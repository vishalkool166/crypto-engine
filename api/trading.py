import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from auth import is_authenticated, verify_totp
from config import cfg

log    = logging.getLogger(__name__)
router = APIRouter()


def _auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


@router.get("/trades/open")
async def trades_open(request: Request):
    _auth(request)
    try:
        from trade.monitor import get_open_positions_enriched
        positions = await get_open_positions_enriched()
        return JSONResponse(content=positions)
    except Exception as e:
        log.error("trades_open error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/trades/balance")
async def trades_balance(request: Request):
    _auth(request)
    try:
        from trade.exchange import get_balance
        balance = await get_balance()
        return JSONResponse(content={
            "currencies": [{
                "currency":   "USDT",
                "free":       balance["free"],
                "used":       balance["used"],
                "total":      balance["total"],
                "unrealized": balance.get("unrealized", 0.0),
            }],
            "total":      balance["total"],
            "free":       balance["free"],
            "used":       balance["used"],
            "unrealized": balance.get("unrealized", 0.0),
        })
    except Exception as e:
        log.error("trades_balance error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/trades/profit")
async def trades_profit(request: Request):
    _auth(request)
    try:
        from trade.monitor import get_profit_summary
        return JSONResponse(content=get_profit_summary())
    except Exception as e:
        log.error("trades_profit error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/trades/history")
async def trades_history(request: Request, limit: int = 20, offset: int = 0):
    _auth(request)
    try:
        from trade.monitor import get_trade_history
        trades = get_trade_history(limit=limit, offset=offset)
        return JSONResponse(content={"trades": trades, "trades_count": len(trades)})
    except Exception as e:
        log.error("trades_history error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/trades/daily")
async def trades_daily(request: Request, days: int = 7):
    _auth(request)
    try:
        from trade.monitor import get_daily_breakdown
        return JSONResponse(content={"data": get_daily_breakdown(days=days)})
    except Exception as e:
        log.error("trades_daily error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/trades/performance")
async def trades_performance(request: Request):
    _auth(request)
    try:
        from trade.monitor import get_performance_by_coin
        return JSONResponse(content=get_performance_by_coin())
    except Exception as e:
        log.error("trades_performance error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/trades/summary")
async def trades_summary(request: Request):
    _auth(request)
    try:
        from trade.monitor import get_open_positions_enriched, get_profit_summary, get_daily_breakdown
        from trade.exchange import get_balance

        async def _profit() -> dict:
            return get_profit_summary()

        async def _daily() -> list:
            return get_daily_breakdown(7)

        positions, profit, balance, daily = await asyncio.gather(
            get_open_positions_enriched(),
            _profit(),
            get_balance(),
            _daily(),
            return_exceptions=True,
        )

        if isinstance(positions, Exception): positions = []
        if isinstance(profit,    Exception): profit    = {}
        if isinstance(balance,   Exception): balance   = {"total": 0, "free": 0, "used": 0, "unrealized": 0}
        if isinstance(daily,     Exception): daily     = []

        unrealized = sum(
            float(t.get("unrealized_pnl") or 0)
            for t in (positions if isinstance(positions, list) else [])
        )

        return JSONResponse(content={
            "status":    positions,
            "profit":    profit,
            "balance": {
                "currencies": [{
                    "currency":   "USDT",
                    "free":       balance.get("free",       0),
                    "used":       balance.get("used",       0),
                    "total":      balance.get("total",      0),
                    "unrealized": unrealized,
                }],
                "total":      balance.get("total", 0),
                "free":       balance.get("free",  0),
                "used":       balance.get("used",  0),
                "unrealized": unrealized,
            },
            "daily":     {"data": daily},
            "bot_state": "running",
        })
    except Exception as e:
        log.error("trades_summary error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/trades/close")
async def trades_close(request: Request):
    _auth(request)
    try:
        body      = await request.json()
        trade_id  = body.get("trade_id")
        totp_code = body.get("totp_code", "")
        coin      = body.get("coin", "")
        direction = body.get("direction", "")

        if not trade_id:
            raise HTTPException(400, "trade_id required")

        if not verify_totp(totp_code):
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid TOTP code"}
            )

        if not coin or not direction:
            from database import get_session, Trade as TradeModel
            with get_session() as db:
                trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
                if not trade:
                    raise HTTPException(404, "Trade not found")
                coin      = trade.coin
                direction = trade.direction

        from trade.executor import close_position
        result = await close_position(
            coin      = coin,
            direction = direction,
            trade_id  = trade_id,
            reason    = "manual_close",
        )
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error("trades_close error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/trades/start")
async def trades_start(request: Request):
    _auth(request)
    try:
        from alerts.scanner import scan_all_coins
        asyncio.create_task(scan_all_coins())
        return JSONResponse(content={"status": "ok", "message": "Scanner started"})
    except Exception as e:
        log.error("trades_start error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/trades/stop")
async def trades_stop(request: Request):
    _auth(request)
    try:
        from trade.monitor import stop_monitor
        stop_monitor()
        return JSONResponse(content={"status": "ok", "message": "Monitor stopped"})
    except Exception as e:
        log.error("trades_stop error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/trades/ping")
async def trades_ping(request: Request):
    _auth(request)
    try:
        from trade.exchange import ping
        ok = await ping()
        return JSONResponse(content={"status": "ok" if ok else "error", "mode": cfg.TRADING_MODE})
    except Exception as e:
        log.error("trades_ping error: %s", e)
        return JSONResponse(content={"status": "error", "reason": str(e)})


@router.get("/trades/ws_status")
async def trades_ws_status(request: Request):
    _auth(request)
    try:
        from trade.ws import get_ws_status
        status = get_ws_status()
        return JSONResponse(content={
            "connected":            status["mark_price_connected"] and status["user_data_connected"],
            "mark_price_connected": status["mark_price_connected"],
            "user_data_connected":  status["user_data_connected"],
            "prices_cached":        status["prices_cached"],
            "mode":                 cfg.TRADING_MODE,
        })
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/trades/config")
async def trades_config(request: Request):
    _auth(request)
    return JSONResponse(content={
        "trading_mode":  cfg.TRADING_MODE,
        "paper_trading": cfg.PAPER_TRADING,
        "coins":         cfg.COINS,
        "grades":        cfg.MIN_GRADE_TO_TRADE,
        "risk_pct":      cfg.RISK_PCT_PER_TRADE,
        "state":         "running",
    })


@router.get("/trades/whitelist")
async def trades_whitelist(request: Request):
    _auth(request)
    return JSONResponse(content={
        "whitelist": [f"{coin}/USDT:USDT" for coin in cfg.COINS],
        "length":    len(cfg.COINS),
    })


@router.post("/trades/mode")
async def trades_mode(request: Request):
    _auth(request)
    try:
        body     = await request.json()
        new_mode = body.get("mode", "")

        if new_mode not in ["live", "paper"]:
            raise HTTPException(400, "mode must be live or paper")

        if not verify_totp(body.get("totp_code", "")):
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid TOTP code"}
            )

        from trade.monitor import get_open_positions_enriched
        open_trades = await get_open_positions_enriched()
        if open_trades:
            return JSONResponse(
                status_code = 400,
                content     = {
                    "success": False,
                    "reason":  f"Cannot switch — {len(open_trades)} open trade(s). Close all first."
                }
            )

        if new_mode == "live" and (not cfg.BINANCE_API_KEY or not cfg.BINANCE_SECRET):
            return JSONResponse(
                status_code = 400,
                content     = {"success": False, "reason": "Binance live API keys not configured"}
            )

        from config import _ensure
        from trade.exchange import close_exchange

        _ensure("TRADING_MODE", new_mode)
        cfg.TRADING_MODE  = new_mode
        cfg.PAPER_TRADING = new_mode != "live"

        await close_exchange()

        from auth import audit
        audit("mode_toggle", "dashboard", f"mode:{new_mode}", ip=request.client.host if request.client else "")

        from api.dashboard import invalidate_all
        invalidate_all()

        return JSONResponse(content={
            "success": True,
            "mode":    new_mode,
            "message": f"Switched to {new_mode} mode"
        })

    except HTTPException:
        raise
    except Exception as e:
        log.error("trades_mode error: %s", e)
        raise HTTPException(500, str(e))