"""Audited execution-mode transitions across a process restart.

The active process never changes account credentials. Quiesce -> verify both
accounts flat -> persist selection -> terminate -> Docker starts a fresh process.
"""
import asyncio
import functools
import hashlib
import hmac
import os
import signal
import time
from fastapi import HTTPException
from config import cfg

_transitioning = False
_active_operations = 0


def transitioning():
    return _transitioning


def guard_operation(fn):
    @functools.wraps(fn)
    async def wrapped(*args, **kwargs):
        global _active_operations
        if _transitioning:
            raise RuntimeError("Execution mode transition in progress; retry after restart")
        _active_operations += 1
        try:
            return await fn(*args, **kwargs)
        finally:
            _active_operations -= 1
    return wrapped


def assert_writes_allowed(path):
    # Listen-key cleanup must remain possible during graceful shutdown.
    if _transitioning and path != "/fapi/v1/listenKey":
        raise RuntimeError("Exchange writes paused for execution-mode transition")


def credentials(mode):
    return ((cfg.BINANCE_API_KEY, cfg.BINANCE_SECRET) if mode == "live"
            else (cfg.BINANCE_DEMO_API_KEY, cfg.BINANCE_DEMO_SECRET))


def live_configured():
    from trade.safety import LIVE_OPT_IN
    return bool(all(credentials("live")) and cfg.TOTP_SECRET and
                os.getenv("SIGNAL_ENGINE_ALLOW_LIVE_TRADING") == LIVE_OPT_IN)


def restore_mode():
    """The persisted operator choice overrides the initial environment default."""
    import runtime_state as rs
    from trade.safety import ensure_live_opt_in
    mode = rs.get("operator_execution_mode", os.getenv("TRADING_MODE", "paper"))
    if mode not in ("paper", "live"):
        raise RuntimeError("Invalid persisted execution mode")
    ensure_live_opt_in(mode)
    if mode == "live" and not live_configured():
        raise RuntimeError("Persisted live mode requires live credentials and TOTP; refusing account fallback")
    if mode == "live":
        from database import get_session, Trade
        from sqlalchemy import or_
        with get_session() as db:
            cross_account = db.query(Trade).filter(
                or_(Trade.is_active.is_(True), Trade.state.in_(["open", "pending", "reconciliation_required"])),
                Trade.execution_mode != "live").count()
        if cross_account:
            raise RuntimeError("Non-live local exposure cannot be managed by a live account; reconcile before startup")
    cfg.TRADING_MODE = mode
    cfg.PAPER_TRADING = mode == "paper"
    return mode


def mode_status():
    import runtime_state as rs
    return {
        "mode": cfg.TRADING_MODE,
        "pending_mode": rs.get("operator_execution_mode") if _transitioning else None,
        "transitioning": _transitioning,
        "live_available": live_configured(),
        "paper_available": bool(all(credentials("paper"))),
        "totp_configured": bool(cfg.TOTP_SECRET),
        "restart_enabled": os.getenv("MODE_SWITCH_RESTART", "false").lower() == "true",
        "engine_enabled": os.getenv("ENGINE_ENABLED", "true").lower() == "true",
        "requires_flat_accounts": True,
    }


def assert_local_flat():
    from database import get_session, Trade
    from trade.order_journal import unresolved
    with get_session() as db:
        from sqlalchemy import or_
        active = db.query(Trade).filter(or_(Trade.is_active.is_(True), Trade.state.in_(
            ["open", "pending", "reconciliation_required"]))).count()
    if active or unresolved():
        raise HTTPException(409, "Close or reconcile all local positions and order intents before switching")


async def assert_account_flat(mode):
    """Independent clients: never borrow or mutate the running exchange client."""
    import httpx
    from urllib.parse import urlencode
    key, secret = credentials(mode)
    if not key or not secret:
        raise HTTPException(409, f"{mode.title()} exchange credentials are required")
    url = "https://fapi.binance.com" if mode == "live" else cfg.BINANCE_DEMO_BASE_URL
    async with httpx.AsyncClient(timeout=10, headers={"X-MBX-APIKEY": key}) as client:
        async def read(path):
            query = urlencode({"timestamp": int(time.time() * 1000), "recvWindow": 5000})
            signature = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            response = await client.get(url + path + "?" + query + "&signature=" + signature)
            response.raise_for_status()
            return response.json()
        try:
            positions = await read("/fapi/v2/positionRisk")
            orders = await read("/fapi/v1/openOrders")
            algos = await read("/fapi/v1/openAlgoOrders")
            position_mode = await read("/fapi/v1/positionSide/dual")
            if not isinstance(positions, list) or not isinstance(orders, list):
                raise ValueError("Invalid exchange account response")
            if isinstance(algos, dict):
                algos = algos.get("orders")
            if not isinstance(algos, list):
                raise ValueError("Invalid conditional-order response")
            if not isinstance(position_mode, dict) or position_mode.get("dualSidePosition") is not False:
                raise HTTPException(409, f"{mode.title()} account must use one-way position mode")
            if any(float(p["positionAmt"]) != 0 for p in positions) or orders or algos:
                raise HTTPException(409, f"{mode.title()} account has positions or orders; close or cancel them first")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(409, f"Could not verify {mode} account state; switching was blocked") from None


async def request_transition(target, expected, actor, ip=""):
    global _transitioning
    if _transitioning:
        raise HTTPException(409, "A mode transition is already in progress")
    if expected != cfg.TRADING_MODE or target == cfg.TRADING_MODE:
        raise HTTPException(409, "Execution mode changed; refresh and confirm again")
    if os.getenv("MODE_SWITCH_RESTART", "false").lower() != "true":
        raise HTTPException(409, "Automatic restart is not configured; use the supplied Docker Compose deployment")
    if os.getenv("ENGINE_ENABLED", "true").lower() != "true":
        raise HTTPException(409, "Enable the engine on the server before switching modes")
    if target == "live" and not live_configured():
        raise HTTPException(409, "Live credentials, TOTP, and explicit server opt-in are required")
    _transitioning = True
    try:
        if _active_operations:
            raise HTTPException(409, "An execution operation is running; wait until it finishes")
        assert_local_flat()
        await assert_account_flat(cfg.TRADING_MODE)
        await assert_account_flat(target)
        assert_local_flat()
        from database import get_session, AuditLog
        import runtime_state as rs
        # Audit persistence is mandatory for this action, unlike best-effort telemetry.
        with get_session() as db:
            db.add(AuditLog(action="execution_mode_change", source=actor,
                detail=f"{cfg.TRADING_MODE} -> {target}; both accounts verified flat; restart requested",
                ip=ip, success=True))
        previous = rs.get("operator_execution_mode")
        try:
            rs.set("operator_execution_mode", target)
        except Exception:
            rs._state["operator_execution_mode"] = previous
            raise
        return {"success": True, "mode": cfg.TRADING_MODE, "pending_mode": target,
                "restart_required": True, "message": "Mode saved; service is restarting"}
    except BaseException:
        _transitioning = False
        raise


async def restart_process():
    await asyncio.sleep(1)
    os.kill(os.getpid(), signal.SIGTERM)
