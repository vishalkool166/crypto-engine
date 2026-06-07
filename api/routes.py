from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from database import (
    get_db, Signal as SignalModel,
    Trade as TradeModel, BacktestResult
)
from alerts.scanner import (
    analyze_coin, scan_all_coins, get_db_stats
)
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
from api.formatters import (
    make_serializable, build_trade_data, build_risk_data,
    build_performance_data, build_radar_data, build_signal_queue,
    build_history_data, build_header_data
)
import traceback
import logging

log = logging.getLogger(__name__)
router = APIRouter()


# ═══════════════════════════════════════════════════════
# DASHBOARD
# Single call — returns everything display-ready.
# ═══════════════════════════════════════════════════════
@router.get("/dashboard")
async def dashboard():
    try:
        from database import SessionLocal

        trade_state = "idle"
        trade_data  = None

        if not state_manager.is_idle:
            state_manager.refresh()
            trade = state_manager.current_trade

            if trade and trade.is_active:
                current     = get_current_price(trade.coin)
                trade_state = trade.state
                trade_data  = build_trade_data(trade, current)

        risk_stats = risk_guard.get_daily_stats()
        risk_data  = build_risk_data(risk_stats)
        stats      = get_db_stats()

        db = SessionLocal()
        try:
            trades_raw = db.query(TradeModel).filter(
                TradeModel.is_active == False
            ).order_by(
                TradeModel.closed_at.desc()
            ).limit(10).all()

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
            cached = cache.get(f"signal_{coin}")
            if cached:
                cached_results.append(cached)

        if cached_results:
            cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            radar_data = build_radar_data(cached_results)
            queue_data = build_signal_queue(cached_results)
            last_scan  = "From cache"

        header_data = build_header_data(risk_stats, stats)

        return JSONResponse(
            content=make_serializable({
                "state":           trade_state,
                "trade":           trade_data,
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
        )

    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# ANALYZE
# ═══════════════════════════════════════════════════════
@router.get("/analyze/{coin}")
async def analyze(
    coin:     str,
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE
):
    coin = coin.upper()
    if coin not in cfg.COINS:
        raise HTTPException(400, f"{coin} not supported")
    try:
        result = await analyze_coin(coin, capital, leverage)
        if "error" in result:
            raise HTTPException(500, result["error"])
        return JSONResponse(content=make_serializable(result))
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# SCAN
# ═══════════════════════════════════════════════════════
@router.get("/scan")
async def scan():
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


# ═══════════════════════════════════════════════════════
# SIGNALS
# ═══════════════════════════════════════════════════════
@router.get("/signals")
async def get_signals(
    limit: int = 50,
    grade: str = None,
    coin:  str = None,
    db: Session = Depends(get_db)
):
    try:
        q = db.query(SignalModel).order_by(SignalModel.timestamp.desc())
        if grade:
            q = q.filter(SignalModel.grade == grade.upper())
        if coin:
            q = q.filter(SignalModel.coin == coin.upper())

        signals = q.limit(limit).all()
        result  = [{
            "id":          s.id,
            "timestamp":   s.timestamp.isoformat() if s.timestamp else None,
            "coin":        s.coin,
            "direction":   s.direction,
            "grade":       s.grade,
            "score":       s.score,
            "signal_type": s.signal_type,
            "entry":       s.entry,
            "sl":          s.sl,
            "tp1":         s.tp1,
            "tp2":         s.tp2,
            "risk_amt":    s.risk_amt,
            "regime":      s.regime,
            "session":     s.session,
            "outcome":     s.outcome,
            "exit_price":  s.exit_price,
            "pnl":         s.pnl
        } for s in signals]

        return JSONResponse(content=result)
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════
@router.get("/stats")
async def get_stats():
    try:
        return JSONResponse(content=make_serializable(get_db_stats()))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# TRADE
# ═══════════════════════════════════════════════════════
@router.get("/trade/status")
async def trade_status():
    try:
        if state_manager.is_idle:
            return JSONResponse(content={"state": "idle", "trade": None})

        state_manager.refresh()
        trade   = state_manager.current_trade
        current = get_current_price(trade.coin)

        return JSONResponse(content={
            "state": trade.state,
            "trade": make_serializable(build_trade_data(trade, current))
        })
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.post("/trade/close")
async def close_trade():
    try:
        result = await trade_manager.manual_close()
        if not result["success"]:
            raise HTTPException(400, result["reason"])
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/trade/history")
async def trade_history(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    try:
        trades = db.query(TradeModel).filter(
            TradeModel.is_active == False
        ).order_by(TradeModel.closed_at.desc()).limit(limit).all()

        result = [{
            "id":            t.id,
            "coin":          t.coin,
            "direction":     t.direction,
            "grade":         t.grade,
            "entry_price":   t.entry_price,
            "exit_price":    t.exit_price,
            "sl_price":      t.sl_price,
            "tp1_price":     t.tp1_price,
            "tp2_price":     t.tp2_price,
            "pnl":           t.pnl,
            "outcome":       t.outcome,
            "close_reason":  t.close_reason,
            "risk_amt":      t.risk_amt,
            "position_size": t.position_size,
            "margin_used":   t.margin_used,
            "leverage":      t.leverage,
            "opened_at":     t.opened_at.isoformat() if t.opened_at else None,
            "closed_at":     t.closed_at.isoformat() if t.closed_at else None
        } for t in trades]

        return JSONResponse(content=result)
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# RISK
# ═══════════════════════════════════════════════════════
@router.get("/risk/daily")
async def daily_risk():
    try:
        return JSONResponse(content=make_serializable(risk_guard.get_daily_stats()))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════
# MARKET
# ═══════════════════════════════════════════════════════
@router.get("/market/{coin}")
async def market(coin: str):
    coin   = coin.upper()
    cached = cache.get(f"signal_{coin}")
    if cached:
        return JSONResponse(content=make_serializable(cached["market"]))
    raise HTTPException(404, "Run scan first")


@router.get("/fear-greed")
async def fear_greed():
    try:
        return JSONResponse(content=make_serializable(await get_fear_greed()))
    except Exception:
        return JSONResponse(content={"value": 50, "label": "Neutral"})


@router.get("/macro-events")
async def macro_events():
    try:
        return JSONResponse(content=make_serializable(await get_news_filter()))
    except Exception:
        return JSONResponse(content=[])


# ═══════════════════════════════════════════════════════
# BACKTEST
# ═══════════════════════════════════════════════════════
@router.get("/backtest/{coin}")
async def backtest(
    coin:     str,
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE
):
    coin = coin.upper()
    if coin not in cfg.COINS:
        raise HTTPException(400, f"{coin} not supported")
    try:
        result = run_backtest(coin=coin, capital=capital, leverage=leverage)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return JSONResponse(content=make_serializable(result))
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/backtest/all/run")
async def backtest_all(
    capital:  float = cfg.CAPITAL,
    leverage: int   = cfg.LEVERAGE
):
    results = []
    for coin in cfg.COINS:
        try:
            r = run_backtest(coin=coin, capital=capital, leverage=leverage)
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
async def backtest_history(db: Session = Depends(get_db)):
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


# ═══════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════
@router.get("/health")
async def health():
    trade = state_manager.current_trade
    return JSONResponse(content={
        "status":       "ok",
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "trade_state":  state_manager.current_state,
        "active_coin":  trade.coin if trade else None,
        "paper_mode":   cfg.PAPER_TRADING,
        "health_state": state_manager.health_state
    })


# ═══════════════════════════════════════════════════════
# FACTOR ANALYSIS
# ═══════════════════════════════════════════════════════
@router.get("/analysis/factors")
async def factor_analysis():
    try:
        return JSONResponse(content=make_serializable(run_factor_analysis()))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))