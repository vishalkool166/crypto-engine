import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from auth import verify_totp
from config import cfg

log    = logging.getLogger(__name__)
router = APIRouter()


def _auth(request: Request) -> None:
    from saas.security import require_admin_access
    require_admin_access(request)


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
async def trades_history(request: Request, limit: int = 20, offset: int = 0,
                         outcome: str | None = None, grade: str | None = None,
                         coin: str | None = None):
    _auth(request)
    if not 1 <= limit <= 100 or not 0 <= offset <= 1_000_000:
        raise HTTPException(422, 'Pagination out of range')
    if outcome and outcome not in ('all', 'win', 'loss', 'timeout', 'expired'):
        raise HTTPException(422, 'Invalid outcome filter')
    if grade and grade not in ('all', 'A+', 'A', 'B'):
        raise HTTPException(422, 'Invalid grade filter')
    if coin and (len(coin) > 24 or not coin.isalnum()):
        raise HTTPException(422, 'Invalid coin filter')
    try:
        from trade.monitor import get_trade_history, count_trade_history
        filters = dict(outcome=outcome, grade=grade, coin=coin, closed_only=True)
        trades = get_trade_history(limit=limit, offset=offset, **filters)
        total = count_trade_history(**filters)
        return JSONResponse(content={"trades": trades, "trades_count": total,
                                     "limit": limit, "offset": offset})
    except Exception as e:
        log.error("trades_history error: %s", type(e).__name__)
        raise HTTPException(500, "Trade history unavailable")


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

        if not isinstance(trade_id, int) or isinstance(trade_id, bool) or trade_id < 1:
            raise HTTPException(400, "Valid trade_id required")

        if not verify_totp(totp_code):
            from auth import audit
            audit("manual_trade_close", "dashboard", f"trade_id:{trade_id}; invalid TOTP",
                  ip=request.client.host if request.client else "", success=False)
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid TOTP code"}
            )

        from database import get_session, Trade as TradeModel
        with get_session() as db:
            trade = db.query(TradeModel).filter(TradeModel.id == trade_id).first()
            if not trade:
                from auth import audit
                audit("manual_trade_close", "dashboard", f"trade_id:{trade_id}; not found",
                      ip=request.client.host if request.client else "", success=False)
                raise HTTPException(404, "Trade not found")
            if not trade.is_active or trade.state != "open":
                from auth import audit
                audit("manual_trade_close", "dashboard", f"trade_id:{trade_id}; not active",
                      ip=request.client.host if request.client else "", success=False)
                raise HTTPException(409, "Trade is not an active open position")
            # The durable trade row is authoritative. Ignore caller-provided
            # coin/direction fields so an ID cannot be paired with another symbol.
            coin, direction = trade.coin, trade.direction

        from trade.executor import close_position
        result = await close_position(
            coin      = coin,
            direction = direction,
            trade_id  = trade_id,
            reason    = "manual_close",
        )
        from auth import audit
        succeeded = bool(result.get("success")) if isinstance(result, dict) else False
        audit("manual_trade_close", "dashboard", f"trade_id:{trade_id}; {coin} {direction}",
              ip=request.client.host if request.client else "", success=succeeded)
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        try:
            from auth import audit
            audit("manual_trade_close", "dashboard", f"request error:{type(e).__name__}",
                  ip=request.client.host if request.client else "", success=False)
        except Exception:
            pass
        log.error("trades_close error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/trades/start")
async def trades_start(request: Request):
    _auth(request)
    try:
        body = await request.json()
        if not verify_totp(body.get("totp_code", "")):
            from auth import audit
            audit("scanner_start", "dashboard", "invalid TOTP", ip=request.client.host if request.client else "", success=False)
            return JSONResponse(status_code=401, content={"success": False, "reason": "Invalid TOTP code"})
        from alerts.scanner import scan_all_coins
        asyncio.create_task(scan_all_coins())
        from auth import audit
        audit("scanner_start", "dashboard", "scanner started", ip=request.client.host if request.client else "")
        return JSONResponse(content={"status": "ok", "message": "Scanner started"})
    except Exception as e:
        log.error("trades_start error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/trades/stop")
async def trades_stop(request: Request):
    _auth(request)
    try:
        body = await request.json()
        if not verify_totp(body.get("totp_code", "")):
            from auth import audit
            audit("monitor_stop", "dashboard", "invalid TOTP", ip=request.client.host if request.client else "", success=False)
            return JSONResponse(status_code=401, content={"success": False, "reason": "Invalid TOTP code"})
        from trade.monitor import stop_monitor
        stop_monitor()
        from auth import audit
        audit("monitor_stop", "dashboard", "monitor stopped", ip=request.client.host if request.client else "")
        return JSONResponse(content={"status": "ok", "message": "Monitor stopped"})
    except Exception as e:
        log.error("trades_stop error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/trades/kill-switch")
async def trades_kill_switch(request: Request):
    """Persist an entry-only halt; reset is gated by fresh exchange reconciliation."""
    _auth(request)
    body = await request.json()
    action = body.get("action") if isinstance(body, dict) else None
    ip = request.client.host if request.client else ""

    if action not in ("halt", "reset"):
        raise HTTPException(400, "action must be halt or reset")
    if not verify_totp(body.get("totp_code", "")):
        from auth import audit
        audit("entry_kill_switch", "dashboard", f"{action}; invalid TOTP", ip=ip, success=False)
        return JSONResponse(status_code=401, content={"success": False, "reason": "Invalid TOTP code"})

    try:
        import runtime_state as rs
        if action == "halt":
            state = rs.set_new_exposure_halt(True, str(body.get("reason") or "operator halt"))
        else:
            if not rs.get_new_exposure_halt().get("enabled"):
                raise HTTPException(409, "New-exposure halt is not active")
            if body.get("confirmation") != "I_HAVE_RECONCILED":
                raise HTTPException(400, "Explicit reconciliation confirmation required")

            # A reset never relies on a cached UI snapshot. Broker, local trade
            # state, and durable order intents must all be known and clear.
            from trade.exchange import get_positions
            positions = await get_positions()
            if positions:
                raise HTTPException(409, "Exchange positions remain open; reconciliation required")
            from database import get_session, Trade as TradeModel
            with get_session() as db:
                unresolved_trades = db.query(TradeModel).filter(
                    TradeModel.state.in_(("pending", "open", "reconciliation_required"))
                ).count()
            if unresolved_trades:
                raise HTTPException(409, "Local trade state requires reconciliation")
            from trade.order_journal import unresolved
            if unresolved():
                raise HTTPException(409, "Order intents require reconciliation")
            state = rs.set_new_exposure_halt(False, "operator reset after reconciliation")

        from auth import audit
        audit("entry_kill_switch", "dashboard", f"{action}; {state['reason']}", ip=ip)
        return JSONResponse(content={"success": True, "halt": state})
    except HTTPException as exc:
        from auth import audit
        audit("entry_kill_switch", "dashboard", f"{action}; denied:{exc.status_code}", ip=ip, success=False)
        raise
    except Exception as exc:
        from auth import audit
        audit("entry_kill_switch", "dashboard", f"{action}; error:{type(exc).__name__}", ip=ip, success=False)
        log.error("trades_kill_switch error: %s", type(exc).__name__)
        raise HTTPException(503, "Kill-switch state or reconciliation unavailable")


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

        from trade.safety import ensure_live_opt_in
        try:
            ensure_live_opt_in(new_mode)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        from trade.order_journal import unresolved
        if unresolved():
            raise HTTPException(409, "Unresolved exchange order intents; reconciliation required")

        if new_mode == "live" and (not cfg.BINANCE_API_KEY or not cfg.BINANCE_SECRET):
            return JSONResponse(
                status_code = 400,
                content     = {"success": False, "reason": "Binance live API keys not configured"}
            )

        from trade.safety import apply_trading_mode
        await apply_trading_mode(new_mode)

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
