import asyncio
import hashlib
import json
import logging
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, Response, RedirectResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware
from api.routes       import router, build_dashboard_payload
from api.trading      import router as trading_router
from saas.admin       import router as admin_router
from database         import init_db
from scheduler        import start_scheduler, stop_scheduler
from alerts.telegram  import send, register_webhook, handle_webhook
from config           import cfg, _bootstrap_secrets
from events           import on_event, emit
import runtime_state  as rs

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

log       = logging.getLogger(__name__)
templates = Jinja2Templates(directory="frontend")

_dashboard_clients:   dict         = {}
_last_payload_hash:   str          = ""
_dashboard_push_task: asyncio.Task = None
_cpu_warmup_task:     asyncio.Task = None

limiter = Limiter(key_func=get_remote_address)


def _get_client_tier(websocket: WebSocket) -> str:
    try:
        from saas.middleware import get_current_user

        class FakeRequest:
            def __init__(self, ws):
                self.cookies = dict(ws.cookies)
                self.headers = dict(ws.headers)

        fake = FakeRequest(websocket)
        user = get_current_user(fake)
        if user:
            return user.get("tier", "free")
    except Exception:
        pass
    return "free"


async def _build_ticker_payload(tier: str = "admin") -> dict:
    from saas.signals import get_summary_for_tier
    from trade.ws import get_all_mark_prices

    summary     = get_summary_for_tier(tier)
    mark_prices = get_all_mark_prices()

    return {
        "type":        "ticker",
        "items":       [],
        "mark_prices": mark_prices,
        "summary": {
            "next_scan_epoch": summary.get("next_scan_epoch", 0),
            "mode":            summary.get("mode",          "paper"),
            "today_pnl":       summary.get("today_pnl",     None),
            "today_pnl_pos":   summary.get("today_pnl_pos", True),
            "today_trades":    summary.get("today_trades",  None),
            "coins_count":     summary.get("coins_count",   0),
        }
    }


async def _build_ws_payload(tier: str = "admin") -> dict:
    from saas.signals import get_dashboard_for_tier
    from trade.ws import get_all_mark_prices
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_mark_price

    dashboard   = get_dashboard_for_tier(tier)
    mark_prices = get_all_mark_prices()

    try:
        open_trades = await get_open_positions_enriched()
        for trade in open_trades:
            coin       = trade.get("coin", "")
            live_price = get_mark_price(coin)
            if live_price:
                trade["current_price"] = live_price
                entry    = float(trade.get("entry_price") or 0)
                leverage = int(trade.get("leverage") or 1)
                margin   = float(trade.get("margin_used") or 0)
                is_short = trade.get("is_short", False)
                if entry > 0:
                    if is_short:
                        pnl = (entry - live_price) / entry * margin * leverage
                    else:
                        pnl = (live_price - entry) / entry * margin * leverage
                    trade["profit_abs"]   = round(pnl - margin * leverage * 0.001, 4)
                    trade["profit_ratio"] = round(
                        (live_price - entry) / entry * leverage if not is_short
                        else (entry - live_price) / entry * leverage,
                        4
                    )
        dashboard["open_trades"] = open_trades
    except Exception as e:
        log.error(f"Trade enrichment error: {e}")

    dashboard["mark_prices"] = mark_prices
    return dashboard


async def _push_to_clients(payload_str: str):
    dead = set()
    for ws_id, ws_info in _dashboard_clients.items():
        ws = ws_info["ws"]
        try:
            await ws.send_text(payload_str)
        except Exception:
            dead.add(ws_id)
    for ws_id in dead:
        _dashboard_clients.pop(ws_id, None)


async def push_event(event_type: str, data: dict = None):
    global _last_payload_hash
    if not _dashboard_clients:
        return
    try:
        tiers_present = set(
            info.get("tier", "free")
            for info in _dashboard_clients.values()
        )

        for tier in tiers_present:
            tier_clients = {
                k: v for k, v in _dashboard_clients.items()
                if v.get("tier") == tier
            }
            if not tier_clients:
                continue

            if event_type == "ping":
                payload      = await _build_ticker_payload(tier)
                payload_str  = json.dumps(payload)
                payload_hash = hashlib.md5(
                    (tier + payload_str).encode()
                ).hexdigest()
                if payload_hash == _last_payload_hash:
                    continue
                _last_payload_hash = payload_hash
            else:
                payload     = await _build_ws_payload(tier)
                payload_str = json.dumps(payload)

            dead = set()
            for ws_id, ws_info in tier_clients.items():
                ws = ws_info["ws"]
                try:
                    await ws.send_text(payload_str)
                except Exception:
                    dead.add(ws_id)
            for ws_id in dead:
                _dashboard_clients.pop(ws_id, None)

    except Exception as e:
        log.error(f"push_event error: {e}")


async def _push_trade_update(event_type: str, data: dict = None):
    if not _dashboard_clients:
        return
    try:
        from trade.monitor import get_open_positions_enriched, get_profit_summary
        from trade.ws import get_mark_price

        open_trades = await get_open_positions_enriched()
        for trade in open_trades:
            coin       = trade.get("coin", "")
            live_price = get_mark_price(coin)
            if live_price:
                trade["current_price"] = live_price

        profit = get_profit_summary()

        payload = json.dumps({
            "type":        "trade_update",
            "event":       event_type,
            "open_trades": open_trades,
            "profit":      profit,
            "data":        data or {},
        })

        await _push_to_clients(payload)

    except Exception as e:
        log.error(f"_push_trade_update error: {e}")


async def _on_trade_event(event_type: str, data: dict):
    push_types = {"trade_closed", "order_filled", "account_update"}
    if event_type in push_types:
        await _push_trade_update(event_type, data)


async def _dashboard_push_loop():
    while True:
        await asyncio.sleep(2)
        if _dashboard_clients:
            await push_event("dashboard")


async def _cpu_warmup_loop():
    import psutil
    while True:
        psutil.cpu_percent(interval=None)
        await asyncio.sleep(30)


async def _session_cleanup_loop():
    from saas.sessions import cleanup_expired_sessions
    while True:
        await asyncio.sleep(3600)
        try:
            count = cleanup_expired_sessions()
            if count:
                log.info(f"Session cleanup: {count} expired sessions removed")
        except Exception as e:
            log.error(f"Session cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _dashboard_push_task, _cpu_warmup_task

    rs.load()
    _bootstrap_secrets()

    on_event(push_event)

    from trade.ws import start_ws, on_trade_event
    on_trade_event(_on_trade_event)

    from auth import setup_status
    status = setup_status()
    if not status["setup_complete"]:
        log.warning("=" * 60)
        log.warning("FIRST RUN — visit /auth/setup to complete setup")
        log.warning(f"TOTP URI: {status['totp_uri']}")
        log.warning(f"API Key:  {status['api_key']}")
        log.warning(f"Username: {status['username']}")
        log.warning("=" * 60)

    _dashboard_push_task = asyncio.create_task(_dashboard_push_loop())
    _cpu_warmup_task     = asyncio.create_task(_cpu_warmup_loop())
    _session_cleanup     = asyncio.create_task(_session_cleanup_loop())

    start_scheduler()
    await register_webhook()

    from alerts.telegram import register_commands
    await register_commands()

    await start_ws()
    log.info("Binance WebSocket streams started")

    mode   = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER (Binance Demo)"
    grades = ", ".join(cfg.MIN_GRADE_TO_TRADE)

    await send(
        f"✅ *Signal Engine v5 Started*\n\n"
        f"Mode:     `{mode}`\n"
        f"Coins:    `{len(cfg.COINS)} coins`\n"
        f"Grades:   `{grades}`\n"
        f"Webhook:  `✅ Active`\n"
        f"WS:       `✅ Binance streams active`\n"
        f"Scan:     `every :00/:15/:30/:45 UTC`\n\n"
        f"Type /help for commands"
    )

    rs.mark_clean_shutdown()

    yield

    rs.mark_crash()

    if _dashboard_push_task:
        _dashboard_push_task.cancel()
        try:
            await _dashboard_push_task
        except asyncio.CancelledError:
            pass

    if _cpu_warmup_task:
        _cpu_warmup_task.cancel()
        try:
            await _cpu_warmup_task
        except asyncio.CancelledError:
            pass

    _session_cleanup.cancel()
    try:
        await _session_cleanup
    except asyncio.CancelledError:
        pass

    from trade.ws import stop_ws
    await stop_ws()

    from trade.exchange import close_exchange
    await close_exchange()

    from trade.monitor import stop_monitor
    stop_monitor()

    stop_scheduler()

    await send("🔴 *Signal Engine v5 Stopped*")

    rs.mark_clean_shutdown()
    log.info("Signal Engine stopped")


app = FastAPI(
    title       = "Signal Engine v5",
    description = "Automated crypto signal engine",
    version     = "5.0.0",
    lifespan    = lifespan
)

app.add_middleware(
    SessionMiddleware,
    secret_key = cfg.JWT_SECRET,
    max_age    = 3600,
    https_only = cfg.ENV == "production",
    same_site  = "lax",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = [
    cfg.DOMAIN,
    cfg.FRONTEND_URL,
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
allowed_origins = [o for o in allowed_origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins     = allowed_origins,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
    allow_credentials = True
)


@app.middleware("http")
async def cache_headers(request: Request, call_next):
    response = await call_next(request)
    path     = request.url.path

    if any(path.endswith(f) for f in [
        'preact.min.js',
        'preact-hooks.min.js',
        'htm.min.js',
        'chartjs.min.js',
        'alpine.min.js',
    ]):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.endswith(('.js', '.css')):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        response.headers["Pragma"]        = "no-cache"
        response.headers["Expires"]       = "0"

    return response


@app.get("/auth/google")
async def auth_google(request: Request):
    try:
        from authlib.integrations.starlette_client import OAuth
        from starlette.config import Config as StarletteConfig

        config = StarletteConfig(environ={
            "GOOGLE_CLIENT_ID":     cfg.GOOGLE_CLIENT_ID,
            "GOOGLE_CLIENT_SECRET": cfg.GOOGLE_CLIENT_SECRET,
        })

        oauth = OAuth(config)
        oauth.register(
            name                = "google",
            server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs       = {"scope": "openid email profile"},
        )

        redirect_uri = f"{cfg.DOMAIN or 'http://localhost:8000'}/auth/callback/google"
        return await oauth.google.authorize_redirect(request, redirect_uri)

    except Exception as e:
        log.error(f"Google auth error: {e}")
        raise HTTPException(500, "OAuth configuration error")


@app.get("/auth/callback/google")
async def auth_callback_google(request: Request):
    try:
        from authlib.integrations.starlette_client import OAuth
        from starlette.config import Config as StarletteConfig
        from saas.users    import create_or_get_user
        from saas.sessions import create_session
        from auth          import create_oauth_jwt

        config = StarletteConfig(environ={
            "GOOGLE_CLIENT_ID":     cfg.GOOGLE_CLIENT_ID,
            "GOOGLE_CLIENT_SECRET": cfg.GOOGLE_CLIENT_SECRET,
        })

        oauth = OAuth(config)
        oauth.register(
            name                = "google",
            server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs       = {"scope": "openid email profile"},
        )

        token    = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)

        email       = userinfo.get("email", "")
        name        = userinfo.get("name", "")
        avatar      = userinfo.get("picture", "")
        provider_id = userinfo.get("sub", "")

        if not email:
            raise HTTPException(400, "No email from Google")

        user = create_or_get_user(
            email       = email,
            name        = name,
            avatar      = avatar,
            provider    = "google",
            provider_id = provider_id,
        )

        ip         = request.client.host if request.client else ""
        user_agent = request.headers.get("user-agent", "")

        session_id = create_session(
            user_id    = user["id"],
            tier       = user["tier"],
            ip         = ip,
            user_agent = user_agent,
        )

        from jose import jwt as jose_jwt
        import datetime as _dt
        from datetime import timedelta
        payload = {
            "sub":        str(user["id"]),
            "email":      user["email"],
            "tier":       user["tier"],
            "is_admin":   user["is_admin"],
            "session_id": session_id,
            "type":       "oauth",
            "iat":        _dt.datetime.now(_dt.timezone.utc),
            "exp":        _dt.datetime.now(_dt.timezone.utc) + timedelta(hours=cfg.OAUTH_JWT_EXPIRY),
        }
        final_token = jose_jwt.encode(payload, cfg.OAUTH_JWT_SECRET, algorithm="HS256")

        is_new   = user.get("is_new", False)
        redirect = f"{cfg.DOMAIN}/"

        response = RedirectResponse(url=redirect)
        response.set_cookie(
            key      = cfg.SESSION_COOKIE_NAME,
            value    = final_token,
            httponly = cfg.SESSION_COOKIE_HTTPONLY,
            secure   = cfg.SESSION_COOKIE_SECURE,
            samesite = cfg.SESSION_COOKIE_SAMESITE,
            max_age  = cfg.SESSION_COOKIE_MAX_AGE,
        )

        from auth import audit
        audit(
            action  = "oauth_login",
            source  = "google",
            detail  = f"user:{email} tier:{user['tier']} new:{is_new}",
            ip      = ip,
            success = True,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Google callback error: {e}")
        return RedirectResponse(url="/login?error=oauth_failed")


@app.get("/auth/session")
async def auth_session(request: Request):
    try:
        from saas.middleware import get_current_user
        from saas.users import get_user_by_id
        user = get_current_user(request)
        if not user:
            return JSONResponse(
                status_code = 401,
                content     = {"authenticated": False}
            )
        user_id = int(user.get("sub", 0))
        if user_id:
            fresh = get_user_by_id(user_id)
            if fresh:
                return JSONResponse(content={
                    "authenticated": True,
                    "user": {
                        "id":       str(fresh["id"]),
                        "email":    fresh["email"],
                        "tier":     fresh["tier"],
                        "is_admin": fresh["is_admin"],
                    }
                })
        return JSONResponse(content={
            "authenticated": True,
            "user": {
                "id":       user.get("sub"),
                "email":    user.get("email"),
                "tier":     user.get("tier"),
                "is_admin": user.get("is_admin", False),
            }
        })
    except Exception as e:
        log.error(f"Session check error: {e}")
        return JSONResponse(
            status_code = 401,
            content     = {"authenticated": False}
        )


@app.get("/auth/logout")
async def auth_logout(request: Request):
    try:
        from saas.middleware import get_current_user
        from saas.sessions  import revoke_session

        user = get_current_user(request)
        if user and user.get("session_id"):
            revoke_session(user["session_id"])
    except Exception:
        pass

    response = RedirectResponse(url="/")
    response.delete_cookie(cfg.SESSION_COOKIE_NAME)
    response.delete_cookie("se_token")
    return response


@app.get("/api/me/sessions")
async def get_my_sessions(request: Request):
    try:
        from saas.middleware import get_current_user
        from saas.sessions  import get_user_sessions

        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        user_id  = int(user.get("sub", 0))
        sessions = get_user_sessions(user_id)

        return JSONResponse(content={"sessions": sessions})

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_my_sessions error: {e}")
        raise HTTPException(500, str(e))


@app.post("/api/me/sessions/{session_id}/revoke")
async def revoke_my_session(request: Request, session_id: str):
    try:
        from saas.middleware import get_current_user
        from saas.sessions  import revoke_session

        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        user_id = int(user.get("sub", 0))
        result  = revoke_session(session_id, user_id)

        if not result.get("success"):
            raise HTTPException(400, result.get("reason", "Failed"))

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/me/sessions/revoke-all")
async def revoke_all_my_sessions(request: Request):
    try:
        from saas.middleware import get_current_user
        from saas.sessions  import revoke_all_sessions

        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        user_id     = int(user.get("sub", 0))
        current_sid = user.get("session_id")
        result      = revoke_all_sessions(user_id, except_session=current_sid)

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/auth/onboarding/complete")
async def complete_onboarding(request: Request):
    try:
        from saas.middleware import get_current_user
        from saas.users     import mark_user_onboarded

        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        user_id = int(user.get("sub", 0))
        if user_id:
            mark_user_onboarded(user_id)

        return JSONResponse(content={"success": True})
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Onboarding complete error: {e}")
        raise HTTPException(500, str(e))


@app.get("/api/pricing")
async def get_pricing():
    try:
        from saas.tiers import get_pricing_data
        return JSONResponse(content=get_pricing_data())
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/me")
async def get_me(request: Request):
    try:
        from saas.middleware import get_current_user
        from saas.users     import get_user_by_id, list_api_keys
        from saas.sessions  import get_user_sessions

        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        user_id   = int(user.get("sub", 0))
        user_data = get_user_by_id(user_id) if user_id else None

        if not user_data:
            return JSONResponse(content={
                "id":       user.get("sub"),
                "email":    user.get("email"),
                "tier":     user.get("tier"),
                "is_admin": user.get("is_admin", False),
            })

        from config import get_tier_features
        features = get_tier_features(user_data["tier"])

        api_keys = []
        if features.get("api_key_access"):
            api_keys = list_api_keys(user_id)

        sessions = get_user_sessions(user_id)

        return JSONResponse(content={
            **user_data,
            "features": features,
            "api_keys": api_keys,
            "sessions": sessions,
        })

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_me error: {e}")
        raise HTTPException(500, str(e))


@app.post("/api/me/api-keys")
async def create_api_key(request: Request):
    try:
        from saas.middleware import get_current_user
        from saas.users     import create_api_key_for_user
        from config         import tier_has_feature

        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        tier = user.get("tier", "free")
        if not tier_has_feature(tier, "api_key_access"):
            raise HTTPException(
                403,
                {"code": "upgrade_required", "required_tier": "elite"}
            )

        body    = await request.json()
        name    = body.get("name", "Default")
        user_id = int(user.get("sub", 0))
        result  = create_api_key_for_user(user_id, name)

        if not result.get("success"):
            raise HTTPException(400, result.get("reason", "Failed"))

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_api_key error: {e}")
        raise HTTPException(500, str(e))


@app.delete("/api/me/api-keys/{key_id}")
async def delete_api_key(request: Request, key_id: int):
    try:
        from saas.middleware import get_current_user
        from saas.users     import revoke_api_key

        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        user_id = int(user.get("sub", 0))
        result  = revoke_api_key(key_id, user_id)

        if not result.get("success"):
            raise HTTPException(400, result.get("reason", "Failed"))

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/auth/setup")
async def auth_setup(request: Request):
    from auth import setup_status, get_qr_svg, get_qr_png_bytes

    status = setup_status()

    if status["setup_complete"]:
        raise HTTPException(
            status_code = 403,
            detail      = "Setup already complete."
        )

    qr_svg           = ""
    qr_png_available = False

    if cfg.TOTP_SECRET:
        qr_svg = get_qr_svg()
        if not qr_svg:
            qr_png_available = bool(get_qr_png_bytes())

    return templates.TemplateResponse("setup.html", {
        "request":          request,
        "status":           status,
        "qr_svg":           qr_svg,
        "qr_png_available": qr_png_available,
        "totp_secret":      cfg.TOTP_SECRET,
        "totp_uri":         status["totp_uri"],
        "username":         cfg.DASHBOARD_USERNAME,
        "api_key":          cfg.DASHBOARD_API_KEY,
    })


@app.get("/login.html")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "mode":    "live" if not cfg.PAPER_TRADING else "paper"
    })


@app.post("/auth/login")
@limiter.limit("10/minute")
async def auth_login(request: Request):
    try:
        body     = await request.json()
        username = body.get("username", "").strip()
        password = body.get("password", "")
        totp     = body.get("totp_code", "")
        ip       = request.client.host if request.client else ""

        from auth import validate_login
        result = validate_login(username, password, totp, ip)

        if result["success"]:
            response = JSONResponse(content={
                "success":  True,
                "username": result.get("username", ""),
                "tier":     result.get("tier", "pro"),
                "mode":     "live" if not cfg.PAPER_TRADING else "paper"
            })
            response.set_cookie(
                key      = "se_token",
                value    = result["token"],
                httponly = True,
                secure   = cfg.ENV == "production",
                samesite = "lax",
                max_age  = 86400
            )
            return response
        else:
            status_code = 423 if result.get("locked") else 401
            return JSONResponse(
                status_code = status_code,
                content     = {
                    "success":            False,
                    "reason":             result["reason"],
                    "locked":             result.get("locked", False),
                    "lockout_minutes":    result.get("lockout_minutes", 0),
                    "attempts_remaining": result.get("attempts_remaining", 5),
                }
            )
    except Exception as e:
        log.error(f"Login error: {e}")
        raise HTTPException(500, "Login failed")


@app.post("/auth/request-totp")
@limiter.limit("5/minute")
async def request_totp_via_telegram(request: Request):
    try:
        body     = await request.json()
        password = body.get("password", "")

        if not password:
            return JSONResponse(
                status_code = 400,
                content     = {"success": False, "reason": "Password required"}
            )

        from auth import verify_password
        if not verify_password(password, cfg.DASHBOARD_PASSWORD_HASH):
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid password"}
            )

        if not cfg.TOTP_SECRET:
            return JSONResponse(
                status_code = 400,
                content     = {"success": False, "reason": "TOTP not configured"}
            )

        import pyotp
        code = pyotp.TOTP(cfg.TOTP_SECRET).now()
        await send(
            f"🔐 *Login Code Requested*\n\n"
            f"Your current TOTP code:\n"
            f"`{code}`\n\n"
            f"_Valid for ~30 seconds._\n"
            f"_If you didn't request this, ignore it._"
        )
        return JSONResponse(content={"success": True})
    except Exception as e:
        log.error(f"Request TOTP error: {e}")
        return JSONResponse(
            status_code = 500,
            content     = {"success": False, "reason": "Failed to send"}
        )


@app.post("/auth/reset-password")
@limiter.limit("5/minute")
async def auth_reset_password(request: Request):
    try:
        body          = await request.json()
        totp_code     = body.get("totp_code", "")
        recovery_code = body.get("recovery_code", "")
        new_password  = body.get("new_password", "")
        ip            = request.client.host if request.client else ""

        from auth import reset_password_with_totp, reset_password_with_recovery

        if recovery_code:
            result = reset_password_with_recovery(recovery_code, new_password, ip)
        else:
            result = reset_password_with_totp(totp_code, new_password, ip)

        return JSONResponse(content=result)
    except Exception as e:
        log.error(f"Reset password error: {e}")
        raise HTTPException(500, "Reset failed")


@app.post("/auth/set-credentials")
async def auth_set_credentials(request: Request):
    try:
        body     = await request.json()
        password = body.get("password")
        username = body.get("username")
        messages = []

        if username:
            from auth import set_username
            set_username(username)
            messages.append(f"Username updated to '{username}'")

        if password:
            if len(password) < 8:
                return JSONResponse(
                    status_code = 400,
                    content     = {"success": False, "reason": "Password too short — minimum 8 characters"}
                )
            from auth import set_password
            set_password(password)
            messages.append("Password updated")

        if not messages:
            return JSONResponse(content={"success": False, "reason": "Nothing to update"})

        return JSONResponse(content={"success": True, "message": " · ".join(messages)})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/auth/regenerate-totp")
async def auth_regenerate_totp(request: Request):
    try:
        body     = await request.json()
        password = body.get("password", "")

        if not password:
            return JSONResponse(
                status_code = 400,
                content     = {"success": False, "reason": "Current password required to regenerate TOTP"}
            )

        from auth import verify_password, regenerate_totp
        if not verify_password(password, cfg.DASHBOARD_PASSWORD_HASH):
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid password"}
            )

        new_secret = regenerate_totp()
        return JSONResponse(content={"success": True, "secret": new_secret})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/auth/generate-recovery-codes")
async def auth_generate_recovery_codes(request: Request):
    try:
        body      = await request.json()
        totp_code = body.get("totp_code", "")

        from auth import verify_totp, generate_recovery_codes, store_recovery_codes
        if not verify_totp(totp_code):
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": "Invalid authenticator code"}
            )

        codes = generate_recovery_codes(8)
        store_recovery_codes(codes)

        ip = request.client.host if request.client else ""
        from auth import audit
        audit("recovery_codes_generated", "web", "New recovery codes generated", ip=ip)

        return JSONResponse(content={"success": True, "codes": codes})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/auth/qr.png")
async def auth_qr_png():
    from auth import get_qr_png_bytes
    try:
        png = get_qr_png_bytes()
        if not png:
            raise HTTPException(500, "QR generation failed")
        return Response(content=png, media_type="image/png")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/ws/status")
async def ws_status(request: Request):
    from trade.ws import get_ws_status
    return JSONResponse(content=get_ws_status())


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()

    tier  = _get_client_tier(websocket)
    ws_id = id(websocket)
    _dashboard_clients[ws_id] = {"ws": websocket, "tier": tier}

    try:
        initial = await _build_ws_payload(tier)
        await websocket.send_text(json.dumps(initial))
    except Exception as e:
        log.error(f"Dashboard WS initial push error: {e}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _dashboard_clients.pop(ws_id, None)
    except Exception:
        _dashboard_clients.pop(ws_id, None)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    await handle_webhook(request)
    return JSONResponse(content={"ok": True})


app.include_router(router,         prefix="/api")
app.include_router(trading_router, prefix="/api")
app.include_router(admin_router,   prefix="/api")

from fastapi.responses import FileResponse
import os as _os


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    static_dir = "frontend"
    file_path  = _os.path.join(static_dir, full_path)
    if _os.path.exists(file_path) and _os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(_os.path.join(static_dir, "index.html"))


app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host      = "0.0.0.0",
        port      = cfg.PORT,
        reload    = False,
        log_level = "info"
    )