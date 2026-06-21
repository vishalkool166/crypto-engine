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
from api.formatters import (
    make_serializable,
    build_performance_data, build_radar_data,
    build_signal_queue, build_history_data, build_header_data
)
import runtime_state as rs

log     = logging.getLogger(__name__)
router  = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _auth(request: Request):
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


async def build_dashboard_payload() -> dict:
    stats = get_db_stats()

    db = SessionLocal()
    try:
        signals_raw = db.query(SignalModel).filter(
            SignalModel.outcome.notin_(["pending"]),
            SignalModel.outcome.isnot(None)
        ).order_by(SignalModel.timestamp.desc()).limit(10).all()

        signals_list = [{
            "id":        s.id,
            "coin":      s.coin,
            "direction": s.direction,
            "grade":     s.grade,
            "outcome":   s.outcome,
            "pnl":       s.pnl,
            "entry":     s.entry,
            "exit_price":s.exit_price,
            "sl":        s.sl,
            "tp1":       s.tp1,
            "tp2":       None,
            "risk_amt":  s.risk_amt,
            "position":  s.position,
            "leverage":  s.leverage,
            "regime":    s.regime,
            "session":   s.session,
            "score":     s.score,
            "timestamp": s.timestamp.isoformat() if s.timestamp else None,
        } for s in signals_raw]
    finally:
        db.close()

    perf_data    = build_performance_data(stats)
    history_data = build_history_data(signals_list)

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

    header_data   = build_header_data(stats)
    coin_universe = build_coin_universe()

    return make_serializable({
        "type":            "dashboard",
        "performance":     perf_data,
        "history":         history_data,
        "radar":           radar_data,
        "queue":           queue_data,
        "header":          header_data,
        "coin_universe":   coin_universe,
        "last_scan":       last_scan,
        "next_scan_epoch": get_next_scan_epoch(),
        "timestamp":       datetime.now(timezone.utc).isoformat()
    })


def build_coin_universe() -> list:
    try:
        with SessionLocal() as db:
            rows = db.query(CoinConfig).order_by(
                CoinConfig.enabled.desc(),
                CoinConfig.volume_24h.desc()
            ).all()

        result = []
        for r in rows:
            cached = cache.get_raw(f"signal_{r.coin}")
            grade  = cached.get("grade", "--")     if cached else "--"
            score  = cached.get("score", 0)        if cached else 0
            dir_   = cached.get("direction", "--") if cached else "--"
            market = cached.get("market", {})      if cached else {}

            from api.formatters import grade_color, pnl_color, fmt_price, fmt_pct
            change = market.get("change24", 0)

            result.append({
                "coin":        r.coin,
                "enabled":     r.enabled,
                "tier":        r.tier,
                "source":      r.source,
                "volume_24h":  r.volume_24h,
                "added_at":    r.added_at.isoformat() if r.added_at else None,
                "last_seen":   r.last_seen.isoformat() if r.last_seen else None,
                "grade":       grade,
                "grade_color": grade_color(grade),
                "score":       score,
                "direction":   dir_,
                "has_signal":  cached is not None,
                "price":       fmt_price(market.get("price", 0)),
                "change":      fmt_pct(change),
                "change_color":pnl_color(change),
                "funding":     round(market.get("funding", 0) * 100, 4) if market else 0,
            })
        return result
    except Exception as e:
        log.error(f"build_coin_universe error: {e}")
        return []


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
    request: Request,
    limit:   int = 50,
    grade:   str = None,
    coin:    str = None,
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
        import time

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
        import time

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
            rows = db.query(CoinConfig).filter(
                CoinConfig.enabled == True
            ).all()
            pairs = [f"{row.coin}/USDT:USDT" for row in rows]

        return JSONResponse(content={
            "pairs":          pairs,
            "refresh_period": 1800
        })
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
                    capital  = cfg.CAPITAL,
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
                        capital  = cfg.CAPITAL,
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

    return JSONResponse(content={
        "status":          "ok",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "trading_mode":    "live" if not cfg.PAPER_TRADING else "paper",
        "coins_count":     len(cfg.COINS),
        "grades":          cfg.MIN_GRADE_TO_TRADE,
        "redis_connected": redis_connected,
        "ml_status":       get_ml_status(),
        "sync_status":     await get_sync_status()
    })


@router.post("/sync/outcomes")
async def sync_outcomes(request: Request):
    _auth(request)
    try:
        from trade.sync import sync_freqtrade_outcomes
        result = await sync_freqtrade_outcomes()
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
                        "reason":  f"Cannot switch mode — {len(status)} open trade(s). Close all trades first."
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

        log.info(f"Freqtrade config updated: dry_run={mode != 'live'}")

    except Exception as e:
        log.error(f"Failed to update Freqtrade config: {e}")
        raise


async def _restart_freqtrade():
    try:
        import docker
        client    = docker.from_env()
        container = client.containers.get("freqtrade")
        container.restart()
        log.info("Freqtrade container restarted")
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
        return JSONResponse(content=make_serializable(build_coin_universe()))
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

        ip = request.client.host if request.client else ""
        audit("coin_toggle", "api", f"{coin} enabled:{enabled}", ip=ip)
        return JSONResponse(content={"success": True, "coin": coin, "enabled": enabled})
    except Exception as e:
        log.error(traceback.format_exc())
        raise HTTPException(500, str(e))


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
                db.add(CoinConfig(
                    coin    = coin,
                    enabled = True,
                    tier    = 1,
                    source  = "manual"
                ))
                db.commit()
                msg = f"{coin} added"

        cfg.COINS = []

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


@router.get("/ft/summary")
async def ft_summary(request: Request):
    _auth(request)
    try:
        from api.freqtrade import _ft_get
        status, profit, balance, daily, config = await asyncio.gather(
            _ft_get("/status"),
            _ft_get("/profit"),
            _ft_get("/balance"),
            _ft_get("/daily?timescale=7"),
            _ft_get("/show_config"),
            return_exceptions=True
        )

        bot_state = "unknown"
        if not isinstance(config, Exception) and config:
            bot_state = config.get("state", "unknown")

        return JSONResponse(content={
            "status":    status    if not isinstance(status,    Exception) else [],
            "profit":    profit    if not isinstance(profit,    Exception) else {},
            "balance":   balance   if not isinstance(balance,   Exception) else {},
            "daily":     daily     if not isinstance(daily,     Exception) else [],
            "bot_state": bot_state
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/ft/status")
async def ft_status(request: Request):
    _auth(request)
    try:
        from api.freqtrade import _ft_get
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
        from api.freqtrade import _ft_get
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
        from api.freqtrade import _ft_get
        data = await _ft_get("/balance")
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/ft/start")
async def ft_start(request: Request):
    _auth(request)
    try:
        from api.freqtrade import _ft_post
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
        from api.freqtrade import _ft_post
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
        from api.freqtrade import _ft_post
        data = await _ft_post("/forcesell", {"tradeid": str(tradeid)})
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))