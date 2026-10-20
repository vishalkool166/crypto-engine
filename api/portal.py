"""Explicit public projection and private operational API."""

import asyncio
import json
import math
import time
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select, text
from portal_settings import settings

router = APIRouter()
_snapshot = {"at": 0, "data": None}
PUBLIC_FIELDS = (
    "id",
    "timestamp",
    "coin",
    "direction",
    "grade",
    "score",
    "entry",
    "sl",
    "tp1",
    "tp2",
    "outcome",
    "market",
    "system_version",
)


def stamp(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def project_signal(row):
    return {key: stamp(getattr(row, key, None)) for key in PUBLIC_FIELDS}


def read_signals(limit=30, offset=0, coin="", grade=""):
    from database import SessionLocal, Signal

    with SessionLocal() as db:
        q = db.query(Signal).filter(Signal.market == "crypto")
        if coin:
            q = q.filter(Signal.coin == coin.upper())
        if grade:
            q = q.filter(Signal.grade == grade)
        total = q.count()
        rows = q.order_by(Signal.id.desc()).offset(offset).limit(limit).all()
        return {
            "items": [project_signal(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


def public_snapshot():
    if _snapshot["data"] is not None and time.monotonic() - _snapshot["at"] < 10:
        return _snapshot["data"]
    from database import SessionLocal, Signal
    from alerts.scanner import get_scan_stats
    from config import cfg

    scan = get_scan_stats()
    last = scan.get("last_scan_at") or None
    age = time.time() - last if last else None
    feed = read_signals(8)
    with SessionLocal() as db:
        counts = dict(
            db.query(Signal.outcome, func.count(Signal.id))
            .filter(Signal.market == "crypto")
            .group_by(Signal.outcome)
            .all()
        )
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
        "strategy_status": "not_evaluated",
        "status": "operational"
        if age is not None and age < 1800
        else "awaiting_data"
        if age is None
        else "stale",
        "last_scan_at": datetime.fromtimestamp(last, timezone.utc).isoformat()
        if last
        else None,
        "data_age_seconds": round(age) if age is not None else None,
        "universe": list(cfg.COINS),
        "signal_count": feed["total"],
        "recorded_outcomes": {str(k or "pending"): v for k, v in counts.items()},
        "signals": feed["items"],
    }
    _snapshot.update(at=time.monotonic(), data=data)
    return data


@router.get("/public/overview")
def overview():
    return public_snapshot()


@router.get("/public/signals")
def signals(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    coin: str = Query("", max_length=16, pattern="^[A-Za-z0-9]*$"),
    grade: str = Query("", pattern="^(A\\+|A|B|F)?$"),
):
    return read_signals(limit, offset, coin, grade)


@router.get("/public/signals/{signal_id}")
def signal_detail(signal_id: int):
    from database import SessionLocal, Signal

    with SessionLocal() as db:
        row = (
            db.query(Signal)
            .filter(Signal.id == signal_id, Signal.market == "crypto")
            .first()
        )
        if row is None:
            raise HTTPException(404, "Signal not found")
        result = project_signal(row)
        safe_keys = {
            "node",
            "name",
            "passed",
            "label",
            "direction",
            "adx",
            "grade",
            "score",
            "adx_pts",
            "rsi_pts",
            "vol_pts",
            "entry",
            "sl",
            "tp1",
            "rr1",
            "sl_pct",
            "reason",
            "result",
        }
        try:
            raw = json.loads(row.factor_scores or "{}")
            steps = raw.get("steps", []) if isinstance(raw, dict) else []
            result["trace"] = [
                {
                    k: stamp(v)
                    for k, v in step.items()
                    if k in safe_keys and not isinstance(v, (dict, list))
                }
                for step in steps
                if isinstance(step, dict) and step.get("node") != "sizing"
            ]
        except (ValueError, TypeError):
            result["trace"] = []
        return result


@router.get("/public/status")
def status():
    data = public_snapshot()
    return {
        k: data[k]
        for k in (
            "status",
            "timestamp",
            "mode",
            "last_scan_at",
            "data_age_seconds",
            "strategy_status",
        )
    }


def private_health(request):
    from database import engine
    from redis_client import get_redis
    from alerts.scanner import get_scan_stats, get_engine_health
    from config import cfg

    checks = {"database": "unknown", "redis": "unknown"}
    try:
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception:
        checks["database"] = "disconnected"
    try:
        redis = get_redis()
        checks["redis"] = (
            "connected" if redis is not None and redis.ping() else "disconnected"
        )
    except Exception:
        checks["redis"] = "disconnected"
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
        "checks": checks,
        "runtime": getattr(request.app.state, "engine_status", "not_started"),
        "scan": get_scan_stats(),
        "engine": get_engine_health(),
        "integrations": {
            "google": bool(cfg.GOOGLE_CLIENT_ID and cfg.GOOGLE_CLIENT_SECRET),
            "telegram": bool(
                cfg.TELEGRAM_TOKEN and cfg.TELEGRAM_CHAT_ID and cfg.WEBHOOK_SECRET
            ),
            "binance_demo": cfg.is_demo_configured(),
            "indian": bool(cfg.ANGELONE_API_KEY and cfg.ANGELONE_CLIENT_ID),
        },
        "origins": {"public": settings.public_origin, "admin": settings.admin_origin},
    }


@router.get("/admin/health")
def admin_health(request: Request):
    return private_health(request)


@router.get("/admin/overview")
async def admin_overview(request: Request):
    from api.dashboard import get_summary, get_performance
    from api.routes import make_serializable

    return make_serializable(
        {
            "summary": get_summary(),
            "performance": get_performance(),
            "health": private_health(request),
        }
    )


@router.post("/admin/scan")
async def run_scan(request: Request):
    if getattr(request.app.state, "scan_running", False):
        raise HTTPException(409, "A manual scan is already running")
    if getattr(request.app.state, "engine_status", "") != "running":
        raise HTTPException(409, "The paper engine is not ready; inspect System health")
    from alerts.scanner import scan_all_coins

    request.app.state.scan_running = True
    try:
        rows = await asyncio.wait_for(scan_all_coins(), timeout=120)
        _snapshot["at"] = 0
        return {
            "success": True,
            "analyzed": len(rows),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        request.app.state.scan_running = False


@router.get("/admin/research")
def research():
    from pathlib import Path

    try:
        gate = json.loads(Path("docs/RESEARCH_GATE.json").read_text())
    except (OSError, ValueError):
        gate = {"status": "not_evaluated"}
    return {
        "strategy_status": "not_evaluated",
        "mode": "paper",
        "gate": gate,
        "methodology": {
            "timeframes": ["4h", "1h"],
            "direction": "EMA200 with EMA20/50 alignment",
            "score": "ADX (40), RSI (30), relative volume (30)",
            "grades": {"A+": 80, "A": 65, "B": 50},
            "risk": "Swing level plus 0.5 ATR buffer; configured R-multiple targets",
        },
        "requirements": [
            "Contiguous closed-bar and funding dataset",
            "Out-of-sample walk-forward evidence",
            "Costs and execution sensitivity",
            "Independent paper-forward reconciliation",
        ],
    }


@router.get("/admin/integrations")
async def integrations(request: Request):
    from config import cfg
    import httpx

    result = {
        "telegram": {
            "configured": bool(cfg.TELEGRAM_TOKEN and cfg.TELEGRAM_CHAT_ID),
            "webhook": None,
        }
    }
    if result["telegram"]["configured"]:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    "https://api.telegram.org/bot"
                    + cfg.TELEGRAM_TOKEN
                    + "/getWebhookInfo"
                )
                info = response.json()
                if not info.get("ok"):
                    raise ValueError("Provider rejected request")
                data = info.get("result", {})
                result["telegram"]["webhook"] = {
                    k: data.get(k)
                    for k in ("url", "pending_update_count", "last_error_date")
                }
                result["telegram"]["status"] = (
                    "error"
                    if data.get("last_error_date")
                    else "registered"
                    if data.get("url")
                    else "not_registered"
                )
        except Exception:
            result["telegram"]["status"] = "unavailable"
    return result


@router.post("/admin/telegram/register")
async def register_telegram(request: Request):
    from config import cfg

    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID or not cfg.WEBHOOK_SECRET:
        raise HTTPException(409, "Telegram credentials and webhook secret are required")
    from alerts.telegram.client import register_webhook, register_commands

    await register_webhook()
    await register_commands()
    return await integrations(request)


@router.get("/admin/settings")
def admin_settings():
    from config import cfg

    return {
        "public_origin": settings.public_origin,
        "admin_origin": settings.admin_origin,
        "admin_emails": list(settings.admin_emails),
        "mode": "paper",
        "strategy_version": cfg.SYSTEM_VERSION,
        "session_hours": settings.session_hours,
        "exchange": "Binance USDⓈ-M Demo",
        "credentials": {
            "google": bool(cfg.GOOGLE_CLIENT_SECRET),
            "telegram": bool(cfg.TELEGRAM_TOKEN),
            "binance_demo": cfg.is_demo_configured(),
            "totp": bool(cfg.TOTP_SECRET),
        },
        "research_features": {
            "indian": "admin_only",
            "rag": "admin_only",
            "ml": "research_only",
        },
    }


from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    coin: str = Field(min_length=2, max_length=12, pattern="^[A-Z0-9]+$")


@router.post("/admin/research/backtest")
async def replay(body: ResearchRequest, request: Request):
    from config import cfg

    if body.coin not in cfg.COINS:
        raise HTTPException(400, "Choose a configured instrument")
    if getattr(request.app.state, "backtest_running", False):
        raise HTTPException(409, "A research replay is already running")
    request.app.state.backtest_running = True
    try:
        from backtest.engine import run_backtest
        from api.routes import make_serializable

        result = await asyncio.to_thread(
            run_backtest, coin=body.coin, capital=1000, leverage=1
        )
        if result.get("error"):
            raise HTTPException(409, str(result["error"]))
        return make_serializable(
            {
                "status": "research_only",
                "simulated_capital": 1000,
                "leverage": 1,
                "result": result,
            }
        )
    finally:
        request.app.state.backtest_running = False


class AssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


@router.get("/admin/assistant/status")
def assistant_status():
    from config import cfg
    import os

    return {
        "configured": bool(os.getenv("GROQ_API_KEY")),
        "scope": "private_trade_history",
        "external_provider": "Groq",
    }


@router.post("/admin/assistant")
async def assistant(body: AssistantRequest):
    import os

    if not os.getenv("GROQ_API_KEY"):
        raise HTTPException(409, "Private research assistant is not configured")
    from chatbot_rag import chat_with_sources

    return await asyncio.wait_for(chat_with_sources(body.question), timeout=45)
