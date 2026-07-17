import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from auth import is_authenticated

log = logging.getLogger(__name__)
router = APIRouter()


def _auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(401, "Unauthorized")


@router.get("/engine/health")
async def engine_health(request: Request):
    _auth(request)
    try:
        from alerts.scanner import get_engine_health, get_scan_stats
        health = get_engine_health()
        stats  = get_scan_stats()
        return JSONResponse(content={
            **health,
            "scan_stats": stats,
        })
    except Exception as e:
        log.error("engine_health: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/rejections")
async def engine_rejections(request: Request):
    _auth(request)
    try:
        from data.rejection_stats import (
            get_total_stats,
            get_daily_stats,
            get_weekly_stats,
            get_top_rejections,
        )
        return JSONResponse(content={
            "total":   get_total_stats(),
            "daily":   get_daily_stats(days=7),
            "weekly":  get_weekly_stats(),
            "top":     get_top_rejections(5),
        })
    except Exception as e:
        log.error("engine_rejections: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/rejections/coin/{coin}")
async def engine_rejections_coin(request: Request, coin: str):
    _auth(request)
    try:
        from data.rejection_stats import get_coin_stats
        return JSONResponse(content=get_coin_stats(coin.upper()))
    except Exception as e:
        log.error("engine_rejections_coin: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/traces")
async def engine_traces(request: Request, limit: int = 50):
    _auth(request)
    try:
        from engines.decision_trace import get_recent_traces, get_rejection_summary
        traces  = get_recent_traces(limit=limit)
        summary = get_rejection_summary(traces)
        return JSONResponse(content={
            "traces":  traces,
            "summary": summary,
            "count":   len(traces),
        })
    except Exception as e:
        log.error("engine_traces: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/traces/{coin}")
async def engine_traces_coin(request: Request, coin: str):
    _auth(request)
    try:
        from engines.decision_trace import get_traces, get_latest_trace
        traces = get_traces(coin.upper())
        latest = get_latest_trace(coin.upper())
        return JSONResponse(content={
            "coin":   coin.upper(),
            "latest": latest,
            "traces": traces,
            "count":  len(traces),
        })
    except Exception as e:
        log.error("engine_traces_coin: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/relative-strength")
async def engine_relative_strength(request: Request):
    _auth(request)
    try:
        from engines.relative_strength import get_rs_summary
        from config import cfg
        summary = get_rs_summary(cfg.COINS)
        return JSONResponse(content=summary)
    except Exception as e:
        log.error("engine_relative_strength: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/relative-strength/{coin}")
async def engine_relative_strength_coin(request: Request, coin: str):
    _auth(request)
    try:
        from engines.relative_strength import rank_coins
        from config import cfg
        ranked = rank_coins(cfg.COINS)
        for r in ranked:
            if r["coin"] == coin.upper():
                return JSONResponse(content=r)
        raise HTTPException(404, f"{coin} not found in ranking")
    except HTTPException:
        raise
    except Exception as e:
        log.error("engine_relative_strength_coin: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/score/{coin}")
async def engine_score_coin(request: Request, coin: str):
    _auth(request)
    try:
        from data.cache import cache
        from engines.decision_trace import get_latest_trace
        cached = cache.get_raw(f"signal_{coin.upper()}")
        trace  = get_latest_trace(coin.upper())
        if not cached and not trace:
            raise HTTPException(404, f"No data for {coin} — run scan first")
        return JSONResponse(content={
            "coin":         coin.upper(),
            "cached_signal":cached,
            "latest_trace": trace,
        })
    except HTTPException:
        raise
    except Exception as e:
        log.error("engine_score_coin: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/filter-analysis")
async def engine_filter_analysis(request: Request):
    _auth(request)
    try:
        from data.rejection_stats import get_total_stats, get_daily_stats
        from engines.decision_trace import get_recent_traces, get_rejection_summary

        total_stats = get_total_stats()
        daily_stats = get_daily_stats(days=30)
        traces      = get_recent_traces(limit=200)
        trace_summary = get_rejection_summary(traces)

        by_reason = total_stats.get("by_reason", {})
        analysis  = []

        for reason, data in by_reason.items():
            analysis.append({
                "filter":      reason,
                "total_count": data["count"],
                "pct_of_scans":data["pct"],
                "impact":      "high" if data["pct"] > 30 else "medium" if data["pct"] > 10 else "low",
            })

        analysis.sort(key=lambda x: x["total_count"], reverse=True)

        return JSONResponse(content={
            "total_scans":    total_stats.get("total_scans", 0),
            "total_signals":  total_stats.get("total_signals", 0),
            "signal_rate":    total_stats.get("signal_rate", 0),
            "filter_analysis":analysis,
            "trace_summary":  trace_summary,
            "daily_trend":    daily_stats,
        })
    except Exception as e:
        log.error("engine_filter_analysis: %s", e)
        raise HTTPException(500, str(e))


@router.post("/engine/rejections/reset")
async def engine_rejections_reset(request: Request):
    _auth(request)
    try:
        from auth import verify_totp
        body = await request.json()
        if not verify_totp(body.get("totp_code", "")):
            return JSONResponse(status_code=401, content={"success": False, "reason": "Invalid TOTP"})
        from data.rejection_stats import reset_stats
        reset_stats()
        return JSONResponse(content={"success": True})
    except Exception as e:
        log.error("engine_rejections_reset: %s", e)
        raise HTTPException(500, str(e))


@router.get("/engine/confidence/{coin}")
async def engine_confidence(request: Request, coin: str):
    _auth(request)
    try:
        from data.cache import cache
        cached = cache.get_raw(f"signal_{coin.upper()}")
        if not cached:
            raise HTTPException(404, f"No cached data for {coin}")

        score_detail = cached.get("score_detail")
        trace        = cached.get("trace")
        grade        = cached.get("grade", "--")
        score        = cached.get("score", 0)

        reasons = []
        if score_detail:
            for comp in score_detail.get("components", []):
                if comp.get("score", 0) > 0:
                    reasons.append({
                        "factor": comp["name"],
                        "score":  comp["score"],
                        "reason": comp.get("reason", ""),
                    })

        reasons.sort(key=lambda x: x["score"], reverse=True)

        return JSONResponse(content={
            "coin":         coin.upper(),
            "grade":        grade,
            "score":        score,
            "score_detail": score_detail,
            "top_reasons":  reasons[:5],
            "trace":        trace,
        })
    except HTTPException:
        raise
    except Exception as e:
        log.error("engine_confidence: %s", e)
        raise HTTPException(500, str(e))