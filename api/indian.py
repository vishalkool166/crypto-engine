import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from auth import is_authenticated

log    = logging.getLogger(__name__)
router = APIRouter()

IST = timezone(timedelta(hours=5, minutes=30))


def _auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


@router.get("/indian/status")
async def indian_status(request: Request):
    _auth(request)
    try:
        from engines.indian.data import (
            is_market_open, is_orb_ready,
            get_day_range_from_redis, get_ltp_from_redis,
            get_last_refresh_age, _is_rate_limited,
        )
        from engines.indian.scanner import get_orb_levels, get_today_signals
        from engines.indian.instruments import get_instruments
        from engines.indian.strategy import MIN_DAY_RANGE, MIN_ORB_SIZE, MAX_ORB_SIZE
        from engines.indian.tracker import get_open_signals_with_pnl
        from config import cfg

        now          = datetime.now(IST)
        market_open  = is_market_open()
        orb_ready    = is_orb_ready()
        instruments  = get_instruments()
        today_signals= get_today_signals()
        open_signals = get_open_signals_with_pnl()
        rate_limited = _is_rate_limited()
        refresh_age  = get_last_refresh_age()

        orb_data = {}
        for name in cfg.INDIAN_INSTRUMENTS:
            orb = get_orb_levels(name)
            if orb:
                orb_data[name] = orb

        day_ranges = {}
        ltps       = {}
        for name in cfg.INDIAN_INSTRUMENTS:
            inst = instruments.get(name)
            if inst:
                day_ranges[name] = get_day_range_from_redis(inst["token"])
                ltps[name]       = get_ltp_from_redis(inst["token"])

        return JSONResponse(content={
            "market_open":    market_open,
            "orb_ready":      orb_ready,
            "time_ist":       now.strftime("%I:%M %p IST"),
            "date":           now.strftime("%Y-%m-%d"),
            "instruments":    instruments,
            "orb_levels":     orb_data,
            "day_ranges":     day_ranges,
            "ltps":           ltps,
            "signals_today":  len(today_signals),
            "signals":        today_signals,
            "open_signals":   open_signals,
            "rate_limited":   rate_limited,
            "data_age_secs":  refresh_age,
            "min_day_range":  MIN_DAY_RANGE,
            "min_orb_size":   MIN_ORB_SIZE,
            "max_orb_size":   MAX_ORB_SIZE,
        })
    except Exception as e:
        log.error("indian_status error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/indian/orb")
async def indian_orb(request: Request):
    _auth(request)
    try:
        from engines.indian.scanner import get_orb_levels
        from config import cfg

        result = {}
        for name in cfg.INDIAN_INSTRUMENTS:
            orb = get_orb_levels(name)
            if orb:
                result[name] = orb

        return JSONResponse(content=result)
    except Exception as e:
        log.error("indian_orb error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/indian/signals")
async def indian_signals(request: Request, limit: int = 50):
    _auth(request)
    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            signals = db.query(SignalModel).filter(
                SignalModel.market == "indian"
            ).order_by(
                SignalModel.timestamp.desc()
            ).limit(limit).all()

        return JSONResponse(content=[{
            "id":         s.id,
            "timestamp":  s.timestamp.isoformat() if s.timestamp else None,
            "instrument": s.instrument or s.coin,
            "direction":  s.direction,
            "grade":      s.grade,
            "entry":      s.entry,
            "sl":         s.sl,
            "tp1":        s.tp1,
            "tp2":        s.tp2,
            "sl_pct":     s.sl_pct,
            "outcome":    s.outcome,
            "exit_price": s.exit_price,
            "pnl_pts":    s.pnl,
            "orb_high":   s.orb_high,
            "orb_low":    s.orb_low,
            "orb_size":   s.orb_size,
            "notes":      s.notes,
            "day_of_week":s.day_of_week,
        } for s in signals])

    except Exception as e:
        log.error("indian_signals error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/indian/signals/{signal_id}/journey")
async def indian_signal_journey(request: Request, signal_id: int):
    _auth(request)
    try:
        from engines.indian.tracker import get_signal_journey
        journey = get_signal_journey(signal_id)
        return JSONResponse(content={"signal_id": signal_id, "journey": journey})
    except Exception as e:
        log.error("indian_signal_journey error: %s", e)
        raise HTTPException(500, str(e))


@router.get("/indian/performance")
async def indian_performance(request: Request):
    _auth(request)
    try:
        from engines.indian.tracker import get_performance
        return JSONResponse(content=get_performance())
    except Exception as e:
        log.error("indian_performance error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/indian/orb/setup")
async def indian_orb_setup(request: Request):
    _auth(request)
    try:
        from engines.indian.scanner import setup_orb
        result = setup_orb()
        return JSONResponse(content={"success": True, "orb": result})
    except Exception as e:
        log.error("indian_orb_setup error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/indian/scan")
async def indian_scan_now(request: Request):
    _auth(request)
    try:
        from engines.indian.scanner import scan_all
        signals = await scan_all()
        return JSONResponse(content={
            "success": True,
            "signals": len(signals),
        })
    except Exception as e:
        log.error("indian_scan_now error: %s", e)
        raise HTTPException(500, str(e))


@router.post("/indian/refresh")
async def indian_refresh(request: Request):
    _auth(request)
    try:
        from engines.indian.data import refresh_indian_data, _is_rate_limited
        from engines.indian.instruments import get_instruments
        from config import cfg

        if _is_rate_limited():
            return JSONResponse(content={
                "success":      False,
                "rate_limited": True,
                "reason":       "AngelOne rate limited — try again in 2 minutes",
            })

        instruments = get_instruments()
        results     = {}

        for name in cfg.INDIAN_INSTRUMENTS:
            inst = instruments.get(name)
            if inst:
                results[name] = refresh_indian_data(inst["token"], name)

        return JSONResponse(content={"success": True, "results": results})
    except Exception as e:
        log.error("indian_refresh error: %s", e)
        raise HTTPException(500, str(e))