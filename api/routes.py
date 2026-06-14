import asyncio
import logging
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from database import (
    get_db, Signal as SignalModel,
    Trade as TradeModel, BacktestResult,
    SessionLocal
)
from alerts.scanner import analyze_coin, scan_all_coins, get_db_stats
from data.cache import cache
from data.fetcher import get_fear_greed, get_news_filter
from trade.state import state_manager
from trade.manager import trade_manager
from trade.risk import risk_guard
from trade.orders import get_current_price
from backtest.engine import run_backtest
from backtest.factor_analysis import run_factor_analysis
from scheduler import get_next_scan_epoch
from config import cfg
from auth import is_authenticated, audit
from api.formatters import (
    make_serializable, build_trade_data, build_all_trades_data,
    build_risk_data, build_performance_data, build_radar_data,
    build_signal_queue, build_history_data, build_header_data
)

log     = logging.getLogger(__name__)
router  = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


async def build_dashboard_payload() -> dict:
    trades_data = []

    if not state_manager.is_idle:
        state_manager.refresh()
        for trade in state_manager.active_trades.values():
            if trade.is_active:
                current = get_current_price(trade.coin)
                trades_data.append(build_trade_data(trade, current))

    trade_state = "idle" if state_manager.is_idle else "in_trade"
    trade_data  = trades_data[0] if len(trades_data) == 1 else None

    risk_stats = risk_guard.get_daily_stats()
    risk_data  = build_risk_data(risk_stats)
    stats      = get_db_stats()

    db = SessionLocal()
    try:
        trades_raw = db.query(TradeModel).filter(
            TradeModel.is_active == False
        ).order_by(TradeModel.closed_at.desc()).limit(10).all()

        trades_list = [{
            "coin":         t.coin,
            "direction":    t.direction,
            "grade":        t.grade,
            "pnl":          t.pnl,
            "outcome":      t.outcome,
            "close_reason": t.close_reason,
            "closed_at":    t.closed_at.isoformat() if t.closed_at else None
        } for t in trades_raw]
    finally:
        db.close()

    perf_data    = build_performance_data(stats, trades_list)
    history_data = build_history_data(trades_list)

    radar_data = []
    queue_data = []
    last_scan  = "--"

    cached_results = []
    for coin in cfg.COINS:
        cached = cache.get_raw(f"signal_{coin}")
        if cached:
            cached_results.append(cached)

    if cached_results:
        cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        radar_data = build_radar_data(cached_results)
        queue_data = build_signal_queue(cached_results)
        last_scan  = "From cache"

    header_data = build_header_data(risk_stats, stats)

    return make_serializable({
        "type":            "dashboard",
        "state":           trade_state,
        "trade":           trade_data,
        "trades":          trades_data,
        "risk":            risk_data,
        "performance":     perf_data,
        "history":         history_data,
        "radar":           radar_data,
        "queue":           queue_data,
        "header":          header_data,
        "last_scan":       last_scan,
        "next_scan_epoch": get_next_scan_epoch(),
        "timestamp":       datetime.now(timezone.utc).isoformat()
    })


@router.get("/dashboard")
@limiter.limit("60/minute")
async def dashboard(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=await build_dashboard_payload())
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/analyze/{coin}")
@limiter.limit("10/minute")
async def analyze(request: Request, coin: str):
    _auth(request)
    coin = coin.upper()
    if coin not in cfg.COINS:
        raise HTTPException(400, f"{coin} not supported")
    try:
        result = await analyze_coin(coin)
        if "error" in result:
            raise HTTPException(500, result["error"])
        return JSONResponse(content=make_serializable(result))
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/scan")
@limiter.limit("1/minute")
async def scan(request: Request):
    _auth(request)
    try:
        results = await scan_all_coins()
        return JSONResponse(content={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count":     len(results),
            "results":   make_serializable(results)
        })
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/signals")
async def get_signals(
    request:  Request,
    limit:    int = 50,
    grade:    str = None,
    coin:     str = None,
    db: Session = Depends(get_db)
):
    _auth(request)
    try:
        q = db.query(SignalModel).order_by(SignalModel.timestamp.desc())
        if grade:
            q = q.filter(SignalModel.grade == grade.upper())
        if coin:
            q = q.filter(SignalModel.coin == coin.upper())

        signals = q.limit(limit).all()
        result  = [{
            "id":           s.id,
            "timestamp":    s.timestamp.isoformat() if s.timestamp else None,
            "coin":         s.coin,
            "direction":    s.direction,
            "grade":        s.grade,
            "score":        s.score,
            "signal_type":  s.signal_type,
            "entry":        s.entry,
            "sl":           s.sl,
            "tp1":          s.tp1,
            "tp2":          s.tp2,
            "risk_amt":     s.risk_amt,
            "regime":       s.regime,
            "session":      s.session,
            "outcome":      s.outcome,
            "exit_price":   s.exit_price,
            "pnl":          s.pnl,
            "market_score": s.market_score,
            "entry_score":  s.entry_score,
            "btc_score":    s.btc_score,
        } for s in signals]

        return JSONResponse(content=result)
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/stats")
async def get_stats(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(get_db_stats()))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/trade/status")
async def trade_status(request: Request):
    _auth(request)
    try:
        if state_manager.is_idle:
            return JSONResponse(content={"state": "idle", "trade": None, "trades": []})

        state_manager.refresh()
        trades_data = []
        for trade in state_manager.active_trades.values():
            current = get_current_price(trade.coin)
            trades_data.append(build_trade_data(trade, current))

        return JSONResponse(content={
            "state":  "in_trade",
            "trade":  trades_data[0] if trades_data else None,
            "trades": make_serializable(trades_data)
        })
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.post("/trade/close")
async def close_trade(request: Request):
    _auth(request)
    try:
        body     = await request.json() if request.headers.get("content-type") == "application/json" else {}
        trade_id = body.get("trade_id")
        result   = await trade_manager.manual_close(trade_id=trade_id)
        if not result["success"]:
            raise HTTPException(400, result["reason"])
        ip = request.client.host if request.client else ""
        audit("manual_close", "api", f"trade_id:{trade_id}", ip=ip)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/trade/history")
async def trade_history(
    request: Request,
    limit:   int = 20,
    db: Session = Depends(get_db)
):
    _auth(request)
    try:
        trades = db.query(TradeModel).filter(
            TradeModel.is_active == False
        ).order_by(TradeModel.closed_at.desc()).limit(limit).all()

        result = [{
            "id":               t.id,
            "coin":             t.coin,
            "direction":        t.direction,
            "grade":            t.grade,
            "entry_price":      t.entry_price,
            "exit_price":       t.exit_price,
            "sl_price":         t.sl_price,
            "tp1_price":        t.tp1_price,
            "tp2_price":        t.tp2_price,
            "pnl":              t.pnl,
            "outcome":          t.outcome,
            "close_reason":     t.close_reason,
            "risk_amt":         t.risk_amt,
            "position_size":    t.position_size,
            "margin_used":      t.margin_used,
            "leverage":         t.leverage,
            "tp1_hit":          t.tp1_hit,
            "partial_pnl":      t.partial_pnl,
            "regime_at_entry":  t.regime_at_entry,
            "session_at_entry": t.session_at_entry,
            "score_at_entry":   t.score_at_entry,
            "balance_at_open":  t.balance_at_open,
            "tier_at_open":     t.tier_at_open,
            "opened_at":        t.opened_at.isoformat() if t.opened_at else None,
            "closed_at":        t.closed_at.isoformat() if t.closed_at else None
        } for t in trades]

        return JSONResponse(content=result)
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/risk/daily")
async def daily_risk(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(risk_guard.get_daily_stats()))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/market/{coin}")
async def market(request: Request, coin: str):
    _auth(request)
    coin   = coin.upper()
    cached = cache.get_raw(f"signal_{coin}")
    if cached:
        return JSONResponse(content=make_serializable(cached["market"]))
    raise HTTPException(404, "Run scan first")


@router.get("/fear-greed")
async def fear_greed(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(await get_fear_greed()))
    except Exception:
        return JSONResponse(content={"value": 50, "label": "Neutral"})


@router.get("/macro-events")
async def macro_events(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(await get_news_filter()))
    except Exception:
        return JSONResponse(content=[])


@router.get("/backtest/{coin}")
async def backtest(request: Request, coin: str):
    _auth(request)
    coin = coin.upper()
    if coin not in cfg.COINS:
        raise HTTPException(400, f"{coin} not supported")
    try:
        from trade.risk import get_current_tier
        tier   = get_current_tier()
        loop   = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None, lambda: run_backtest(
                    coin=coin,
                    capital=tier["balance"] or cfg.CAPITAL,
                    leverage=tier["leverage"]
                )
            ),
            timeout=120.0
        )
        if "error" in result:
            raise HTTPException(400, result["error"])
        return JSONResponse(content=make_serializable(result))
    except asyncio.TimeoutError:
        raise HTTPException(408, "Backtest timed out")
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/backtest/all/run")
async def backtest_all(request: Request):
    _auth(request)
    from trade.risk import get_current_tier
    tier    = get_current_tier()
    results = []
    loop    = asyncio.get_running_loop()

    for coin in cfg.COINS:
        try:
            r = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda c=coin: run_backtest(
                        coin=c,
                        capital=tier["balance"] or cfg.CAPITAL,
                        leverage=tier["leverage"]
                    )
                ),
                timeout=120.0
            )
            if "error" not in r:
                results.append(r)
        except Exception as e:
            log.error(f"Backtest error {coin}: {e}")
            continue

    results.sort(key=lambda x: x.get("win_rate", 0), reverse=True)
    return JSONResponse(content=make_serializable({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "count":     len(results),
        "results":   results
    }))


@router.get("/backtest/history/all")
async def backtest_history(request: Request, db: Session = Depends(get_db)):
    _auth(request)
    try:
        rows = db.query(BacktestResult).order_by(
            BacktestResult.run_at.desc()
        ).limit(50).all()

        result = [{
            "id":           r.id,
            "run_at":       r.run_at.isoformat() if r.run_at else None,
            "coin":         r.coin,
            "period_start": r.period_start,
            "period_end":   r.period_end,
            "total_trades": r.total_trades,
            "wins":         r.wins,
            "losses":       r.losses,
            "win_rate":     r.win_rate,
            "total_pnl":    r.total_pnl,
            "max_drawdown": r.max_drawdown,
            "notes":        r.notes
        } for r in rows]

        return JSONResponse(content=make_serializable(result))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/health")
async def health(request: Request):
    trade = state_manager.current_trade
    import runtime_state as rs
    return JSONResponse(content={
        "status":        "ok",
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "trade_state":   state_manager.current_state,
        "active_trades": len(state_manager.active_trades),
        "active_coin":   trade.coin if trade else None,
        "trading_mode":  rs.get_trading_mode(),
        "health_state":  state_manager.health_state
    })


@router.get("/analysis/factors")
async def factor_analysis(request: Request):
    _auth(request)
    try:
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_factor_analysis)
        return JSONResponse(content=make_serializable(result))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/audit/log")
async def audit_log(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    _auth(request)
    try:
        from database import AuditLog
        rows = db.query(AuditLog).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).all()

        result = [{
            "id":        r.id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "action":    r.action,
            "source":    r.source,
            "detail":    r.detail,
            "ip":        r.ip,
            "success":   r.success
        } for r in rows]

        return JSONResponse(content=result)
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/tier/status")
async def tier_status(request: Request):
    _auth(request)
    from trade.risk import get_current_tier
    import runtime_state as rs
    tier    = get_current_tier()
    balance = rs.get_balance_cache()
    return JSONResponse(content={
        "tier":          tier["tier"],
        "balance":       tier["balance"],
        "risk_pct":      tier["risk_pct"],
        "max_trades":    tier["max_trades"],
        "leverage":      tier["leverage"],
        "balance_cache": balance
    })