import asyncio
import logging
import traceback
import time
import os
import psutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from slowapi import Limiter
from slowapi.util import get_remote_address
from database import (
    get_db, Signal as SignalModel,
    BacktestResult, CoinConfig, SessionLocal
)
from alerts.scanner import analyze_coin, scan_all_coins, get_db_stats
from data.cache import cache
from data.fetcher import get_fear_greed, get_news_filter
from backtest.engine import run_backtest
from backtest.factor_analysis import run_factor_analysis
from scheduler import get_next_scan_epoch
from config import cfg
from auth import is_authenticated, audit
from api.dashboard import (
    get_summary, get_performance, get_signals_data,
    get_history, get_universe, get_ticker_bar,
    invalidate_all
)
import runtime_state as rs
import httpx

log     = logging.getLogger(__name__)
router  = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_cpu_cache     = {"pct": 0.0, "updated_at": 0.0}
_CPU_CACHE_TTL = 30.0
_health_cache: dict = {"data": None, "at": 0.0}


def make_serializable(obj):
    import math
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_serializable(i) for i in obj]
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (int, str, bool)):
        return obj
    return str(obj)


def _auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


def _cpu_pct() -> float:
    now = time.time()
    if now - _cpu_cache["updated_at"] > _CPU_CACHE_TTL:
        _cpu_cache["pct"]        = psutil.cpu_percent(interval=None)
        _cpu_cache["updated_at"] = now
    return _cpu_cache["pct"]


def _system_stats() -> dict:
    try:
        mem  = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        ut   = int(time.time() - psutil.boot_time())
        containers = []
        try:
            import docker
            for c in docker.from_env().containers.list():
                s        = c.stats(stream=False)
                mu       = s["memory_stats"].get("usage", 0)
                ml       = s["memory_stats"].get("limit", 1)
                cd       = s["cpu_stats"]["cpu_usage"]["total_usage"] - s["precpu_stats"]["cpu_usage"]["total_usage"]
                sd       = s["cpu_stats"].get("system_cpu_usage", 0) - s["precpu_stats"].get("system_cpu_usage", 0)
                containers.append({
                    "name":    c.name,
                    "status":  c.status,
                    "mem_mb":  round(mu / 1024 / 1024),
                    "mem_pct": round(mu / ml * 100, 1),
                    "cpu_pct": round((cd / sd * 100) if sd > 0 else 0, 1),
                })
        except Exception:
            pass
        return {
            "ram_used_mb":   round(mem.used   / 1024 / 1024),
            "ram_total_mb":  round(mem.total  / 1024 / 1024),
            "ram_pct":       round(mem.percent, 1),
            "ram_available": round(mem.available / 1024 / 1024),
            "cpu_pct":       round(_cpu_pct(), 1),
            "disk_used_gb":  round(disk.used  / 1024 ** 3, 1),
            "disk_total_gb": round(disk.total / 1024 ** 3, 1),
            "disk_pct":      round(disk.percent, 1),
            "uptime_secs":   ut,
            "uptime_str":    f"{ut//86400}d {(ut%86400)//3600}h {(ut%3600)//60}m",
            "containers":    containers,
        }
    except Exception as e:
        log.error("_system_stats error: %s", e)
        return {}


async def build_dashboard_payload() -> dict:
    return make_serializable({
        "type":        "dashboard",
        "summary":     get_summary(),
        "performance": get_performance(),
        "signals":     get_signals_data(),
        "history":     get_history(limit=10),
        "universe":    get_universe(),
        "ticker":      get_ticker_bar(),
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    })


def _db_stats_optimized() -> dict:
    try:
        with SessionLocal() as db:
            total   = db.query(func.count(SignalModel.id)).scalar() or 0
            pending = db.query(func.count(SignalModel.id)).filter(SignalModel.outcome == "pending").scalar() or 0
            wins    = db.query(func.count(SignalModel.id)).filter(SignalModel.outcome == "win").scalar()    or 0
            losses  = db.query(func.count(SignalModel.id)).filter(SignalModel.outcome == "loss").scalar()   or 0
            closed  = wins + losses
            pnl     = db.query(func.sum(SignalModel.pnl)).filter(SignalModel.outcome.in_(["win", "loss"])).scalar() or 0.0

            by_grade = {}
            for g in ["A+", "A", "B"]:
                gt  = db.query(func.count(SignalModel.id)).filter(SignalModel.grade == g, SignalModel.outcome.in_(["win", "loss"])).scalar() or 0
                gw  = db.query(func.count(SignalModel.id)).filter(SignalModel.grade == g, SignalModel.outcome == "win").scalar() or 0
                gp  = db.query(func.sum(SignalModel.pnl)).filter(SignalModel.grade == g, SignalModel.outcome.in_(["win", "loss"])).scalar() or 0.0
                by_grade[g] = {
                    "total":     gt,
                    "wins":      gw,
                    "losses":    gt - gw,
                    "win_rate":  round(gw / gt * 100, 1) if gt > 0 else 0,
                    "total_pnl": round(float(gp), 2),
                }

            return {
                "total":     total,
                "closed":    closed,
                "pending":   pending,
                "wins":      wins,
                "losses":    losses,
                "win_rate":  round(wins / closed * 100, 1) if closed > 0 else 0,
                "total_pnl": round(float(pnl), 2),
                "by_grade":  by_grade,
            }
    except Exception as e:
        log.error("_db_stats_optimized error: %s", e)
        return {}


@router.get("/dashboard")
@limiter.limit("60/minute")
async def dashboard(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=await build_dashboard_payload())
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/dashboard/summary")
async def dashboard_summary(request: Request):
    _auth(request)
    return JSONResponse(content=make_serializable(get_summary()))


@router.get("/dashboard/performance")
async def dashboard_performance(request: Request):
    _auth(request)
    return JSONResponse(content=make_serializable(get_performance()))


@router.get("/dashboard/signals")
async def dashboard_signals(request: Request):
    _auth(request)
    return JSONResponse(content=make_serializable(get_signals_data()))


@router.get("/dashboard/history")
async def dashboard_history(request: Request, limit: int = 20):
    _auth(request)
    return JSONResponse(content=make_serializable(get_history(limit=limit)))


@router.get("/dashboard/universe")
async def dashboard_universe(request: Request):
    _auth(request)
    return JSONResponse(content=make_serializable(get_universe()))


@router.get("/dashboard/ticker")
async def dashboard_ticker(request: Request):
    _auth(request)
    return JSONResponse(content=make_serializable(get_ticker_bar()))


@router.get("/dashboard/coin/{coin}")
async def dashboard_coin_detail(request: Request, coin: str):
    _auth(request)
    try:
        from api.dashboard import get_coin_detail
        data = get_coin_detail(coin.upper())
        if not data:
            raise HTTPException(404, f"No cached data for {coin} — run scan first")
        return JSONResponse(content=make_serializable(data))
    except HTTPException:
        raise
    except Exception as e:
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
        from data.cache import cache as _cache
        _cache.clear_all()
        results = await scan_all_coins()
        invalidate_all()
        return JSONResponse(content={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count":     len(results),
        })
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/signals")
async def get_signals(
    request: Request,
    limit:   int = 50,
    grade:   str = None,
    coin:    str = None,
    outcome: str = None,
    db: Session = Depends(get_db),
):
    _auth(request)
    try:
        q = db.query(SignalModel).order_by(SignalModel.timestamp.desc())
        if grade:
            q = q.filter(SignalModel.grade == grade.upper())
        if coin:
            q = q.filter(SignalModel.coin == coin.upper())
        if outcome:
            q = q.filter(SignalModel.outcome == outcome.lower())
        return JSONResponse(content=[{
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
            "risk_amt":     s.risk_amt,
            "regime":       s.regime,
            "session":      s.session,
            "outcome":      s.outcome,
            "exit_price":   s.exit_price,
            "pnl":          s.pnl,
            "market_score": s.market_score,
            "entry_score":  s.entry_score,
            "btc_score":    s.btc_score,
        } for s in q.limit(limit).all()])
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/signals/latest")
async def signals_latest(request: Request):
    _auth(request)
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            raise HTTPException(503, "Redis unavailable")
        best = max(
            (
                json.loads(d) for coin in cfg.COINS
                if (d := r.get(f"signal:{coin}USDT")) and
                time.time() <= json.loads(d).get("valid_until", 0) and
                json.loads(d).get("grade") in ["A+", "A"]
            ),
            key=lambda x: x.get("score", 0),
            default=None,
        )
        if not best:
            raise HTTPException(404, "No valid signals found")
        return JSONResponse(content=best)
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/signals/active")
async def signals_active(request: Request):
    _auth(request)
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if not r:
            raise HTTPException(503, "Redis unavailable")
        active = sorted(
            (
                json.loads(d) for coin in cfg.COINS
                if (d := r.get(f"signal:{coin}USDT")) and
                time.time() <= json.loads(d).get("valid_until", 0) and
                json.loads(d).get("grade") in cfg.MIN_GRADE_TO_TRADE
            ),
            key=lambda x: x.get("score", 0),
            reverse=True,
        )
        return JSONResponse(content=active)
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/signal/{signal_id}")
async def get_signal_by_id(request: Request, signal_id: int, db: Session = Depends(get_db)):
    row = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
    if not row:
        raise HTTPException(404, "Signal not found")
    return JSONResponse(content={
        "id": row.id, "coin": row.coin, "direction": row.direction,
        "grade": row.grade, "entry": row.entry, "sl": row.sl,
        "tp1": row.tp1, "score": row.score,
    })


@router.get("/coins/active")
async def coins_active():
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if r and (data := r.get("pairs:active")):
            return JSONResponse(content=json.loads(data))
        with SessionLocal() as db:
            pairs = [f"{r.coin}/USDT:USDT" for r in db.query(CoinConfig).filter(CoinConfig.enabled == True).all()]
        return JSONResponse(content={"pairs": pairs, "refresh_period": 1800})
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/stats")
async def get_stats(request: Request):
    _auth(request)
    return JSONResponse(content=make_serializable(_db_stats_optimized()))


@router.get("/market/{coin}")
async def market(request: Request, coin: str):
    _auth(request)
    cached = cache.get_raw(f"signal_{coin.upper()}")
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
        loop   = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: run_backtest(coin=coin, capital=1000, leverage=10)),
            timeout=120.0,
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
    loop    = asyncio.get_running_loop()
    results = []
    for coin in cfg.COINS:
        try:
            r = await asyncio.wait_for(
                loop.run_in_executor(None, lambda c=coin: run_backtest(coin=c, capital=1000, leverage=10)),
                timeout=120.0,
            )
            if "error" not in r:
                results.append(r)
        except Exception as e:
            log.error("Backtest error %s: %s", coin, e)
    results.sort(key=lambda x: x.get("win_rate", 0), reverse=True)
    return JSONResponse(content=make_serializable({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "count":     len(results),
        "results":   results,
    }))


@router.get("/backtest/history/all")
async def backtest_history(request: Request, db: Session = Depends(get_db)):
    _auth(request)
    rows = db.query(BacktestResult).order_by(BacktestResult.run_at.desc()).limit(50).all()
    return JSONResponse(content=make_serializable([{
        "id": r.id, "run_at": r.run_at.isoformat() if r.run_at else None,
        "coin": r.coin, "period_start": r.period_start, "period_end": r.period_end,
        "total_trades": r.total_trades, "wins": r.wins, "losses": r.losses,
        "win_rate": r.win_rate, "total_pnl": r.total_pnl,
        "max_drawdown": r.max_drawdown, "notes": r.notes,
    } for r in rows]))


@router.get("/health")
async def health(request: Request):
    if _health_cache["data"] and time.time() - _health_cache["at"] < 30:
        return JSONResponse(content=_health_cache["data"])
    from ml.eligibility import get_ml_status
    from trade.sync import get_sync_status
    redis_ok = False
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            r.ping()
            redis_ok = True
    except Exception:
        pass
    loop   = asyncio.get_running_loop()
    system = await loop.run_in_executor(None, _system_stats)
    result = {
        "status":          "ok",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "trading_mode":    "live" if not cfg.PAPER_TRADING else "paper",
        "coins_count":     len(cfg.COINS),
        "grades":          cfg.MIN_GRADE_TO_TRADE,
        "redis_connected": redis_ok,
        "ml_status":       get_ml_status(),
        "sync_status":     await get_sync_status(),
        "system":          system,
    }
    _health_cache["data"] = result
    _health_cache["at"]   = time.time()
    return JSONResponse(content=result)


@router.post("/sync/outcomes")
async def sync_outcomes(request: Request):
    _auth(request)
    try:
        from trade.sync import sync_trade_outcomes
        result = await sync_trade_outcomes()
        invalidate_all()
        return JSONResponse(content=result)
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/mode/status")
async def mode_status(request: Request):
    _auth(request)
    return JSONResponse(content={
        "mode":         "live" if not cfg.PAPER_TRADING else "paper",
        "paper":        cfg.PAPER_TRADING,
        "grades":       cfg.MIN_GRADE_TO_TRADE,
        "b_grade_live": False,
    })


@router.post("/mode/toggle")
async def mode_toggle(request: Request):
    _auth(request)
    try:
        body     = await request.json()
        new_mode = body.get("mode", "")
        if new_mode not in ["live", "paper"]:
            raise HTTPException(400, "Invalid mode")
        from auth import verify_totp
        if not verify_totp(body.get("totp_code", "")):
            return JSONResponse(status_code=401, content={"success": False, "reason": "Invalid TOTP code"})
        from trade.monitor import get_open_positions_enriched
        if await get_open_positions_enriched():
            return JSONResponse(status_code=400, content={"success": False, "reason": "Close all trades first"})
        if new_mode == "live" and (not cfg.BINANCE_API_KEY or not cfg.BINANCE_SECRET):
            return JSONResponse(status_code=400, content={"success": False, "reason": "Live API keys not configured"})
        from config import _ensure
        from trade.exchange import close_exchange
        _ensure("TRADING_MODE", new_mode)
        cfg.TRADING_MODE  = new_mode
        cfg.PAPER_TRADING = new_mode != "live"
        await close_exchange()
        audit("mode_toggle", "dashboard", f"mode:{new_mode}", ip=request.client.host if request.client else "")
        invalidate_all()
        return JSONResponse(content={"success": True, "mode": new_mode, "grades": cfg.MIN_GRADE_TO_TRADE})
    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


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
    from database import AuditLog
    rows = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return JSONResponse(content=[{
        "id": r.id, "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        "action": r.action, "source": r.source, "detail": r.detail,
        "ip": r.ip, "success": r.success,
    } for r in rows])


@router.get("/coins")
async def get_coins(request: Request):
    _auth(request)
    return JSONResponse(content=make_serializable(get_universe()))


@router.post("/coins/toggle")
async def toggle_coin(request: Request):
    _auth(request)
    try:
        body    = await request.json()
        coin    = body.get("coin", "").upper()
        enabled = body.get("enabled", True)
        with SessionLocal() as db:
            row = db.query(CoinConfig).filter(CoinConfig.coin == coin).first()
            if not row:
                return JSONResponse(status_code=404, content={"success": False, "reason": f"{coin} not found"})
            row.enabled = enabled
            db.commit()
        cfg.COINS = []
        from api.dashboard import _invalidate
        _invalidate("universe")
        audit("coin_toggle", "api", f"{coin} enabled:{enabled}", ip=request.client.host if request.client else "")
        return JSONResponse(content={"success": True, "coin": coin, "enabled": enabled})
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


async def _backfill_coin(coin: str) -> None:
    try:
        from backfill import run_backfill
        await run_backfill(coins=[coin])
    except Exception as e:
        log.error("Auto backfill failed for %s: %s", coin, e)


@router.post("/coins/add")
async def add_coin(request: Request):
    _auth(request)
    try:
        body = await request.json()
        coin = body.get("coin", "").upper().strip().replace("USDT", "").replace("/", "")
        if not coin or len(coin) > 10:
            return JSONResponse(status_code=400, content={"success": False, "reason": "Invalid coin name"})
        try:
            from data.fetcher import exchange
            markets = await exchange.load_markets(reload=True)
            if f"{coin}/USDT" not in markets and f"{coin}/USDT:USDT" not in markets:
                return JSONResponse(status_code=400, content={"success": False, "reason": f"{coin} not found on Binance Futures"})
        except Exception as e:
            log.warning("Binance validation failed for %s: %s", coin, e)
            return JSONResponse(status_code=500, content={"success": False, "reason": f"Could not validate {coin}"})
        with SessionLocal() as db:
            existing = db.query(CoinConfig).filter(CoinConfig.coin == coin).first()
            if existing:
                existing.enabled = True
                db.commit()
                msg = f"{coin} re-enabled"
            else:
                db.add(CoinConfig(coin=coin, enabled=True, tier=1, source="manual"))
                db.commit()
                msg = f"{coin} added"
        cfg.COINS = []
        from api.dashboard import _invalidate
        _invalidate("universe")
        asyncio.create_task(_backfill_coin(coin))
        if coin not in cfg._FALLBACK_COINS:
            cfg._FALLBACK_COINS.append(coin)
        audit("coin_add", "api", msg, ip=request.client.host if request.client else "")
        return JSONResponse(content={"success": True, "coin": coin, "message": msg})
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.delete("/coins/{coin}")
async def remove_coin(request: Request, coin: str):
    _auth(request)
    try:
        coin = coin.upper()
        with SessionLocal() as db:
            row = db.query(CoinConfig).filter(CoinConfig.coin == coin).first()
            if row:
                db.delete(row)
                db.commit()
        cfg.COINS = []
        from api.dashboard import _invalidate
        _invalidate("universe")
        if coin in cfg._FALLBACK_COINS:
            cfg._FALLBACK_COINS.remove(coin)
        audit("coin_delete", "api", f"deleted:{coin}", ip=request.client.host if request.client else "")
        return JSONResponse(content={"success": True, "coin": coin})
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/coins/validate/{coin}")
async def validate_coin(request: Request, coin: str):
    _auth(request)
    coin = coin.upper().replace("USDT", "").replace("/", "")
    try:
        from data.fetcher import exchange
        markets = await exchange.load_markets(reload=True)
        if f"{coin}/USDT" not in markets and f"{coin}/USDT:USDT" not in markets:
            return JSONResponse(content={"valid": False, "reason": f"{coin} not found"})
        return JSONResponse(content={"valid": True, "coin": coin})
    except Exception as e:
        log.error("Coin validate error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/candles/{coin}/{tf}")
async def get_candles(request: Request, coin: str, tf: str):
    _auth(request)
    coin = coin.upper()
    if tf not in ["15m", "1h", "4h", "1d"]:
        raise HTTPException(400, f"Invalid timeframe. Use: 15m, 1h, 4h, 1d")
    try:
        from database import Candle
        limit = {"15m": 200, "1h": 300, "4h": 500, "1d": 365}.get(tf, 300)
        with SessionLocal() as db:
            candles = db.query(Candle).filter(
                Candle.coin == coin, Candle.timeframe == tf
            ).order_by(Candle.timestamp.desc()).limit(limit).all()
        if not candles:
            return JSONResponse(content=[])
        return JSONResponse(content=[{
            "time": c.timestamp // 1000, "open": c.open,
            "high": c.high, "low": c.low, "close": c.close, "volume": c.volume,
        } for c in reversed(candles)])
    except Exception as e:
        log.error("Candles error %s %s: %s", coin, tf, e)
        raise HTTPException(500, str(e))


@router.get("/proxy/binance/aggTrades")
async def proxy_binance_agg_trades(request: Request, symbol: str, limit: int = 100):
    _auth(request)
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://fapi.binance.com/fapi/v1/aggTrades",
                params={"symbol": symbol.upper(), "limit": limit},
                timeout=10.0,
            )
            return JSONResponse(content=res.json())
    except httpx.TimeoutException:
        raise HTTPException(504, "Binance API timeout")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/proxy/binance/price")
async def proxy_binance_price(request: Request, symbol: str):
    _auth(request)
    try:
        from redis_client import get_redis
        import json
        r = get_redis()
        if r and (data := r.get(f"ticker:{symbol.upper()}")):
            return JSONResponse(content={"price": str(json.loads(data).get("last", 0))})
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://fapi.binance.com/fapi/v1/ticker/price",
                params={"symbol": symbol.upper()},
                timeout=5.0,
            )
            return JSONResponse(content=res.json())
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/system/docker-purge")
async def docker_purge(request: Request):
    _auth(request)
    try:
        body = await request.json()
        from auth import verify_totp
        if not verify_totp(body.get("totp_code", "")):
            return JSONResponse(status_code=401, content={"success": False, "reason": "Invalid TOTP code"})
        import subprocess
        disk_before = psutil.disk_usage('/').used
        result      = subprocess.run(
            ["/usr/bin/docker", "system", "prune", "-f", "--volumes"],
            capture_output=True, text=True, timeout=120,
            cwd="/home/ubuntu/crypto-engine",
            env={**os.environ, "HOME": "/root", "PATH": "/usr/bin:/usr/local/bin:/bin"},
        )
        freed_mb = round((disk_before - psutil.disk_usage('/').used) / 1024 ** 2)
        audit("docker_purge", "dashboard", f"freed:{freed_mb}MB", ip=request.client.host if request.client else "")
        if result.returncode == 0:
            return JSONResponse(content={"success": True, "output": result.stdout, "freed_mb": freed_mb})
        return JSONResponse(status_code=500, content={"success": False, "reason": result.stderr or "Failed"})
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Docker purge timed out")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/system/disk")
async def system_disk(request: Request):
    _auth(request)
    disk = psutil.disk_usage('/')
    return JSONResponse(content={
        "used_gb":  round(disk.used  / 1024 ** 3, 1),
        "total_gb": round(disk.total / 1024 ** 3, 1),
        "free_gb":  round(disk.free  / 1024 ** 3, 1),
        "pct":      round(disk.percent, 1),
    })


@router.get("/backtest-signal/{coin}")
async def backtest_signal(request: Request, coin: str, date: str = None):
    _auth(request)
    coin = coin.upper()
    try:
        from data.store import load_candles
        from engines.indicators import calculate_all
        from engines.regime import detect_regime, assess_btc_stability
        from engines.sweep import detect_sweep
        from engines.displacement import detect_displacement
        from engines.retest import detect_retest
        from engines.confluence import score_confluence
        from engines.signal import run_no_trade_engine, generate_signal
        import pandas as pd
        import json

        if not date:
            raise HTTPException(400, "date parameter required (YYYY-MM-DD)")

        from redis_client import get_redis
        r         = get_redis()
        cache_key = f"backtest_signal:{coin}:{date}"
        if r and (cached := r.get(cache_key)):
            return JSONResponse(content=json.loads(cached))

        target_ts = pd.Timestamp(date, tz="UTC")
        window    = 200

        df_1d = load_candles(coin, "1d", limit=1000)
        df_4h = load_candles(coin, "4h", limit=2000)
        df_1h = load_candles(coin, "1h", limit=2000)
        df_1w = load_candles(coin, "1w", limit=500)

        if any(df is None for df in [df_1d, df_4h, df_1h, df_1w]):
            raise HTTPException(404, f"Insufficient data for {coin}")

        d1d_w = df_1d[df_1d.index < target_ts].iloc[-window:]
        d4h_w = df_4h[df_4h.index < target_ts].iloc[-window:]
        d1h_w = df_1h[df_1h.index < target_ts].iloc[-window:]
        d1w_w = df_1w[df_1w.index < target_ts].iloc[-100:]

        if any(len(df) < 50 for df in [d1d_w, d4h_w, d1h_w]) or len(d1w_w) < 10:
            raise HTTPException(404, f"Not enough historical data for {coin} at {date}")

        is_btc = coin == "BTC"
        if is_btc:
            btc_data    = calculate_all(d1d_w)
            btc_4h_data = calculate_all(d4h_w)
        else:
            df_btc_1d   = load_candles("BTC", "1d", limit=1000)
            df_btc_4h   = load_candles("BTC", "4h", limit=2000)
            btc_1d_w    = df_btc_1d[df_btc_1d.index < target_ts].iloc[-window:] if df_btc_1d is not None else None
            btc_4h_w    = df_btc_4h[df_btc_4h.index < target_ts].iloc[-window:] if df_btc_4h is not None else None
            btc_data    = calculate_all(btc_1d_w) if btc_1d_w is not None and len(btc_1d_w) >= 50 else None
            btc_4h_data = calculate_all(btc_4h_w) if btc_4h_w is not None and len(btc_4h_w) >= 50 else None

        d1d      = calculate_all(d1d_w)
        d4h      = calculate_all(d4h_w)
        d1h      = calculate_all(d1h_w)
        d1w      = calculate_all(d1w_w)
        btc_inst = assess_btc_stability(btc_data) if btc_data else assess_btc_stability(d1d)

        price      = d1d["price"]
        prev_close = float(d1d_w.iloc[-2]["close"]) if len(d1d_w) >= 2 else price

        market = {
            "price": price, "change24": (price - prev_close) / prev_close * 100 if prev_close > 0 else 0,
            "funding": 0.0, "oi": 0.0, "oi_change": 0.0, "long_ratio": 50.0, "short_ratio": 50.0,
            "fear_greed": {"value": 50, "label": "Neutral"},
        }
        oi_matrix   = {"primary_score": 5, "primary_label": "Neutral", "funding_score": 6, "funding_warning": "", "crowding_warning": ""}
        news_filter = {"clear": True, "blocked": False, "warning": False, "alerts": []}
        key_levels  = {
            "pdh": float(d1d_w.iloc[-2]["high"])  if len(d1d_w) >= 2 else 0,
            "pdl": float(d1d_w.iloc[-2]["low"])   if len(d1d_w) >= 2 else 0,
            "pdc": float(d1d_w.iloc[-2]["close"]) if len(d1d_w) >= 2 else 0,
            "pwh": float(d1w_w.iloc[-2]["high"])  if len(d1w_w) >= 2 else 0,
            "pwl": float(d1w_w.iloc[-2]["low"])   if len(d1w_w) >= 2 else 0,
        }
        session = {"name": "London/NY Overlap", "quality": "BEST", "score": 9, "tradeable": True, "desc": "Backtest neutral"}
        regime  = detect_regime(d1d, d4h)
        sweep   = detect_sweep(d1d_w, key_levels, d1d.get("atr", 0), d1d["swings"])
        disp    = detect_displacement(d4h_w, d4h.get("atr", 0))
        retest  = detect_retest(d4h_w, d4h, sweep, disp, d1h=d1h, d1d=d1d)

        wconf    = score_confluence(d1w, d1d, d4h, d1h, market, key_levels, session, btc_data, btc_inst, regime, sweep, disp, retest, oi_matrix, coin, btc_4h=btc_4h_data)
        no_trade = run_no_trade_engine(regime, d1d, d4h, market, session, sweep, disp, retest, btc_data, btc_inst, oi_matrix, news_filter, wconf["norm_score"], coin=coin, d1w=d1w, wconf=wconf)
        signal   = generate_signal(d1d, d4h, wconf, no_trade, market, key_levels, d1w=d1w, d1h=d1h)

        result = {
            "coin":      coin,
            "date":      date,
            "grade":     signal.get("grade"),
            "direction": signal.get("direction"),
            "score":     signal.get("score", 0),
            "entry":     signal.get("entry"),
            "sl":        signal.get("sl"),
            "stoploss":  signal.get("sl"),
            "tp1":       signal.get("tp1"),
            "signal_id": f"{coin}_{date}",
        }

        if r:
            r.setex(cache_key, 86400, json.dumps(make_serializable(result)))

        return JSONResponse(content=make_serializable(result))

    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))