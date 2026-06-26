import asyncio
import hashlib
import json
import logging
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.routes       import router, build_dashboard_payload
from api.freqtrade    import router as ft_router, start_ft_ws, stop_ft_ws, on_ft_event
from database         import init_db
from scheduler        import start_scheduler, stop_scheduler
from alerts.telegram  import send, register_webhook, handle_webhook
from config           import cfg, _bootstrap_secrets
from events           import on_event, emit
import runtime_state  as rs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

log       = logging.getLogger(__name__)
templates = Jinja2Templates(directory="frontend")

_dashboard_clients:   set          = set()
_last_payload_hash:   str          = ""
_dashboard_push_task: asyncio.Task = None

limiter = Limiter(key_func=get_remote_address)


async def _build_ws_payload() -> dict:
    from api.dashboard import get_summary, get_signals_data, get_ticker_bar
    return {
        "type":    "dashboard",
        "summary": get_summary(),
        "signals": get_signals_data(),
        "ticker":  get_ticker_bar(),
    }


async def _push_to_clients(payload_str: str):
    dead = set()
    for ws in _dashboard_clients:
        try:
            await ws.send_text(payload_str)
        except Exception:
            dead.add(ws)
    _dashboard_clients.difference_update(dead)


async def push_event(event_type: str, data: dict = None):
    global _last_payload_hash
    if not _dashboard_clients:
        return
    try:
        payload      = await _build_ws_payload()
        payload_str  = json.dumps(payload)
        payload_hash = hashlib.md5(payload_str.encode()).hexdigest()

        if payload_hash == _last_payload_hash and event_type == "ping":
            return

        _last_payload_hash = payload_hash
        await _push_to_clients(payload_str)

    except Exception as e:
        log.error(f"push_event error: {e}")


async def _push_ft_update(event_type: str, data: dict = None):
    if not _dashboard_clients:
        return
    try:
        from api.freqtrade import _ft_get_safe
        from database import SessionLocal
        from database import Signal as SignalModel

        status, profit, balance, config = await asyncio.gather(
            _ft_get_safe("/status"),
            _ft_get_safe("/profit"),
            _ft_get_safe("/balance"),
            _ft_get_safe("/show_config"),
        )

        bot_state = "unknown"
        if config:
            bot_state = config.get("state", "unknown")

        trades_with_health = []
        if status and isinstance(status, list):
            tp1_map = {}
            sl_map  = {}

            try:
                with SessionLocal() as db:
                    for trade in status:
                        pair      = trade.get("pair", "")
                        coin      = pair.replace("/USDT:USDT", "").replace("/USDT", "")
                        is_short  = trade.get("is_short", False)
                        direction = "SHORT" if is_short else "LONG"

                        signal = db.query(SignalModel).filter(
                            SignalModel.coin      == coin,
                            SignalModel.direction == direction,
                            SignalModel.outcome   == "pending"
                        ).order_by(SignalModel.timestamp.desc()).first()

                        if not signal:
                            signal = db.query(SignalModel).filter(
                                SignalModel.coin      == coin,
                                SignalModel.direction == direction
                            ).order_by(SignalModel.timestamp.desc()).first()

                        if signal:
                            if signal.tp1: tp1_map[coin] = float(signal.tp1)
                            if signal.sl:  sl_map[coin]  = float(signal.sl)

            except Exception as e:
                log.warning(f"ft push tp1/sl error: {e}")

            for trade in status:
                pair = trade.get("pair", "")
                coin = pair.replace("/USDT:USDT", "").replace("/USDT", "")

                health = None
                try:
                    from trade.health_monitor import get_health_from_redis
                    health = get_health_from_redis(coin)
                except Exception:
                    pass

                trade_copy              = dict(trade)
                trade_copy["health"]    = health
                trade_copy["tp1"]       = tp1_map.get(coin, None)
                trade_copy["sl_signal"] = sl_map.get(coin, None)
                trades_with_health.append(trade_copy)

        payload = json.dumps({
            "type":      "ft_update",
            "event":     event_type,
            "status":    trades_with_health,
            "profit":    profit    if profit    else {},
            "balance":   balance   if balance   else {},
            "bot_state": bot_state
        })

        await _push_to_clients(payload)

    except Exception as e:
        log.error(f"_push_ft_update error: {e}")


async def _on_ft_event(event_type: str, data: dict):
    log.info(f"FT event received: {event_type}")

    push_types = {
        "entry_fill",
        "exit_fill",
        "trade",
        "status",
    }

    if event_type in push_types:
        await _push_ft_update(event_type, data)


async def _dashboard_push_loop():
    while True:
        await asyncio.sleep(15)
        if _dashboard_clients:
            await push_event("ping")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _dashboard_push_task

    rs.load()
    _bootstrap_secrets()

    on_event(push_event)
    on_ft_event(_on_ft_event)

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

    start_scheduler()
    await register_webhook()

    from alerts.telegram import register_commands
    await register_commands()

    await start_ft_ws()

    mode   = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"
    grades = ", ".join(cfg.MIN_GRADE_TO_TRADE)

    await send(
        f"✅ *Signal Engine v5 Started*\n\n"
        f"Mode:     `{mode}`\n"
        f"Coins:    `{len(cfg.COINS)} coins`\n"
        f"Grades:   `{grades}`\n"
        f"Webhook:  `✅ Active`\n"
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

    await stop_ft_ws()
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

allowed_origins = [cfg.DOMAIN, "http://localhost:8000", "http://127.0.0.1:8000"]
allowed_origins = [o for o in allowed_origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins     = allowed_origins,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
    allow_credentials = True
)


@app.middleware("http")
async def no_cache_js(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.endswith(('.js', '.css')):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"]        = "no-cache"
        response.headers["Expires"]       = "0"
    return response


@app.get("/auth/setup")
async def auth_setup(request: Request):
    from auth import setup_status, get_qr_svg, get_qr_png_bytes
    status = setup_status()

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
            return JSONResponse(
                status_code = 401,
                content     = {"success": False, "reason": result["reason"]}
            )
    except Exception as e:
        log.error(f"Login error: {e}")
        raise HTTPException(500, "Login failed")


@app.post("/auth/request-totp")
async def request_totp_via_telegram(request: Request):
    try:
        if not cfg.TOTP_SECRET:
            return JSONResponse(
                status_code = 400,
                content     = {"success": False, "reason": "TOTP not configured"}
            )
        import pyotp
        from alerts.telegram import send
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
async def auth_reset_password(request: Request):
    try:
        body         = await request.json()
        totp_code    = body.get("totp_code", "")
        new_password = body.get("new_password", "")
        ip           = request.client.host if request.client else ""

        from auth import reset_password_with_totp
        result = reset_password_with_totp(totp_code, new_password, ip)
        return JSONResponse(content=result)
    except Exception as e:
        log.error(f"Reset password error: {e}")
        raise HTTPException(500, "Reset failed")


@app.get("/auth/logout")
async def auth_logout():
    response = JSONResponse(content={"success": True})
    response.delete_cookie("se_token")
    return response


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
                    content     = {"success": False, "reason": "Password too short"}
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
async def auth_regenerate_totp():
    try:
        from auth import regenerate_totp
        new_secret = regenerate_totp()
        log.info("TOTP secret regenerated")
        return JSONResponse(content={"success": True, "secret": new_secret})
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


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    _dashboard_clients.add(websocket)

    try:
        initial = await build_dashboard_payload()
        await websocket.send_text(json.dumps(initial))
    except Exception as e:
        log.error(f"Dashboard WS initial push error: {e}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _dashboard_clients.discard(websocket)
    except Exception:
        _dashboard_clients.discard(websocket)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    await handle_webhook(request)
    return JSONResponse(content={"ok": True})


app.include_router(router,    prefix="/api")
app.include_router(ft_router, prefix="/api")

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