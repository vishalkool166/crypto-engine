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
        from data.store       import load_candles
        from engines.indicators import calculate_all
        from engines.context  import check as context_check
        from engines.sweep    import detect as detect_sweep
        from engines.zone     import detect as detect_zone
        from engines.trigger  import detect as detect_trigger
        from engines.risk     import calculate as calculate_risk
        from engines.state    import get as get_coin_state
        from trade.ws         import get_mark_price
        from data.cache       import cache

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
        d15m_indicators = calculate_all(df_15m, timeframe="15m")

        atr_1h  = d1h.get("atr")  or float(df_1h["close"].iloc[-1])  * 0.01
        atr_15m = d15m_indicators.get("atr") or float(df_15m["close"].iloc[-1]) * 0.005

        result["indicators"] = {
            "price":   d4h.get("price",  0),
            "ema20":   d4h.get("ema20",  0),
            "ema50":   d4h.get("ema50",  0),
            "ema200":  d4h.get("ema200", 0),
            "atr_4h":  d4h.get("atr",   0),
            "atr_1h":  atr_1h,
            "atr_15m": atr_15m,
            "adx":     d4h.get("adx",   0),
            "rsi":     d4h.get("rsi",   0),
            "trend":   d4h.get("trend", {}).get("label", "Unknown"),
            "slope20": d4h.get("slope20", 0),
            "slope50": d4h.get("slope50", 0),
        }

        ctx = context_check(d4h, coin)
        result["context"] = {
            "pass":          ctx["pass"],
            "direction":     ctx.get("direction", "NEUTRAL"),
            "reason":        ctx.get("reason", ""),
            "btc_score":     ctx.get("btc_score", 0),
            "htf_score":     ctx.get("htf_score", 0),
            "context_score": ctx.get("context_score", 0),
            "trace":         ctx.get("trace", {}),
        }

        if not ctx["pass"]:
            result["pipeline_stopped_at"] = "context"
            result["state"]      = get_coin_state(coin)["status"]
            result["live_price"] = get_mark_price(coin) or d4h.get("price", 0)
            return JSONResponse(content=make_serializable(result))

        direction = ctx["direction"]

        sweep_result = detect_sweep(df_1h, d1h, direction)
        result["sweep"] = {
            "detected":   sweep_result["detected"],
            "score":      sweep_result.get("score", 0),
            "age_hours":  (sweep_result.get("sweep") or {}).get("age_hours", 0),
            "label":      (sweep_result.get("sweep") or {}).get("level_label", sweep_result.get("label", "--")),
            "intensity":  (sweep_result.get("sweep") or {}).get("intensity", 0),
            "wick_atr":   (sweep_result.get("sweep") or {}).get("wick_atr", 0),
            "vol_ratio":  (sweep_result.get("sweep") or {}).get("vol_ratio", 0),
            "confirmed":  sweep_result.get("confirmed", False),
            "gate_pass":  sweep_result.get("score", 0) >= cfg.SCALP_ENGINE["sweep_min_score"],
            "gate_min":   cfg.SCALP_ENGINE["sweep_min_score"],
        }

        if not sweep_result["detected"] or not result["sweep"]["gate_pass"]:
            result["pipeline_stopped_at"] = "sweep"
            result["state"]      = get_coin_state(coin)["status"]
            result["live_price"] = get_mark_price(coin) or d4h.get("price", 0)
            return JSONResponse(content=make_serializable(result))

        zone_result = detect_zone(d4h, df_4h, direction, atr_1h)
        zone_data   = zone_result.get("zone") or {}
        result["zone"] = {
            "detected":     zone_result["detected"],
            "score":        zone_result.get("score", 0),
            "type":         zone_data.get("type", "--"),
            "top":          zone_data.get("top", 0),
            "bottom":       zone_data.get("bottom", 0),
            "mid":          zone_data.get("mid", 0),
            "distance_pct": zone_data.get("distance_pct", 0),
            "touch_count":  zone_data.get("touch_count", 0),
            "strength":     zone_data.get("strength", 0),
            "origin_desc":  zone_data.get("origin_desc", ""),
            "gate_pass":    zone_result.get("score", 0) >= cfg.SCALP_ENGINE["zone_min_score"],
            "gate_min":     cfg.SCALP_ENGINE["zone_min_score"],
        }

        if not zone_result["detected"] or not result["zone"]["gate_pass"]:
            result["pipeline_stopped_at"] = "zone"
            result["state"]      = get_coin_state(coin)["status"]
            result["live_price"] = get_mark_price(coin) or d4h.get("price", 0)
            return JSONResponse(content=make_serializable(result))

        price   = d4h.get("price", 0)
        atr_15m = d4h.get("atr", price * 0.005) * 0.3

        trigger_result = detect_trigger(
            df_15m    = df_15m,
            zone      = zone_data,
            direction = direction,
            atr_15m   = atr_15m,
        )
        result["trigger"] = {
            "confirmed":   trigger_result["confirmed"],
            "pattern":     trigger_result.get("pattern"),
            "score":       trigger_result.get("score", 0),
            "reason":      trigger_result.get("reason", ""),
            "entry_price": trigger_result.get("entry_price"),
            "vol_mult":    trigger_result.get("vol_mult", 0),
            "gate_pass":   trigger_result["confirmed"],
            "gate_min":    cfg.SCALP_ENGINE["trigger_min_score"],
        }

        if not trigger_result["confirmed"]:
            result["pipeline_stopped_at"] = "trigger"
            result["state"]      = get_coin_state(coin)["status"]
            result["live_price"] = get_mark_price(coin) or d4h.get("price", 0)
            sweep_s  = sweep_result.get("score", 0)
            zone_s   = zone_result.get("score",  0)
            combined = round(sweep_s * 0.40 + zone_s * 0.35, 3)
            result["partial_score"] = combined
            return JSONResponse(content=make_serializable(result))

        entry = trigger_result.get("entry_price") or d4h.get("price", 0)

        risk_result = calculate_risk(
            direction = direction,
            entry     = entry,
            sweep     = (sweep_result.get("sweep") or {}),
            zone      = zone_data,
            trigger   = trigger_result,
            atr_15m   = atr_15m,
            d1h       = d1h,
            d4h       = d4h,
        )
        result["risk"] = {
            "valid":      risk_result["valid"],
            "reason":     risk_result.get("reason", ""),
            "sl":         risk_result.get("sl"),
            "tp1":        risk_result.get("tp1"),
            "tp2":        risk_result.get("tp2"),
            "sl_pct":     risk_result.get("sl_pct"),
            "sl_dist":    risk_result.get("sl_dist"),
            "rr1":        risk_result.get("rr1"),
            "rr2":        risk_result.get("rr2"),
            "tp1_label":  risk_result.get("tp1_label"),
            "tp2_label":  risk_result.get("tp2_label"),
            "sl_reason":  risk_result.get("sl_reason"),
        }

        if not risk_result["valid"]:
            result["pipeline_stopped_at"] = "risk"
            result["state"]      = get_coin_state(coin)["status"]
            result["live_price"] = get_mark_price(coin) or d4h.get("price", 0)
            return JSONResponse(content=make_serializable(result))

        from engines.scorer import SignalScore, assign_grade, score_session, score_ml, SCORE_WEIGHTS
        from engines.scorer import score_btc_context, score_htf_alignment

        sig_score = SignalScore()
        sig_score.coin      = coin
        sig_score.direction = direction

        btc_score_val = ctx.get("btc_score", 0)
        htf_score_val = ctx.get("htf_score", 0)

        sig_score.add("btc_context",   btc_score_val, SCORE_WEIGHTS["btc_context"]["max"],   True, ctx.get("trace", {}).get("btc", ""))
        sig_score.add("htf_alignment", htf_score_val, SCORE_WEIGHTS["htf_alignment"]["max"], True, ctx.get("trace", {}).get("htf", ""))
        sig_score.add("sweep",   sweep_result["score"]   * SCORE_WEIGHTS["sweep"]["max"],   SCORE_WEIGHTS["sweep"]["max"],   True, "")
        sig_score.add("zone",    zone_result["score"]    * SCORE_WEIGHTS["zone"]["max"],    SCORE_WEIGHTS["zone"]["max"],    True, "")
        sig_score.add("trigger", trigger_result["score"] * SCORE_WEIGHTS["trigger"]["max"], SCORE_WEIGHTS["trigger"]["max"], True, "")

        from datetime import datetime as _dt, timezone as _tz
        _hour = _dt.now(_tz.utc).hour
        if 8  <= _hour < 13:  _session = "London"
        elif 13 <= _hour < 17: _session = "London/NY Overlap"
        elif 17 <= _hour < 21: _session = "New York"
        elif 0  <= _hour < 8:  _session = "Asia"
        else:                   _session = "Off Hours"

        session_score, session_reason = score_session(_session)
        sig_score.add("session", session_score, SCORE_WEIGHTS["session"]["max"], True, session_reason)

        from engines.signal import _get_total_trades, _get_ml_probability
        total_trades   = _get_total_trades()
        ml_probability = _get_ml_probability({
            "coin":          coin,
            "direction":     direction,
            "sweep_score":   sweep_result["score"],
            "zone_score":    zone_result["score"],
            "trigger_score": trigger_result["score"],
            "grade":         "A",
            "score":         sig_score.pct(),
            "funding":       0,
        })
        ml_score, ml_reason = score_ml(ml_probability, total_trades)
        sig_score.add("ml", ml_score, SCORE_WEIGHTS["ml"]["max"], True, ml_reason)

        sig_score.total = round(sig_score.total + ctx.get("context_score", 0), 3)

        from engines.signal import _get_regime
        regime = _get_regime(d4h)
        pct    = sig_score.pct()
        grade  = assign_grade(pct, regime)

        result["signal"] = {
            "confirmed":     True,
            "grade":         grade,
            "score_pct":     pct,
            "score_detail":  sig_score.to_dict(),
            "combined":      round(sweep_result["score"] * 0.40 + zone_result["score"] * 0.35 + trigger_result["score"] * 0.25, 3),
            "sweep_score":   sweep_result["score"],
            "zone_score":    zone_result["score"],
            "trigger_score": trigger_result["score"],
            "entry":         entry,
            "sl":            risk_result["sl"],
            "tp1":           risk_result["tp1"],
            "tp2":           risk_result.get("tp2"),
            "sl_pct":        risk_result["sl_pct"],
            "rr1":           risk_result["rr1"],
            "rr2":           risk_result.get("rr2"),
            "ml_probability":ml_probability,
            "regime":        regime,
            "session":       _session,
        }

        result["pipeline_stopped_at"] = None
        result["state"]      = "signal_ready"
        result["live_price"] = get_mark_price(coin) or entry

        cached = cache.get_raw(f"signal_{coin}")
        if cached:
            result["cache"] = {
                "grade":     cached.get("grade"),
                "score":     cached.get("score"),
                "direction": cached.get("direction"),
                "state":     cached.get("state"),
                "regime":    cached.get("regime"),
                "session":   cached.get("session"),
                "trace":     cached.get("trace"),
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


@router.get("/backtest-signal/{coin}")
async def backtest_signal(request: Request, coin: str, date: str = None):
    _auth(request)
    coin = coin.upper()
    try:
        from data.store import load_candles
        from engines.indicators import calculate_all
        from engines.context import check as context_check
        from engines.sweep import detect as detect_sweep
        from engines.zone import detect as detect_zone
        from engines.risk import calculate as calculate_risk
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

        df_4h = load_candles(coin, "4h", limit=2000)
        df_1h = load_candles(coin, "1h", limit=2000)

        if df_4h is None or df_1h is None:
            raise HTTPException(404, f"Insufficient data for {coin}")

        d4h_w = df_4h[df_4h.index < target_ts].iloc[-window:]
        d1h_w = df_1h[df_1h.index < target_ts].iloc[-window:]

        if len(d4h_w) < 50 or len(d1h_w) < 50:
            raise HTTPException(404, f"Not enough historical data for {coin} at {date}")

        d4h    = calculate_all(d4h_w, timeframe="4h")
        d1h    = calculate_all(d1h_w, timeframe="1h")
        atr_1h = d1h.get("atr") or float(d1h_w["close"].iloc[-1]) * 0.01

        ctx = context_check(d4h, coin)
        if not ctx["pass"]:
            result = {
                "coin": coin, "date": date, "grade": "F",
                "direction": "NO_DIRECTION", "score": 0,
                "entry": None, "sl": None, "stoploss": None, "tp1": None,
                "signal_id": f"{coin}_{date}", "reason": ctx["reason"],
            }
            return JSONResponse(content=make_serializable(result))

        direction    = ctx["direction"]
        sweep_result = detect_sweep(d1h_w, d1h, direction)

        if not sweep_result["detected"]:
            result = {
                "coin": coin, "date": date, "grade": "F",
                "direction": direction, "score": 0,
                "entry": None, "sl": None, "stoploss": None, "tp1": None,
                "signal_id": f"{coin}_{date}", "reason": "no_sweep",
            }
            return JSONResponse(content=make_serializable(result))

        zone_result = detect_zone(d4h, d4h_w, direction, atr_1h)

        if not zone_result["detected"]:
            result = {
                "coin": coin, "date": date, "grade": "F",
                "direction": direction, "score": 0,
                "entry": None, "sl": None, "stoploss": None, "tp1": None,
                "signal_id": f"{coin}_{date}", "reason": "no_zone",
            }
            return JSONResponse(content=make_serializable(result))

        price   = d4h.get("price", 0)
        atr_15m = d4h.get("atr", price * 0.005) * 0.3

        risk_result = calculate_risk(
            direction = direction,
            entry     = price,
            sweep     = sweep_result["sweep"],
            zone      = zone_result["zone"],
            trigger   = {
                "candle_low":  float(d4h_w.iloc[-1]["low"]),
                "candle_high": float(d4h_w.iloc[-1]["high"]),
            },
            atr_15m   = atr_15m,
            d1h       = d1h,
            d4h       = d4h,
        )

        if not risk_result["valid"]:
            result = {
                "coin": coin, "date": date, "grade": "F",
                "direction": direction, "score": 0,
                "entry": None, "sl": None, "stoploss": None, "tp1": None,
                "signal_id": f"{coin}_{date}", "reason": risk_result["reason"],
            }
            return JSONResponse(content=make_serializable(result))

        from engines.scorer import assign_grade
        from engines.signal import _get_regime
        combined = round(sweep_result["score"] * 0.40 + zone_result["score"] * 0.35 + 0.7 * 0.25, 3)
        regime   = _get_regime(d4h)
        pct      = min(combined * 100, 100)
        grade    = assign_grade(pct, regime)

        result = {
            "coin":      coin,
            "date":      date,
            "grade":     grade,
            "direction": direction,
            "score":     combined,
            "entry":     price,
            "sl":        risk_result["sl"],
            "stoploss":  risk_result["sl"],
            "tp1":       risk_result["tp1"],
            "tp2":       risk_result["tp2"],
            "rr1":       risk_result["rr1"],
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