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
from api.formatters import make_serializable
import runtime_state as rs
import httpx
import psutil
import time
import subprocess
import os

log     = logging.getLogger(__name__)
router  = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_boot_time = time.time()


def _auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


def _get_system_stats() -> dict:
    try:
        mem  = psutil.virtual_memory()
        cpu  = psutil.cpu_percent(interval=0.1)
        disk = psutil.disk_usage('/')

        uptime_secs = int(time.time() - psutil.boot_time())
        days        = uptime_secs // 86400
        hours       = (uptime_secs % 86400) // 3600
        mins        = (uptime_secs % 3600) // 60

        containers = []
        try:
            import docker
            client = docker.from_env()
            for c in client.containers.list():
                stats     = c.stats(stream=False)
                mem_usage = stats["memory_stats"].get("usage", 0)
                mem_limit = stats["memory_stats"].get("limit", 1)
                cpu_delta  = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                             stats["precpu_stats"]["cpu_usage"]["total_usage"]
                sys_delta  = stats["cpu_stats"].get("system_cpu_usage", 0) - \
                             stats["precpu_stats"].get("system_cpu_usage", 0)
                cpu_pct    = (cpu_delta / sys_delta * 100) if sys_delta > 0 else 0

                containers.append({
                    "name":    c.name,
                    "status":  c.status,
                    "mem_mb":  round(mem_usage / 1024 / 1024),
                    "mem_pct": round(mem_usage / mem_limit * 100, 1),
                    "cpu_pct": round(cpu_pct, 1),
                })
        except Exception:
            pass

        return {
            "ram_used_mb":   round(mem.used / 1024 / 1024),
            "ram_total_mb":  round(mem.total / 1024 / 1024),
            "ram_pct":       round(mem.percent, 1),
            "ram_available": round(mem.available / 1024 / 1024),
            "cpu_pct":       round(cpu, 1),
            "disk_used_gb":  round(disk.used / 1024 ** 3, 1),
            "disk_total_gb": round(disk.total / 1024 ** 3, 1),
            "disk_pct":      round(disk.percent, 1),
            "uptime_secs":   uptime_secs,
            "uptime_str":    f"{days}d {hours}h {mins}m",
            "containers":    containers,
        }
    except Exception as e:
        log.error(f"System stats error: {e}")
        return {}


async def build_dashboard_payload() -> dict:
    summary    = get_summary()
    perf       = get_performance()
    signals    = get_signals_data()
    history    = get_history(limit=10)
    universe   = get_universe()
    ticker     = get_ticker_bar()

    return make_serializable({
        "type":          "dashboard",
        "summary":       summary,
        "performance":   perf,
        "signals":       signals,
        "history":       history,
        "universe":      universe,
        "ticker":        ticker,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
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


@router.get("/dashboard/summary")
async def dashboard_summary(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(get_summary()))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/dashboard/performance")
async def dashboard_performance(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(get_performance()))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/dashboard/signals")
async def dashboard_signals(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(get_signals_data()))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/dashboard/history")
async def dashboard_history(request: Request, limit: int = 20):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(get_history(limit=limit)))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/dashboard/universe")
async def dashboard_universe(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(get_universe()))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/dashboard/ticker")
async def dashboard_ticker(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(get_ticker_bar()))
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
    db: Session = Depends(get_db)
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


@router.get("/signals/latest")
async def signals_latest(request: Request):
    _auth(request)
    try:
        from redis_client import get_redis
        import json

        r = get_redis()
        if not r:
            raise HTTPException(503, "Redis unavailable")

        best       = None
        best_score = 0

        for coin in cfg.COINS:
            key  = f"signal:{coin}USDT"
            data = r.get(key)
            if not data:
                continue
            try:
                sig = json.loads(data)
            except Exception:
                continue
            if time.time() > sig.get("valid_until", 0):
                continue
            if sig.get("grade") not in ["A+", "A"]:
                continue
            score = sig.get("score", 0)
            if score > best_score:
                best       = sig
                best_score = score

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

        active = []

        for coin in cfg.COINS:
            key  = f"signal:{coin}USDT"
            data = r.get(key)
            if not data:
                continue
            try:
                sig = json.loads(data)
            except Exception:
                continue
            if time.time() > sig.get("valid_until", 0):
                continue
            if sig.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
                continue
            active.append(sig)

        active.sort(key=lambda x: x.get("score", 0), reverse=True)
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
        "id":        row.id,
        "coin":      row.coin,
        "direction": row.direction,
        "grade":     row.grade,
        "entry":     row.entry,
        "sl":        row.sl,
        "tp1":       row.tp1,
        "score":     row.score,
    })


@router.get("/coins/active")
async def coins_active():
    try:
        from redis_client import get_redis
        import json

        r = get_redis()
        if r:
            data = r.get("pairs:active")
            if data:
                return JSONResponse(content=json.loads(data))

        with SessionLocal() as db:
            rows  = db.query(CoinConfig).filter(CoinConfig.enabled == True).all()
            pairs = [f"{row.coin}/USDT:USDT" for row in rows]

        return JSONResponse(content={"pairs": pairs, "refresh_period": 1800})
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
        loop   = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None, lambda: run_backtest(
                    coin     = coin,
                    capital  = 1000,
                    leverage = 10
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
    results = []
    loop    = asyncio.get_running_loop()

    for coin in cfg.COINS:
        try:
            r = await asyncio.wait_for(
                loop.run_in_executor(
                    None, lambda c=coin: run_backtest(
                        coin     = c,
                        capital  = 1000,
                        leverage = 10
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
    from ml.eligibility import get_ml_status
    from trade.sync import get_sync_status

    redis_connected = False
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            r.ping()
            redis_connected = True
    except Exception:
        pass

    loop   = asyncio.get_running_loop()
    system = await loop.run_in_executor(None, _get_system_stats)

    return JSONResponse(content={
        "status":          "ok",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "trading_mode":    "live" if not cfg.PAPER_TRADING else "paper",
        "coins_count":     len(cfg.COINS),
        "grades":          cfg.MIN_GRADE_TO_TRADE,
        "redis_connected": redis_connected,
        "ml_status":       get_ml_status(),
        "sync_status":     await get_sync_status(),
        "system":          system,
    })


@router.post("/sync/outcomes")
async def sync_outcomes(request: Request):
    _auth(request)
    try:
        from trade.sync import sync_freqtrade_outcomes
        result = await sync_freqtrade_outcomes()
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
        "b_grade_live": False
    })


@router.post("/mode/toggle")
async def mode_toggle(request: Request):
    _auth(request)
    try:
        body     = await request.json()
        totp     = body.get("totp_code", "")
        new_mode = body.get("mode", "")

        if new_mode not in ["live", "paper"]:
            raise HTTPException(400, "Invalid mode")

        from auth import verify_totp
        if not verify_totp(totp):
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid TOTP code"}
            )

        try:
            from api.freqtrade import _ft_get
            status = await _ft_get("/status")
            if status and isinstance(status, list) and len(status) > 0:
                return JSONResponse(
                    status_code = 400,
                    content     = {
                        "success": False,
                        "reason":  f"Cannot switch — {len(status)} open trade(s). Close all first."
                    }
                )
        except Exception as e:
            log.warning(f"Could not check open trades: {e}")

        if new_mode == "live":
            if not cfg.BINANCE_API_KEY or not cfg.BINANCE_SECRET:
                return JSONResponse(
                    status_code = 400,
                    content     = {"success": False, "reason": "Binance API keys not configured"}
                )

        from config import _ensure
        _ensure("TRADING_MODE", new_mode)
        cfg.TRADING_MODE  = new_mode
        cfg.PAPER_TRADING = new_mode != "live"

        _update_freqtrade_config(new_mode)

        try:
            await _restart_freqtrade()
        except Exception as e:
            log.warning(f"Freqtrade restart failed: {e}")

        ip = request.client.host if request.client else ""
        audit("mode_toggle", "dashboard", f"mode:{new_mode}", ip=ip)

        invalidate_all()

        return JSONResponse(content={
            "success": True,
            "mode":    new_mode,
            "grades":  cfg.MIN_GRADE_TO_TRADE,
            "message": f"Switched to {new_mode} mode. Freqtrade restarting."
        })

    except HTTPException:
        raise
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


def _update_freqtrade_config(mode: str):
    import json
    config_path = "freqtrade/user_data/config.json"
    try:
        with open(config_path, "r") as f:
            ft_config = json.load(f)

        if mode == "live":
            ft_config["dry_run"] = False
            ft_config.pop("dry_run_wallet", None)
        else:
            ft_config["dry_run"]        = True
            ft_config["dry_run_wallet"] = 1000

        with open(config_path, "w") as f:
            json.dump(ft_config, f, indent=2)

    except Exception as e:
        log.error(f"Failed to update Freqtrade config: {e}")
        raise


async def _restart_freqtrade():
    try:
        import docker
        client    = docker.from_env()
        container = client.containers.get("freqtrade")
        container.restart()
    except Exception as e:
        log.error(f"Freqtrade restart error: {e}")
        raise


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


@router.get("/coins")
async def get_coins(request: Request):
    _auth(request)
    try:
        return JSONResponse(content=make_serializable(get_universe()))
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


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
                return JSONResponse(
                    status_code = 404,
                    content     = {"success": False, "reason": f"{coin} not found"}
                )
            row.enabled = enabled
            db.commit()

        cfg.COINS = []
        from api.dashboard import _invalidate
        _invalidate("universe")

        ip = request.client.host if request.client else ""
        audit("coin_toggle", "api", f"{coin} enabled:{enabled}", ip=ip)
        return JSONResponse(content={"success": True, "coin": coin, "enabled": enabled})
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


async def _backfill_new_coin(coin: str):
    try:
        from backfill import run_backfill
        await run_backfill(coins=[coin])
    except Exception as e:
        log.error(f"Auto backfill failed for {coin}: {e}")


@router.post("/coins/add")
async def add_coin(request: Request):
    _auth(request)
    try:
        body = await request.json()
        coin = body.get("coin", "").upper().strip().replace("USDT", "").replace("/", "")

        if not coin:
            return JSONResponse(status_code=400, content={"success": False, "reason": "Coin name required"})

        if len(coin) > 10:
            return JSONResponse(status_code=400, content={"success": False, "reason": "Invalid coin name"})

        try:
            from data.fetcher import exchange
            markets = await exchange.load_markets(reload=True)
            symbol  = f"{coin}/USDT"
            symbol2 = f"{coin}/USDT:USDT"
            if symbol not in markets and symbol2 not in markets:
                return JSONResponse(
                    status_code = 400,
                    content     = {"success": False, "reason": f"{coin} not found on Binance Futures"}
                )
            market_data = markets.get(symbol) or markets.get(symbol2, {})
            if not market_data.get("active", True):
                return JSONResponse(
                    status_code = 400,
                    content     = {"success": False, "reason": f"{coin} is not active on Binance"}
                )
        except Exception as e:
            log.warning(f"Binance validation failed for {coin}: {e}")
            return JSONResponse(
                status_code = 500,
                content     = {"success": False, "reason": f"Could not validate {coin} — try again"}
            )

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

        asyncio.create_task(_backfill_new_coin(coin))

        if coin not in cfg._FALLBACK_COINS:
            cfg._FALLBACK_COINS.append(coin)

        ip = request.client.host if request.client else ""
        audit("coin_add", "api", msg, ip=ip)
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

        ip = request.client.host if request.client else ""
        audit("coin_delete", "api", f"deleted:{coin}", ip=ip)
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
        symbol  = f"{coin}/USDT"
        symbol2 = f"{coin}/USDT:USDT"
        if symbol not in markets and symbol2 not in markets:
            return JSONResponse(content={"valid": False, "reason": f"{coin} not found on Binance Futures"})
        market_data = markets.get(symbol) or markets.get(symbol2, {})
        if not market_data.get("active", True):
            return JSONResponse(content={"valid": False, "reason": f"{coin} is not active"})
        return JSONResponse(content={"valid": True, "coin": coin, "symbol": symbol})
    except Exception as e:
        log.error(f"Coin validate error: {e}")
        raise HTTPException(500, str(e))


@router.get("/candles/{coin}/{tf}")
async def get_candles(request: Request, coin: str, tf: str):
    _auth(request)
    coin = coin.upper()

    valid_tfs = ["15m", "1h", "4h", "1d"]
    if tf not in valid_tfs:
        raise HTTPException(400, f"Invalid timeframe. Use: {valid_tfs}")

    limits = {"15m": 200, "1h": 300, "4h": 500, "1d": 365}
    limit  = limits.get(tf, 300)

    try:
        from database import SessionLocal, Candle
        with SessionLocal() as db:
            candles = db.query(Candle).filter(
                Candle.coin      == coin,
                Candle.timeframe == tf
            ).order_by(Candle.timestamp.desc()).limit(limit).all()

        if not candles:
            return JSONResponse(content=[])

        candles = list(reversed(candles))

        result = [{
            "time":   c.timestamp // 1000,
            "open":   c.open,
            "high":   c.high,
            "low":    c.low,
            "close":  c.close,
            "volume": c.volume
        } for c in candles]

        return JSONResponse(content=result)

    except Exception as e:
        log.error(f"Candles endpoint error {coin} {tf}: {e}")
        raise HTTPException(500, str(e))


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

        if not date:
            raise HTTPException(400, "date parameter required (YYYY-MM-DD)")

        cache_key = f"backtest_signal:{coin}:{date}"
        from redis_client import get_redis
        import json
        r = get_redis()
        if r:
            cached = r.get(cache_key)
            if cached:
                return JSONResponse(content=json.loads(cached))

        target_ts = pd.Timestamp(date, tz="UTC")

        df_1d = load_candles(coin, "1d", limit=1000)
        df_4h = load_candles(coin, "4h", limit=2000)
        df_1h = load_candles(coin, "1h", limit=2000)
        df_1w = load_candles(coin, "1w", limit=500)

        if df_1d is None or df_4h is None or df_1h is None or df_1w is None:
            raise HTTPException(404, f"Insufficient data for {coin}")

        window = 200

        d1d_w = df_1d[df_1d.index < target_ts].iloc[-window:]
        d4h_w = df_4h[df_4h.index < target_ts].iloc[-window:]
        d1h_w = df_1h[df_1h.index < target_ts].iloc[-window:]
        d1w_w = df_1w[df_1w.index < target_ts].iloc[-100:]

        if len(d1d_w) < 50 or len(d4h_w) < 50 or len(d1h_w) < 50 or len(d1w_w) < 10:
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

        d1d = calculate_all(d1d_w)
        d4h = calculate_all(d4h_w)
        d1h = calculate_all(d1h_w)
        d1w = calculate_all(d1w_w)

        btc_inst = assess_btc_stability(btc_data) if btc_data else assess_btc_stability(d1d)

        price      = d1d["price"]
        prev_close = float(d1d_w.iloc[-2]["close"]) if len(d1d_w) >= 2 else price

        market = {
            "price":       price,
            "change24":    (price - prev_close) / prev_close * 100 if prev_close > 0 else 0,
            "funding":     0.0,
            "oi":          0.0,
            "oi_change":   0.0,
            "long_ratio":  50.0,
            "short_ratio": 50.0,
            "fear_greed":  {"value": 50, "label": "Neutral"}
        }

        oi_matrix = {
            "primary_score":    5,
            "primary_label":    "Neutral",
            "funding_score":    6,
            "funding_warning":  "",
            "crowding_warning": ""
        }

        news_filter = {"clear": True, "blocked": False, "warning": False, "alerts": []}

        key_levels = {
            "pdh": float(d1d_w.iloc[-2]["high"])  if len(d1d_w) >= 2 else 0,
            "pdl": float(d1d_w.iloc[-2]["low"])   if len(d1d_w) >= 2 else 0,
            "pdc": float(d1d_w.iloc[-2]["close"]) if len(d1d_w) >= 2 else 0,
            "pwh": float(d1w_w.iloc[-2]["high"])  if len(d1w_w) >= 2 else 0,
            "pwl": float(d1w_w.iloc[-2]["low"])   if len(d1w_w) >= 2 else 0,
        }

        session = {
            "name":      "London/NY Overlap",
            "quality":   "BEST",
            "score":     9,
            "tradeable": True,
            "desc":      "Backtest neutral"
        }

        regime = detect_regime(d1d, d4h)
        sweep  = detect_sweep(d1d_w, key_levels, d1d.get("atr", 0), d1d["swings"])
        disp   = detect_displacement(d4h_w, d4h.get("atr", 0))
        retest = detect_retest(d4h_w, d4h, sweep, disp, d1h=d1h, d1d=d1d)

        wconf = score_confluence(
            d1w, d1d, d4h, d1h,
            market, key_levels,
            session, btc_data,
            btc_inst, regime,
            sweep, disp,
            retest, oi_matrix,
            coin,
            btc_4h=btc_4h_data
        )

        no_trade = run_no_trade_engine(
            regime, d1d, d4h,
            market, session,
            sweep, disp,
            retest, btc_data,
            btc_inst, oi_matrix,
            news_filter,
            wconf["norm_score"],
            coin  = coin,
            d1w   = d1w,
            wconf = wconf
        )

        signal = generate_signal(
            d1d, d4h,
            wconf, no_trade,
            market, key_levels,
            d1w = d1w,
            d1h = d1h
        )

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


@router.get("/proxy/binance/aggTrades")
async def proxy_binance_agg_trades(request: Request, symbol: str, limit: int = 100):
    _auth(request)
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://fapi.binance.com/fapi/v1/aggTrades",
                params  = {"symbol": symbol.upper(), "limit": limit},
                timeout = 10.0
            )
            return JSONResponse(content=res.json())
    except httpx.TimeoutException:
        raise HTTPException(504, "Binance API timeout")
    except Exception as e:
        log.error(f"Binance proxy error: {e}")
        raise HTTPException(500, str(e))


@router.get("/proxy/binance/price")
async def proxy_binance_price(request: Request, symbol: str):
    _auth(request)
    try:
        from redis_client import get_redis
        import json

        r = get_redis()
        if r:
            data = r.get(f"ticker:{symbol.upper()}")
            if data:
                parsed = json.loads(data)
                return JSONResponse(content={"price": str(parsed.get("last", 0))})

        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://fapi.binance.com/fapi/v1/ticker/price",
                params  = {"symbol": symbol.upper()},
                timeout = 5.0
            )
            return JSONResponse(content=res.json())
    except Exception as e:
        log.error(f"Binance price proxy error: {e}")
        raise HTTPException(500, str(e))


@router.post("/system/docker-purge")
async def docker_purge(request: Request):
    _auth(request)
    try:
        body      = await request.json()
        totp_code = body.get("totp_code", "")

        from auth import verify_totp
        if not verify_totp(totp_code):
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid TOTP code"}
            )

        disk_before = psutil.disk_usage('/').used

        result = subprocess.run(
            ["docker", "system", "prune", "-f", "--volumes"],
            capture_output = True,
            text           = True,
            timeout        = 120,
            cwd            = "/home/ubuntu/crypto-engine"
        )

        disk_after = psutil.disk_usage('/').used
        freed_gb   = round((disk_before - disk_after) / 1024 ** 3, 2)
        freed_mb   = round((disk_before - disk_after) / 1024 ** 2, 0)

        ip = request.client.host if request.client else ""
        audit("docker_purge", "dashboard", f"freed:{freed_mb}MB", ip=ip)

        if result.returncode == 0:
            return JSONResponse(content={
                "success":  True,
                "output":   result.stdout,
                "freed_gb": freed_gb,
                "freed_mb": freed_mb,
                "message":  f"Docker purge complete. Freed {freed_mb}MB of disk space."
            })
        else:
            return JSONResponse(
                status_code = 500,
                content     = {
                    "success": False,
                    "reason":  result.stderr or "Docker purge failed"
                }
            )

    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Docker purge timed out")
    except Exception as e:
        log.error(f"Docker purge error: {e}")
        raise HTTPException(500, str(e))


@router.get("/system/disk")
async def system_disk(request: Request):
    _auth(request)
    try:
        disk = psutil.disk_usage('/')
        return JSONResponse(content={
            "used_gb":  round(disk.used  / 1024 ** 3, 1),
            "total_gb": round(disk.total / 1024 ** 3, 1),
            "free_gb":  round(disk.free  / 1024 ** 3, 1),
            "pct":      round(disk.percent, 1),
        })
    except Exception as e:
        raise HTTPException(500, str(e))