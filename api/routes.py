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
from alerts.scanner import scan_all_coins, get_db_stats
from data.cache import cache
from data.fetcher import get_fear_greed, get_news_filter
from backtest.engine import run_backtest
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
async def dashboard(request: Request):
    _auth(request)
    return await build_dashboard_payload()

@router.get("/dashboard/summary")
async def dashboard_summary(request: Request):
    _auth(request)
    return make_serializable(get_summary())

@router.get("/dashboard/performance")
async def dashboard_performance(request: Request):
    _auth(request)
    return make_serializable(get_performance())

@router.get("/dashboard/signals")
async def dashboard_signals(request: Request):
    _auth(request)
    return make_serializable(get_signals_data())

@router.get("/dashboard/history")
async def dashboard_history(request: Request, limit: int = 20):
    _auth(request)
    return make_serializable(get_history(min(max(limit,1),100)))

@router.get("/dashboard/universe")
async def dashboard_universe(request: Request):
    _auth(request)
    return make_serializable(get_universe())

@router.get("/dashboard/ticker")
async def dashboard_ticker(request: Request):
    _auth(request)
    return JSONResponse(content=make_serializable(get_ticker_bar()))


@router.get("/dashboard/coin/{coin}")
async def dashboard_coin_detail(request: Request, coin: str):
    from access.security import require_admin_access
    require_admin_access(request)
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
        bounded_limit = min(max(limit, 1), 100)
        records = [{
            "id":          item.id,
            "timestamp":   item.timestamp.isoformat() if item.timestamp else None,
            "coin":        item.coin,
            "direction":   item.direction,
            "grade":       item.grade,
            "score":       item.score,
            "signal_type": item.signal_type,
            "entry":       item.entry,
            "sl":          item.sl,
            "tp1":         item.tp1,
            "risk_amt":    item.risk_amt,
            "outcome":     item.outcome,
            "exit_price":  item.exit_price,
            "pnl":         item.pnl,
            "market":      item.market,
        } for item in q.limit(bounded_limit).all()]
        return JSONResponse(content=make_serializable(records))
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
        return JSONResponse(content=make_serializable(best))
    except HTTPException:
        raise
    except Exception as e:
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
        return JSONResponse(content=make_serializable(active[:100]))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/signal/{signal_id}")
async def get_signal_by_id(request: Request, signal_id: int, db: Session = Depends(get_db)):
    _auth(request)
    row = db.query(SignalModel).filter(SignalModel.id == signal_id).first()
    if not row: raise HTTPException(404, "Signal not found")
    return JSONResponse(content=make_serializable({c.name:getattr(row,c.name) for c in row.__table__.columns}))


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
        return JSONResponse(content=make_serializable(cached.get("market", {})))
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


_backtest_lock: dict = {}






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




@router.post("/sync/outcomes")
async def sync_outcomes(request: Request):
    from access.security import require_admin_access
    require_admin_access(request)
    try:
        from trade.sync import sync_trade_outcomes
        result = await sync_trade_outcomes()
        invalidate_all()
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/mode/status")
async def mode_status(request: Request):
    _auth(request)
    return JSONResponse(content={
        "mode":   "live" if not cfg.PAPER_TRADING else "paper",
        "paper":  cfg.PAPER_TRADING,
        "grades": cfg.MIN_GRADE_TO_TRADE,
    })




@router.get("/audit/log")
async def audit_log(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    from access.security import require_admin_access
    require_admin_access(request)
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
    from access.security import require_admin_access
    require_admin_access(request)
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
        raise HTTPException(500, str(e))


async def _backfill_coin(coin: str) -> None:
    try:
        from backfill import run_backfill
        await run_backfill(coins=[coin])
    except Exception as e:
        log.error("Auto backfill failed for %s: %s", coin, e)


@router.post("/coins/add")
async def add_coin(request: Request):
    from access.security import require_admin_access
    require_admin_access(request)
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
            return JSONResponse(status_code=500, content={"success": False, "reason": f"Could not validate {coin}"})
        with SessionLocal() as db:
            existing = db.query(CoinConfig).filter(CoinConfig.coin == coin).first()
            if existing:
                existing.enabled = True
                db.commit()
                msg = f"{coin} re-enabled"
            else:
                db.add(CoinConfig(coin=coin, enabled=True, tier=1, source="manual", market="crypto"))
                db.commit()
                msg = f"{coin} added"
        cfg.COINS = []
        from api.dashboard import _invalidate
        _invalidate("universe")
        asyncio.create_task(_backfill_coin(coin))
        audit("coin_add", "api", msg, ip=request.client.host if request.client else "")
        return JSONResponse(content={"success": True, "coin": coin, "message": msg})
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/coins/{coin}")
async def remove_coin(request: Request, coin: str):
    from access.security import require_admin_access
    require_admin_access(request)
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
        audit("coin_delete", "api", f"deleted:{coin}", ip=request.client.host if request.client else "")
        return JSONResponse(content={"success": True, "coin": coin})
    except Exception as e:
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
        raise HTTPException(500, str(e))


@router.get("/candles/{coin}/{tf}")
async def get_candles(request: Request, coin: str, tf: str):
    _auth(request)
    coin = coin.upper()
    if tf not in ["15m", "1h", "4h", "1d"]:
        raise HTTPException(400, "Invalid timeframe. Use: 15m, 1h, 4h, 1d")
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




@router.get("/system/telemetry")
async def system_telemetry(request: Request):
    """Authenticated host/container telemetry, no AWS API or extra credentials."""
    from access.security import require_admin_access
    require_admin_access(request)
    from alerts.scanner import get_scan_stats
    from ops.host_telemetry import aws_environment, docker_containers
    host = _system_stats()
    # Existing psutil/Docker SDK integration is optional. The read-only
    # Docker Engine API fallback does not add a pip dependency.
    if not host.get('containers'):
        host['containers'] = docker_containers()
    return JSONResponse(content=make_serializable({
        'host': host,
        'aws': aws_environment(),
        'scans': get_scan_stats(),
        'note':'Container and EC2 metadata appear only when runtime permissions allow; no secrets are read.'
    }))


@router.get("/system/disk")
async def system_disk(request: Request):
    from access.security import require_admin_access
    require_admin_access(request)
    disk = psutil.disk_usage('/')
    return JSONResponse(content={
        "used_gb":  round(disk.used  / 1024 ** 3, 1),
        "total_gb": round(disk.total / 1024 ** 3, 1),
        "free_gb":  round(disk.free  / 1024 ** 3, 1),
        "pct":      round(disk.percent, 1),
    })


@router.get("/coins/states")
async def coins_states(request: Request):
    _auth(request)
    try:
        from engines.state import get_all_states
        all_states = get_all_states()
        result     = []
        for coin, s in all_states.items():
            setup = s.get("setup") or {}
            result.append({
                "coin":      coin,
                "state":     s["status"],
                "direction": setup.get("direction", "--"),
                "setup":     setup,
            })
        result.sort(key=lambda x: (
            ["in_trade", "watching", "cooldown", "idle"]
            .index(x["state"]) if x["state"] in
            ["in_trade", "watching", "cooldown", "idle"]
            else 99
        ))
        return JSONResponse(content=make_serializable(result))
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/trades/{trade_id}/journey")
async def trade_journey(request: Request, trade_id: int):
    from access.security import require_admin_access
    require_admin_access(request)
    try:
        from trade.monitor import get_trade_journey
        journey = get_trade_journey(trade_id)
        return JSONResponse(content={"trade_id": trade_id, "journey": journey})
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/engine/monthly-report")
async def monthly_report(request: Request, year: int = None, month: int = None):
    from access.security import require_admin_access
    require_admin_access(request)
    try:
        from reports.monthly_report import generate_monthly_report
        return JSONResponse(content=make_serializable(generate_monthly_report(year, month)))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/engine/monthly-report/history")
async def monthly_report_history(request: Request, months: int = 3):
    from access.security import require_admin_access
    require_admin_access(request)
    try:
        from reports.monthly_report import get_last_n_months
        return JSONResponse(content=make_serializable(get_last_n_months(months)))
    except Exception as e:
        raise HTTPException(500, str(e))


