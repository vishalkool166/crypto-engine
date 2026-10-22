"""HTTP entrypoint. Public projection and Google-authenticated operator APIs."""

import asyncio
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from collections import OrderedDict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from portal_settings import settings
from operator_auth import (
    init_operator_schema,
    current_operator,
    require_operator,
    create_operator_session,
    revoke_operator_session,
    oauth_client,
)
from api.portal import router as portal_router, public_snapshot
from service_runtime import lifespan

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
# HTTP client INFO logs include token-bearing Telegram URLs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger(__name__)
settings.validate()
app = FastAPI(
    title="Signal Engine",
    version="3.4.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    redirect_slashes=False,
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret or secrets.token_hex(32),
    session_cookie="__Host-se_oauth_state" if settings.production else "se_oauth_state",
    max_age=600,
    https_only=settings.production,
    same_site="lax",
)
_buckets = OrderedDict()


def app_host(request):
    return request.headers.get(
        "x-forwarded-app-host", request.headers.get("host", "")
    ).lower()


def trusted_edge(headers):
    if not settings.production:
        return True
    value = headers.get("x-origin-verify", "")
    return bool(
        settings.origin_secret and hmac.compare_digest(value, settings.origin_secret)
    )


def admit(ip, category, maximum):
    key = (ip, category)
    now = time.monotonic()
    previous = _buckets.get(key, (now, 0))
    started, count = previous if now - previous[0] < 60 else (now, 0)
    _buckets[key] = (started, count + 1)
    _buckets.move_to_end(key)
    while len(_buckets) > 10000:
        _buckets.popitem(last=False)
    return count < maximum


@app.middleware("http")
async def boundary(request: Request, call_next):
    path = request.url.path
    if path == "/health/live":
        return JSONResponse({"status": "alive"})
    if not trusted_edge(request.headers):
        return JSONResponse({"detail": "Forbidden"}, status_code=403)
    host = app_host(request)
    local_host = not settings.production and host.split(":")[0] in (
        "localhost", "127.0.0.1", "testserver"
    )
    # A public Pages host must never inherit the local development allowance,
    # even when local defaults are used by the test/development environment.
    public_path = path.startswith("/api/v1/public/")
    public_host = settings.public_enabled and host == settings.public_host
    webhook_path = path == "/webhook/telegram"
    admin_host = settings.admin_enabled and (
        host == settings.admin_host
        or (local_host and (not settings.public_enabled or host != settings.public_host))
    )
    if public_path:
        if not settings.public_enabled:
            return JSONResponse({"detail": "Not found"}, status_code=404)
    elif webhook_path and (public_host or admin_host or local_host):
        pass
    elif not admin_host:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    ip = (
        request.headers.get("x-visitor-ip", "")
        if settings.production
        else (request.client.host if request.client else "")
    )
    mutating = request.method not in ("GET", "HEAD", "OPTIONS")
    category = (
        "auth" if path.startswith("/auth/") else "mutation" if mutating else "read"
    )
    if not admit(ip, category, 20 if category == "auth" else 30 if mutating else 120):
        return JSONResponse(
            {"detail": "Request limit reached; try again shortly"},
            status_code=429,
            headers={"Retry-After": "60"},
        )
    if mutating:
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 65536:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
            body.extend(chunk)
        request._body = bytes(body)
    if path.startswith("/api/v1/admin/") or path in ("/auth/session", "/auth/logout"):
        user = current_operator(request)
        if not user:
            return JSONResponse(
                {"detail": "Operator authentication required"}, status_code=401
            )
        if mutating:
            origins = (
                (settings.admin_origin,)
                if settings.production
                else (
                    settings.admin_origin,
                    "http://localhost:5174",
                    "http://127.0.0.1:5174",
                )
            )
            if request.headers.get("origin") not in origins or not hmac.compare_digest(
                request.headers.get("x-csrf-token", ""), user["csrf"]
            ):
                return JSONResponse(
                    {"detail": "Request verification failed"}, status_code=403
                )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        {
            "detail": "Service operation failed; consult operator logs"
            if exc.status_code >= 500
            else exc.detail
        },
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def server_error(request, exc):
    log.exception("Unhandled request failure on %s", request.url.path)
    return JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)


@app.get("/auth/google")
async def google_start(request: Request):
    return await oauth_client().authorize_redirect(
        request,
        settings.admin_origin + "/auth/callback/google",
        prompt="select_account",
    )


@app.get("/auth/callback/google")
async def google_callback(request: Request):
    try:
        token = await oauth_client().authorize_access_token(request)
        info = token.get("userinfo")
        if not info:
            raise HTTPException(403, "Google identity was not verified")
        session = create_operator_session(info)
        response = RedirectResponse(settings.admin_origin + "/", status_code=303)
        response.set_cookie(
            settings.cookie_name,
            session,
            max_age=settings.session_hours * 3600,
            secure=settings.production,
            httponly=True,
            samesite="lax",
            path="/",
        )
        from auth import audit

        audit("operator_login", "google", "Verified operator sign-in", success=True)
        return response
    except HTTPException:
        return RedirectResponse(
            settings.admin_origin + "/login?error=unauthorized", status_code=303
        )
    except Exception:
        log.warning("Google operator authentication failed")
        return RedirectResponse(
            settings.admin_origin + "/login?error=authentication_failed",
            status_code=303,
        )


@app.get("/auth/session")
def session(request: Request):
    user = require_operator(request)
    return {
        "authenticated": True,
        "user": {"email": user["email"], "is_admin": True},
        "csrf": user["csrf"],
        "expires_at": user["expires_at"],
    }


@app.post("/auth/logout")
def logout(request: Request):
    revoke_operator_session(request)
    response = JSONResponse({"success": True})
    response.delete_cookie(
        settings.cookie_name,
        path="/",
        secure=settings.production,
        httponly=True,
        samesite="lax",
    )
    return response


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    from alerts.telegram.router import handle_webhook

    await handle_webhook(request)
    return {"ok": True}


app.include_router(portal_router, prefix="/api/v1")
from api.execution import router as execution_router
app.include_router(execution_router, prefix="/api/v1/admin")
from api.strategy_lab import router as strategy_lab_router
app.include_router(strategy_lab_router, prefix="/api/v1/admin")

# Existing operational functions remain available only within the operator boundary.
# Dangerous system administration and live mode switches are deliberately unmounted.
from api.routes import router as data_router
from api.trading import router as trading_router
from api.engine_health import router as engine_router
from api.indian import router as indian_router

DENIED = {
    "/health",
    "/scan",
    "/mode/toggle",
    "/system/docker-purge",
    "/backtest/{coin}",
    "/backtest/all/run",
    "/trades/start",
    "/trades/stop",
    "/trades/mode",
    "/chat",
    "/demo/track",
    "/content/{post_id}/publish",
}
for source in (data_router, trading_router, engine_router, indian_router):
    source.routes[:] = [
        route
        for route in source.routes
        if route.path not in DENIED
        and not route.path.startswith(("/content", "/demo", "/mode/"))
    ]
    app.include_router(source, prefix="/api/v1/admin")

_ws_counts = {}


async def stream(websocket, private):
    if not trusted_edge(websocket.headers):
        await websocket.close(code=1008)
        return
    if (private and not settings.admin_enabled) or (not private and not settings.public_enabled):
        await websocket.close(code=1008)
        return
    origin = websocket.headers.get("origin", "")
    expected = settings.admin_origin if private else settings.public_origin
    local = (
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    )
    if origin != expected and (settings.production or origin not in local):
        await websocket.close(code=1008)
        return
    if private and (
        app_host(websocket) != settings.admin_host
        and settings.production
        or not current_operator(websocket)
    ):
        await websocket.close(code=1008)
        return
    ip = (
        websocket.headers.get("x-visitor-ip", "")
        if settings.production
        else str(websocket.client.host)
    )
    if _ws_counts.get(ip, 0) >= 5 or sum(_ws_counts.values()) >= 200:
        await websocket.close(code=1013)
        return
    _ws_counts[ip] = _ws_counts.get(ip, 0) + 1
    await websocket.accept()
    last_health_at = 0.0
    health_data = None
    try:
        while True:
            if private and not current_operator(websocket):
                await websocket.close(code=1008)
                break
            if private:
                import time
                from api.portal import private_health
                from trade.ws import get_all_mark_prices

                now = time.monotonic()
                if health_data is None or now - last_health_at >= 15:
                    health_data = await asyncio.to_thread(private_health, websocket)
                    last_health_at = now
                data = {
                    **health_data,
                    "mark_prices": get_all_mark_prices(),
                    "mark_prices_at": datetime.now(timezone.utc).isoformat(),
                }
                interval = 1
            else:
                data = await asyncio.to_thread(public_snapshot)
                interval = 30
            await asyncio.wait_for(websocket.send_json(data), timeout=10)
            # Client input is never treated as a trading command.
            await asyncio.sleep(interval)
    except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError):
        pass
    except Exception:
        log.warning("Dashboard stream unavailable")
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            pass
    finally:
        _ws_counts[ip] = max(0, _ws_counts.get(ip, 1) - 1)
        if not _ws_counts[ip]:
            _ws_counts.pop(ip, None)


@app.websocket("/ws/public")
async def public_ws(websocket: WebSocket):
    await stream(websocket, False)


@app.websocket("/ws/admin")
async def admin_ws(websocket: WebSocket):
    await stream(websocket, True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)
