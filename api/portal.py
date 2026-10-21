"""Explicit public projection and private operational API."""

import asyncio
import json
import math
import os
import time
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select, text
from portal_settings import settings

router = APIRouter()
_snapshot = {"at": 0, "data": None}

DATA_TABLES = {
    "signals": "Recorded signals and outcomes",
    "signal_snapshots": "Signal state snapshots",
    "trade_outcomes": "Signal and trade outcome reconciliation",
    "trades": "Trade lifecycle and execution environment records",
    "trade_journey": "Recorded price path for each trade",
    "candles": "Stored market candles",
    "backtest_results": "Cached research replay results",
    "coin_config": "Crypto instrument configuration",
    "instrument_config": "Market instrument configuration",
    "binance_trade_records": "Exchange trade and fill reconciliation",
    "binance_account_snapshots": "Recorded demo account snapshots",
    "binance_funding_records": "Funding payments and settlements",
    "portfolio_snapshots": "Portfolio state snapshots",
    "coin_last_outcomes": "Latest recorded outcome per instrument",
    "system_versions": "Engine version history",
    "pillar_weight_history": "Signal scoring weight history",
    "adaptation_recommendations": "Engine adaptation proposals",
    "adaptation_log": "Recorded adaptation decisions",
    "rollback_checkpoints": "Engine rollback checkpoints",
    "thesis_snapshots": "Research thesis snapshots",
    "audit_log": "Operator and security audit events",
    "signal_deliveries": "Signal notification delivery history",
    "content_posts": "Stored content drafts and publication state",
    "users": "Retained legacy account records; customer access is disabled",
    "subscriptions": "Retained legacy plan records; billing is disabled",
    "api_keys": "Retained legacy API key metadata; hashes are redacted",
    "user_sessions": "Retained legacy session metadata; secrets are redacted",
    "demo_visits": "Retained legacy demo analytics",
    "operator_identities": "Google-verified operator identities",
    "operator_sessions": "Operator session metadata; secrets are redacted",
}
REDACTED_COLUMNS = {
    "password_hash", "password", "token", "token_hash", "csrf", "secret",
    "secret_hash", "api_key", "key_hash", "totp_secret", "recovery_codes",
    "google_subject", "authorization", "refresh_token", "session_token",
}


def _is_redacted_column(name):
    key = str(name).lower()
    return key in REDACTED_COLUMNS or any(
        marker in key
        for marker in ("password", "secret", "token", "credential", "api_key", "key_hash", "csrf")
    )
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
    from datetime import timedelta
    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=13)
    with SessionLocal() as db:
        counts = dict(
            db.query(Signal.outcome, func.count(Signal.id))
            .filter(Signal.market == "crypto")
            .group_by(Signal.outcome)
            .all()
        )
        activity_rows = db.query(func.date(Signal.timestamp), func.count(Signal.id)).filter(
            Signal.market == "crypto", Signal.timestamp >= str(start_day)
        ).group_by(func.date(Signal.timestamp)).all()
    activity_counts = dict(activity_rows)
    activity = [{"date": str(start_day + timedelta(days=i)), "count": activity_counts.get(str(start_day + timedelta(days=i)), 0)} for i in range(14)]
    data = {
        "activity": activity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": cfg.TRADING_MODE,
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
        "mode": cfg.TRADING_MODE,
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
        raise HTTPException(409, "The engine is not ready; inspect System health")
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
    from config import cfg
    from pathlib import Path

    try:
        gate = json.loads(Path("docs/RESEARCH_GATE.json").read_text())
    except (OSError, ValueError):
        gate = {"status": "not_evaluated"}
    return {
        "strategy_status": "not_evaluated",
        "mode": cfg.TRADING_MODE,
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
            "transport": os.getenv("TELEGRAM_TRANSPORT", "polling"),
            "expected_webhook_url": cfg.DOMAIN.rstrip("/") + "/webhook/telegram",
            "allowed_users_configured": bool(os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()),
        }
    }
    from alerts.telegram.service import status as command_status
    result["telegram"]["command_service"] = command_status()
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
                    for k in (
                        "url",
                        "pending_update_count",
                        "last_error_date",
                        "last_error_message",
                    )
                }
                result["telegram"]["status"] = (
                    "error"
                    if data.get("last_error_date")
                    else "registered"
                    if data.get("url") == result["telegram"]["expected_webhook_url"]
                    else "url_mismatch"
                    if data.get("url")
                    else "not_registered"
                )
        except Exception:
            result["telegram"]["status"] = "unavailable"
    if result["telegram"]["transport"] == "polling":
        result["telegram"]["status"] = "polling_connected" if result["telegram"]["command_service"]["connected"] else "polling_reconnecting"
    result["telegram"]["configured_chat_id"] = str(cfg.TELEGRAM_CHAT_ID or "")
    return result


@router.post("/admin/telegram/register")
async def register_telegram(request: Request):
    from config import cfg

    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID or (os.getenv("TELEGRAM_TRANSPORT", "polling") == "webhook" and not cfg.WEBHOOK_SECRET):
        raise HTTPException(409, "Telegram credentials and webhook secret are required")
    from alerts.telegram.client import register_webhook, register_commands

    if os.getenv("TELEGRAM_TRANSPORT", "polling") == "polling":
        from alerts.telegram.service import start
        await start()
        commands_registered = await register_commands()
        state = await integrations(request)
        state["telegram"]["registration"] = {"webhook": False, "commands": commands_registered, "transport": "polling"}
        return state
    webhook_registered = await register_webhook()
    commands_registered = await register_commands()
    state = await integrations(request)
    state["telegram"]["registration"] = {
        "webhook": webhook_registered,
        "commands": commands_registered,
    }
    return state


@router.get("/admin/settings")
def admin_settings():
    from config import cfg

    return {
        "public_origin": settings.public_origin,
        "admin_origin": settings.admin_origin,
        "admin_emails": list(settings.admin_emails),
        "mode": cfg.TRADING_MODE,
        "strategy_version": cfg.SYSTEM_VERSION,
        "session_hours": settings.session_hours,
        "exchange": "Binance USDⓈ-M Live" if cfg.TRADING_MODE == "live" else "Binance USDⓈ-M Demo",
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


@router.get("/admin/data/catalog")
def data_catalog():
    """Read-only, operator-only inventory of persisted tables."""
    from database import engine
    from sqlalchemy import inspect

    inspector = inspect(engine)
    available = set(inspector.get_table_names())
    catalog = []
    for table in sorted(available):
        if table.startswith("sqlite_"):
            continue
        purpose = DATA_TABLES.get(table, "Unclassified retained table; review its purpose before changing its schema")
        try:
            quoted = engine.dialect.identifier_preparer.quote(table)
            with engine.connect() as connection:
                count = connection.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar_one()
            columns = inspector.get_columns(table)
            catalog.append({
                "name": table,
                "purpose": purpose,
                "rows": int(count),
                "columns": len(columns),
                "sensitive": any(_is_redacted_column(column["name"]) for column in columns),
            })
        except Exception:
            # Preserve catalog visibility even when one legacy table needs review.
            catalog.append({"name": table, "purpose": purpose, "rows": None, "columns": None, "sensitive": True})
    return {"tables": catalog, "total_tables": len(catalog)}


@router.get("/admin/performance/context")
def performance_context():
    """Return descriptive breakdowns from closed trades and recorded factor scores."""
    from collections import defaultdict
    from database import SessionLocal, Trade as TradeModel, Signal as SignalModel

    def group_trades(rows, key_name):
        groups = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        for row in rows:
            label = getattr(row, key_name, None) or "Unspecified"
            item = groups[str(label)]
            pnl = float(row.net_pnl or row.pnl or 0)
            item["total"] += 1
            item["wins"] += row.outcome == "win"
            item["losses"] += row.outcome == "loss"
            item["pnl"] += pnl
        result = []
        for label, item in groups.items():
            result.append({
                key_name: label,
                **item,
                "win_rate": round(item["wins"] / item["total"] * 100, 1) if item["total"] else 0,
                "pnl": round(item["pnl"], 4),
            })
        return sorted(result, key=lambda item: item["total"], reverse=True)

    def numeric_factors(raw):
        try:
            value = json.loads(raw or "{}")
        except (TypeError, ValueError):
            return {}
        factors = {}
        breakdown = value.get("score_breakdown", {}) if isinstance(value, dict) else {}
        if isinstance(breakdown, dict):
            for name, score in breakdown.items():
                if isinstance(score, (int, float)) and math.isfinite(float(score)):
                    factors[str(name)] = float(score)
        components = value.get("components", []) if isinstance(value, dict) else []
        if isinstance(components, list):
            for component in components:
                if not isinstance(component, dict):
                    continue
                name = component.get("name") or component.get("factor")
                score = component.get("score")
                if name and isinstance(score, (int, float)) and math.isfinite(float(score)):
                    factors[str(name)] = float(score)
        steps = value.get("steps", []) if isinstance(value, dict) else []
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                name = step.get("name") or step.get("node") or step.get("factor")
                score = step.get("score")
                if name and isinstance(score, (int, float)) and math.isfinite(float(score)):
                    factors[str(name)] = float(score)
        return factors

    with SessionLocal() as db:
        trades = db.query(TradeModel).filter(TradeModel.outcome.in_(["win", "loss"])).all()
        signals = db.query(SignalModel).filter(
            SignalModel.outcome.in_(["win", "loss"]),
            SignalModel.factor_scores.is_not(None),
        ).all()

    factor_groups = defaultdict(lambda: {"observations": 0, "win_score": 0.0, "loss_score": 0.0, "wins": 0, "losses": 0})
    for signal in signals:
        for name, score in numeric_factors(signal.factor_scores).items():
            item = factor_groups[name]
            item["observations"] += 1
            if signal.outcome == "win":
                item["wins"] += 1
                item["win_score"] += score
            else:
                item["losses"] += 1
                item["loss_score"] += score

    factors = []
    for name, item in factor_groups.items():
        avg_wins = item["win_score"] / item["wins"] if item["wins"] else None
        avg_losses = item["loss_score"] / item["losses"] if item["losses"] else None
        factors.append({
            "factor": name,
            "observations": item["observations"],
            "mean_score_wins": round(avg_wins, 3) if avg_wins is not None else None,
            "mean_score_losses": round(avg_losses, 3) if avg_losses is not None else None,
            "score_difference": round(avg_wins - avg_losses, 3) if avg_wins is not None and avg_losses is not None else None,
        })
    factors.sort(key=lambda item: item["observations"], reverse=True)

    return {
        "by_version": group_trades(trades, "system_version"),
        "by_regime": group_trades(trades, "regime_at_entry"),
        "factors": factors,
        "factor_note": "Descriptive averages from stored factor scores; small samples and associations do not establish causation.",
    }


@router.get("/admin/data/{table}")
def data_table(
    table: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000000),
    q: str = Query("", max_length=100),
):
    """Paginated, read-only view of a whitelisted table with secrets redacted."""
    from database import engine
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if table not in set(inspector.get_table_names()):
        raise HTTPException(404, "Data table is not present in this database")
    if table.startswith("sqlite_"):
        raise HTTPException(404, "SQLite internal tables are not part of the application data view")

    columns = inspector.get_columns(table)
    names = [str(column["name"]) for column in columns]
    if not names:
        return {"table": table, "columns": [], "rows": [], "total": 0, "limit": limit, "offset": offset}
    preparer = engine.dialect.identifier_preparer
    quoted_table = preparer.quote(table)
    quoted_columns = [preparer.quote(name) for name in names]
    searchable = [
        name for name in names
        if any(token in name.lower() for token in ("coin", "symbol", "outcome", "status", "direction", "market", "email", "action", "entity", "type", "state", "title", "reason"))
    ]
    where = ""
    params = {"limit": limit, "offset": offset}
    if q.strip() and searchable:
        where = " WHERE " + " OR ".join(
            f"CAST({preparer.quote(name)} AS TEXT) LIKE :term" for name in searchable
        )
        params["term"] = f"%{q.strip()}%"
    primary = inspector.get_pk_constraint(table).get("constrained_columns") or []
    sort_column = next((name for name in ("timestamp", "created_at", "opened_at", "snapshot_at", "id") if name in names), None)
    if not sort_column and primary:
        sort_column = primary[0]
    order = f" ORDER BY {preparer.quote(sort_column)} DESC" if sort_column else ""
    select_columns = ", ".join(quoted_columns)
    with engine.connect() as connection:
        total = connection.execute(text(f"SELECT COUNT(*) FROM {quoted_table}{where}"), params).scalar_one()
        raw_rows = connection.execute(
            text(f"SELECT {select_columns} FROM {quoted_table}{where}{order} LIMIT :limit OFFSET :offset"),
            params,
        ).mappings().all()
    rows = []
    for row in raw_rows:
        safe = {}
        for name, value in row.items():
            if _is_redacted_column(name):
                safe[name] = "[REDACTED]"
            elif isinstance(value, bytes):
                safe[name] = f"[binary data: {len(value)} bytes]"
            else:
                safe[name] = stamp(value)
        rows.append(safe)
    return {
        "table": table,
        "purpose": DATA_TABLES.get(table, "Unclassified retained table; review its purpose before changing its schema"),
        "columns": [
            {"name": str(column["name"]), "type": str(column["type"]), "redacted": _is_redacted_column(column["name"])}
            for column in columns
        ],
        "rows": rows,
        "total": int(total),
        "limit": limit,
        "offset": offset,
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
