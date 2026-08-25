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
        from data.store import load_candles
        from engines.indicators import calculate_all
        from engines.regime.detector import detect as detect_regime
        from engines.trend.direction import detect as detect_trend
        from engines.reversion.timing import detect as detect_reversion
        from engines.ict.confirmation import confirm as confirm_ict
        from engines.risk.calculator import calculate as calculate_risk
        from engines.scoring.scorer import build_score, assign_grade, get_session
        from trade.ws import get_mark_price

        result = {
            "coin":      coin,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        df_4h  = load_candles(coin, "4h",  limit=200)
        df_1h  = load_candles(coin, "1h",  limit=300)
        df_15m = load_candles(coin, "15m", limit=200)

        result["candles"] = {
            "4h":  len(df_4h)  if df_4h  is not None else 0,
            "1h":  len(df_1h)  if df_1h  is not None else 0,
            "15m": len(df_15m) if df_15m is not None else 0,
        }

        if df_4h is None or len(df_4h) < 50:
            result["error"] = "Insufficient 4H candles"
            return JSONResponse(content=make_serializable(result))
        if df_1h is None or len(df_1h) < 50:
            result["error"] = "Insufficient 1H candles"
            return JSONResponse(content=make_serializable(result))
        if df_15m is None or len(df_15m) < 20:
            result["error"] = "Insufficient 15M candles"
            return JSONResponse(content=make_serializable(result))

        d4h  = calculate_all(df_4h,  timeframe="4h")
        d1h  = calculate_all(df_1h,  timeframe="1h")
        d15m = calculate_all(df_15m, timeframe="15m")

        atr_1h  = float(d1h.get("atr")  or df_1h["close"].iloc[-1]  * 0.01)
        atr_15m = float(d15m.get("atr") or df_15m["close"].iloc[-1] * 0.005)

        regime = detect_regime(d4h)
        result["regime"] = {
            "label":      regime.label,
            "adx":        regime.adx,
            "atr_pct":    regime.atr_pct,
            "size_mult":  regime.size_mult,
            "is_trending":regime.is_trending,
            "is_ranging": regime.is_ranging,
            "is_choppy":  regime.is_choppy,
            "is_volatile":regime.is_volatile,
        }

        trend = detect_trend(d4h, coin)
        result["trend"] = {
            "passed":      trend.passed,
            "direction":   trend.direction,
            "adx":         trend.adx,
            "alignment":   trend.alignment,
            "daily_bias":  trend.daily_bias,
            "weekly_bias": trend.weekly_bias,
            "btc_score":   trend.btc_score,
            "htf_score":   trend.htf_score,
            "reason":      trend.reason,
        }

        if not trend.passed:
            result["pipeline_stopped_at"] = "trend"
            result["live_price"]          = get_mark_price(coin) or d4h.get("price", 0)
            return JSONResponse(content=make_serializable(result))

        direction = trend.direction

        reversion = detect_reversion(d1h, df_1h, direction)
        result["reversion"] = {
            "window_open": reversion.window_open,
            "rsi":         reversion.rsi,
            "bb_touch":    reversion.bb_touch,
            "extreme":     reversion.extreme,
            "score":       reversion.score,
            "reason":      reversion.reason,
        }

        if not reversion.window_open:
            result["pipeline_stopped_at"] = "reversion"
            result["live_price"]          = get_mark_price(coin) or d4h.get("price", 0)
            return JSONResponse(content=make_serializable(result))

        ict = confirm_ict(
            df_4h     = df_4h,
            d4h       = d4h,
            df_1h     = df_1h,
            d1h       = d1h,
            df_15m    = df_15m,
            d15m      = d15m,
            direction = direction,
            atr_1h    = atr_1h,
            atr_15m   = atr_15m,
        )

        result["ict"] = {
            "confirmed":     ict.confirmed,
            "score":         ict.score,
            "sweep_score":   ict.sweep_score,
            "zone_score":    ict.zone_score,
            "trigger_score": ict.trigger_score,
            "entry_price":   ict.entry_price,
            "reason":        ict.reason,
            "sweep_label":   ict.sweep.label     if ict.sweep else "",
            "sweep_age":     ict.sweep.age_hours if ict.sweep else 0,
            "zone_type":     ict.zone.type       if ict.zone  else "",
        }

        if not ict.confirmed:
            result["pipeline_stopped_at"] = "ict"
            result["live_price"]          = get_mark_price(coin) or d4h.get("price", 0)
            return JSONResponse(content=make_serializable(result))

        entry = float(ict.entry_price) if ict.entry_price else float(d4h.get("price", 0))

        risk = calculate_risk(
            direction = direction,
            entry     = entry,
            sweep     = ict.sweep,
            zone      = ict.zone,
            ict       = ict.trigger,
            atr_15m   = atr_15m,
            d1h       = d1h,
            d4h       = d4h,
        )

        result["risk"] = {
            "valid":     risk.valid,
            "entry":     risk.entry,
            "sl":        risk.sl,
            "tp1":       risk.tp1,
            "tp2":       risk.tp2,
            "sl_pct":    risk.sl_pct,
            "rr1":       risk.rr1,
            "rr2":       risk.rr2,
            "tp1_label": risk.tp1_label,
            "tp2_label": risk.tp2_label,
            "sl_reason": risk.sl_reason,
            "reason":    risk.reason,
        }

        if not risk.valid:
            result["pipeline_stopped_at"] = "risk"
            result["live_price"]          = get_mark_price(coin) or d4h.get("price", 0)
            return JSONResponse(content=make_serializable(result))

        session = get_session()

        hs    = build_score(
            coin          = coin,
            direction     = direction,
            regime_result = regime,
            trend_result  = trend,
            reversion     = reversion,
            ict_result    = ict,
            session       = session,
        )
        pct   = hs.pct()
        grade = assign_grade(pct, regime.label)

        result["signal"] = {
            "confirmed":     True,
            "grade":         grade,
            "score_pct":     pct,
            "score_detail":  hs.to_dict(),
            "sweep_score":   ict.sweep_score,
            "zone_score":    ict.zone_score,
            "trigger_score": ict.trigger_score,
            "combined":      ict.score,
            "entry":         risk.entry,
            "sl":            risk.sl,
            "tp1":           risk.tp1,
            "tp2":           risk.tp2,
            "rr1":           risk.rr1,
            "regime":        regime.label,
            "session":       session,
        }

        result["pipeline_stopped_at"] = None
        result["state"]               = "signal_ready"
        result["live_price"]          = get_mark_price(coin) or entry

        cached = cache.get_raw(f"signal_{coin}")
        if cached:
            result["cache"] = {
                "grade":     cached.get("grade"),
                "score":     cached.get("score"),
                "direction": cached.get("direction"),
                "state":     cached.get("state"),
                "regime":    cached.get("regime"),
                "session":   cached.get("session"),
            }

        return JSONResponse(content=make_serializable(result))

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
    from alerts.scanner import get_engine_health
    from data.rejection_stats import get_top_rejections
    from chatbot_rag import get_rag_status
    from monitoring.langsmith_setup import get_langsmith_status

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
        "status":           "ok",
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "trading_mode":     "live" if not cfg.PAPER_TRADING else "paper",
        "coins_count":      len(cfg.COINS),
        "grades":           cfg.MIN_GRADE_TO_TRADE,
        "redis_connected":  redis_ok,
        "ml_status":        get_ml_status(),
        "sync_status":      await get_sync_status(),
        "engine_health":    get_engine_health(),
        "top_rejections":   get_top_rejections(3),
        "rag_status":       get_rag_status(),
        "langsmith_status": get_langsmith_status(),
        "system":           system,
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
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


@router.get("/engine/ml/validation")
async def ml_validation(request: Request):
    _auth(request)
    try:
        from ml.trainer import get_validation_report
        return JSONResponse(content=get_validation_report())
    except Exception as e:
        log.error("ml_validation: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/monthly-report")
async def monthly_report(request: Request, year: int = None, month: int = None):
    _auth(request)
    try:
        from reports.monthly_report import generate_monthly_report
        return JSONResponse(content=make_serializable(generate_monthly_report(year, month)))
    except Exception as e:
        log.error("monthly_report: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/monthly-report/history")
async def monthly_report_history(request: Request, months: int = 3):
    _auth(request)
    try:
        from reports.monthly_report import get_last_n_months
        return JSONResponse(content=make_serializable(get_last_n_months(months)))
    except Exception as e:
        log.error("monthly_report_history: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/filter-report")
async def filter_report(request: Request):
    _auth(request)
    try:
        from reports.filter_analysis import run_filter_analysis
        return JSONResponse(content=make_serializable(run_filter_analysis()))
    except Exception as e:
        log.error("filter_report: %s", e)
        raise HTTPException(500, str(e))


@router.post("/content/generate")
async def generate_content(request: Request):
    from saas.middleware import get_current_user
    from config import tier_meets_minimum, TIER_ELITE

    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Authentication required")
    if not tier_meets_minimum(user.get("tier", "free"), TIER_ELITE):
        raise HTTPException(403, {"code": "upgrade_required", "required_tier": "elite"})

    try:
        params    = dict(request.query_params)
        coin      = params.get("coin", "")
        post_type = params.get("type", "market")

        if not cfg.GROQ_API_KEY:
            raise HTTPException(503, "Groq not configured")

        from groq import AsyncGroq
        client = AsyncGroq(api_key=cfg.GROQ_API_KEY)

        if post_type == "signal" and coin:
            cached    = None
            narrative = ""
            try:
                cached = cache.get_raw(f"signal_{coin}")
            except Exception:
                pass
            if cached:
                narrative = cached.get("narrative", "") or cached.get("explanation", {}).get("thesis", "")

            prompt = f"""You are a sharp crypto analyst with dry wit.

Signal data:
Coin: {coin}USDT
{narrative[:500] if narrative else "Active setup detected"}

Write a tweet about this setup. Rules:
- Under 280 characters
- Sharp, witty, slightly sarcastic
- Factually grounded in the data
- No hashtags
- No emojis
- Sounds like a smart human trader
- Get to the point immediately
- Do not start with "Just" or "So"

Output only the tweet text. Nothing else."""

        else:
            market_context = []
            for c in cfg.COINS[:5]:
                cached = cache.get_raw(f"signal_{c}")
                if cached:
                    price  = cached.get("market", {}).get("price",    0)
                    change = cached.get("market", {}).get("change24", 0)
                    state  = cached.get("state", "idle")
                    if price:
                        market_context.append(f"{c}: ${price:.4f} ({change:+.2f}%) [{state}]")

            context_str = "\n".join(market_context) if market_context else "Market scanning"

            prompt = f"""You are a sharp crypto analyst with dry wit.

Current market snapshot:
{context_str}

Write a market commentary tweet. Rules:
- Under 280 characters
- Sharp, witty, slightly sarcastic
- Based on the actual data above
- No hashtags
- No emojis
- Sounds like a smart human trader
- Get to the point immediately
- Do not start with "Just" or "So"

Output only the tweet text. Nothing else."""

        response = await client.chat.completions.create(
            model       = "llama-3.3-70b-versatile",
            messages    = [{"role": "user", "content": prompt}],
            max_tokens  = 100,
            temperature = 0.8,
        )

        text = response.choices[0].message.content.strip().strip('"').strip("'")
        return JSONResponse(content={"text": text, "coin": coin, "type": post_type})

    except HTTPException:
        raise
    except Exception as e:
        log.error("Content generate error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/chat")
async def chat_endpoint(request: Request):
    try:
        from saas.middleware import get_current_user
        from config import tier_meets_minimum, TIER_ELITE

        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")
        if not tier_meets_minimum(user.get("tier", "free"), TIER_ELITE):
            raise HTTPException(403, {"code": "upgrade_required"})

        body    = await request.json()
        message = body.get("message", "").strip()

        if not message:
            raise HTTPException(400, "Message required")

        from chatbot_rag import chat_with_sources
        result = await chat_with_sources(message)
        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error("Chat endpoint error: %s", e)
        raise HTTPException(500, str(e))