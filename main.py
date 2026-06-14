import asyncio
import hashlib
import json
import logging
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, Response
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from api.routes       import router, build_dashboard_payload
from database         import init_db
from scheduler        import start_scheduler, stop_scheduler
from trade.state      import state_manager
from trade.price_feed import price_feed
from trade.manager    import trade_manager
from trade.risk       import risk_guard
from alerts.telegram  import send, register_webhook, handle_webhook
from config           import cfg, _bootstrap_secrets
import runtime_state  as rs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

_ws_clients:          set          = set()
_dashboard_clients:   set          = set()
_last_dashboard_data: dict         = {}
_last_payload_hash:   str          = ""
_dashboard_push_task: asyncio.Task = None

limiter = Limiter(key_func=get_remote_address)


async def broadcast_price(coin: str, price: float):
    if not _ws_clients:
        return

    active_trades = state_manager.active_trades
    if not active_trades:
        return

    trade = next((t for t in active_trades.values() if t.coin == coin), None)
    if not trade:
        return

    from api.formatters import fmt_price, fmt_pnl, fmt_pct, pnl_color
    from trade.risk import get_current_tier

    tier    = get_current_tier()
    capital = tier["balance"] or cfg.CAPITAL
    is_long = trade.direction == "LONG"

    upnl = risk_guard.calculate_unrealized_pnl(
        direction     = trade.direction,
        entry_price   = trade.entry_price,
        current_price = price,
        pos_size      = trade.position_size
    )
    pnl_pct  = (upnl / capital * 100) if capital else 0
    move_pct = (price - trade.entry_price) / trade.entry_price * 100

    payload = json.dumps({
        "type":          "price",
        "coin":          coin,
        "trade_id":      trade.id,
        "price":         fmt_price(price),
        "price_raw":     price,
        "pnl":           fmt_pnl(upnl),
        "pnl_color":     pnl_color(upnl),
        "pnl_pct":       fmt_pct(pnl_pct) + " of capital",
        "move_pct":      fmt_pct(move_pct),
        "move_color":    pnl_color(move_pct),
        "current_color": "#248a3d" if (
            (is_long     and price > trade.entry_price) or
            (not is_long and price < trade.entry_price)
        ) else "#c0392b"
    })

    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


async def push_dashboard():
    global _last_dashboard_data, _last_payload_hash
    if not _dashboard_clients:
        return
    try:
        data         = await build_dashboard_payload()
        payload_str  = json.dumps(data)
        payload_hash = hashlib.md5(payload_str.encode()).hexdigest()

        if payload_hash == _last_payload_hash:
            return

        _last_payload_hash   = payload_hash
        _last_dashboard_data = data

        dead = set()
        for ws in _dashboard_clients:
            try:
                await ws.send_text(payload_str)
            except Exception:
                dead.add(ws)
        _dashboard_clients.difference_update(dead)

    except Exception as e:
        log.error(f"Dashboard push error: {e}")


async def _dashboard_push_loop():
    while True:
        await asyncio.sleep(3)
        await push_dashboard()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _dashboard_push_task

    rs.load()

    _bootstrap_secrets()

    from auth import setup_status
    status = setup_status()
    if not status["setup_complete"]:
        log.warning("=" * 60)
        log.warning("FIRST RUN — Dashboard password not set!")
        log.warning("Visit /auth/setup to complete setup")
        log.warning(f"TOTP URI: {status['totp_uri']}")
        log.warning(f"API Key:  {status['api_key']}")
        log.warning("=" * 60)

    if rs.was_crash():
        log.warning("Crash detected on last run — forcing paper mode")
        rs.set_trading_mode("paper")
        cfg.TRADING_MODE  = "paper"
        cfg.PAPER_TRADING = True
        rs.mark_clean_shutdown()

    from data.fetcher import get_live_balance
    from trade.risk import get_tier_config
    balance = await get_live_balance()
    if balance > 0:
        rs.set_balance_cache(balance)
        tier = get_tier_config(balance)
        rs.set_tier_config(tier)
        cfg.CAPITAL = balance
        log.info(f"Balance loaded: ${balance:.2f} Tier:{tier['tier']}")
    else:
        log.warning("Balance fetch failed — using cached/default")
        cached_bal = rs.get_balance_cache().get("balance", 0)
        if cached_bal > 0:
            cfg.CAPITAL = cached_bal

    price_feed.on_price(trade_manager.on_price_update)
    price_feed.on_price(broadcast_price)

    if not state_manager.is_idle:
        for trade in state_manager.active_trades.values():
            log.info(f"Resumed trade: {trade.coin} {trade.direction} {trade.state}")
            await price_feed.start(trade.coin)
            await trade_manager.reconcile_orders(trade)

        active_list = ", ".join(
            f"{t.coin} {t.direction}" for t in state_manager.active_trades.values()
        )
        await send(
            f"🔄 *Bot Restarted*\n\n"
            f"Resumed {len(state_manager.active_trades)} active trade(s):\n"
            f"`{active_list}`\n"
            f"Mode: `{'PAPER' if cfg.PAPER_TRADING else 'LIVE'}`"
        )
    else:
        log.info("No active trades — idle")

    _dashboard_push_task = asyncio.create_task(_dashboard_push_loop())

    start_scheduler()
    await register_webhook()

    from alerts.telegram import register_commands
    await register_commands()

    from trade.risk import get_current_tier
    tier = get_current_tier()

    await send(
        f"✅ *Signal Engine v5 Started*\n\n"
        f"Mode:     `{'🔴 LIVE' if not cfg.PAPER_TRADING else '🔵 PAPER'}`\n"
        f"Balance:  `${tier['balance']:.2f}`\n"
        f"Tier:     `{tier['tier']}`\n"
        f"Leverage: `{tier['leverage']}x`\n"
        f"Risk:     `{tier['risk_pct']*100:.0f}%`\n"
        f"Max trades: `{tier['max_trades']}`\n"
        f"Coins:    `{len(cfg.COINS)} coins`\n"
        f"Grades:   `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Webhook:  `✅ Active`\n\n"
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

    stop_scheduler()
    await price_feed.stop()

    if not state_manager.is_idle:
        active_list = ", ".join(
            f"{t.coin} {t.direction}" for t in state_manager.active_trades.values()
        )
        await send(
            f"⚠️ *Bot Shutting Down*\n\n"
            f"Active trades NOT closed:\n"
            f"`{active_list}`\n\n"
            f"Bot will resume on restart."
        )
    else:
        await send("🔴 *Signal Engine v5 Stopped*")

    rs.mark_clean_shutdown()
    log.info("Signal Engine stopped")


app = FastAPI(
    title       = "Signal Engine v5",
    description = "Automated crypto signal + trade engine",
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


@app.post("/auth/login")
async def auth_login(request: Request):
    try:
        body     = await request.json()
        password = body.get("password", "")
        totp     = body.get("totp_code", "")
        ip       = request.client.host if request.client else ""

        from auth import validate_login
        result = validate_login(password, totp, ip)

        if result["success"]:
            response = JSONResponse(content={"success": True})
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


@app.get("/auth/logout")
async def auth_logout():
    response = JSONResponse(content={"success": True})
    response.delete_cookie("se_token")
    return response


@app.get("/auth/setup")
async def auth_setup(request: Request):
    from auth import setup_status, get_qr_svg
    status = setup_status()

    qr_svg = ""
    if cfg.TOTP_SECRET:
        try:
            qr_svg = get_qr_svg()
        except Exception as e:
            log.error(f"QR generation error: {e}")

    html = f"""<!DOCTYPE html>
<html>
<head>
<title>Signal Engine v5 — Setup</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: -apple-system, sans-serif; background: #f5f5f7; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
  .card {{ background: white; border-radius: 18px; padding: 40px; max-width: 480px; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,0.12); }}
  h1 {{ font-size: 22px; margin-bottom: 8px; }}
  p {{ color: #6e6e73; font-size: 14px; margin-bottom: 24px; }}
  .qr {{ text-align: center; margin: 24px 0; }}
  .info {{ background: #f5f5f7; border-radius: 12px; padding: 16px; margin-bottom: 16px; font-size: 13px; }}
  .info code {{ background: #e8e8ed; padding: 2px 6px; border-radius: 4px; font-size: 12px; word-break: break-all; }}
  label {{ font-size: 13px; font-weight: 600; display: block; margin-bottom: 6px; }}
  input {{ width: 100%; padding: 12px; border: 1px solid rgba(0,0,0,0.1); border-radius: 10px; font-size: 14px; box-sizing: border-box; margin-bottom: 16px; }}
  button {{ width: 100%; padding: 14px; background: #0071e3; color: white; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; }}
  button:hover {{ background: #0077ed; }}
  .status {{ font-size: 12px; margin-top: 8px; padding: 8px 12px; border-radius: 8px; }}
  .ok {{ background: rgba(52,199,89,0.1); color: #248a3d; }}
  .warn {{ background: rgba(255,149,0,0.1); color: #e8820c; }}
  #msg {{ margin-top: 16px; font-size: 13px; text-align: center; }}
</style>
</head>
<body>
<div class="card">
  <h1>⚡ Signal Engine v5</h1>
  <p>First run setup — configure your dashboard password and TOTP authenticator.</p>

  <div class="info">
    <div>TOTP Secret: <code>{cfg.TOTP_SECRET}</code></div>
    <div style="margin-top:8px">API Key: <code>{cfg.DASHBOARD_API_KEY}</code></div>
  </div>

  {'<div class="qr">' + qr_svg + '</div>' if qr_svg else '<p style="color:#ff3b30">QR generation failed — use secret above manually</p>'}

  <div class="info">
    <div>Scan the QR code with Google Authenticator, Authy, or any TOTP app.</div>
    <div style="margin-top:8px">TOTP URI: <code>{status['totp_uri']}</code></div>
  </div>

  <div class="status {'ok' if status['password_set'] else 'warn'}">
    Password: {'✅ Set' if status['password_set'] else '⚠️ Not set — fill form below'}
  </div>
  <div class="status {'ok' if status['totp_secret_set'] else 'warn'}" style="margin-top:8px">
    TOTP: {'✅ Secret generated' if status['totp_secret_set'] else '⚠️ Not configured'}
  </div>

  <div style="margin-top:24px">
    <label>Set Dashboard Password</label>
    <input type="password" id="pw" placeholder="Choose a strong password">
    <label>Confirm Password</label>
    <input type="password" id="pw2" placeholder="Confirm password">
    <button onclick="setPassword()">Set Password</button>
    <div id="msg"></div>
  </div>
</div>

<script>
async function setPassword() {{
  const pw  = document.getElementById('pw').value
  const pw2 = document.getElementById('pw2').value
  const msg = document.getElementById('msg')

  if (!pw || pw.length < 8) {{ msg.textContent = '❌ Password must be at least 8 characters'; msg.style.color='#ff3b30'; return }}
  if (pw !== pw2) {{ msg.textContent = '❌ Passwords do not match'; msg.style.color='#ff3b30'; return }}

  const res  = await fetch('/auth/set-password', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{password: pw}})
  }})
  const data = await res.json()

  if (data.success) {{
    msg.textContent = '✅ Password set! You can now login at /'
    msg.style.color = '#248a3d'
  }} else {{
    msg.textContent = '❌ ' + (data.reason || 'Failed')
    msg.style.color = '#ff3b30'
  }}
}}
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.post("/auth/set-password")
async def auth_set_password(request: Request):
    try:
        body     = await request.json()
        password = body.get("password", "")
        if len(password) < 8:
            return JSONResponse(status_code=400, content={"success": False, "reason": "Password too short"})
        from auth import set_password
        set_password(password)
        log.info("Dashboard password set via /auth/setup")
        return JSONResponse(content={"success": True})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/auth/qr.png")
async def auth_qr_png():
    from auth import get_qr_png_bytes
    try:
        png = get_qr_png_bytes()
        return Response(content=png, media_type="image/png")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.websocket("/ws/price")
async def price_websocket(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    log.info(f"Price WS connected — clients: {len(_ws_clients)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    _dashboard_clients.add(websocket)
    log.info(f"Dashboard WS connected — clients: {len(_dashboard_clients)}")

    try:
        if _last_dashboard_data:
            await websocket.send_text(json.dumps(_last_dashboard_data))
        else:
            data = await build_dashboard_payload()
            await websocket.send_text(json.dumps(data))
    except Exception as e:
        log.error(f"Dashboard WS initial push error: {e}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _dashboard_clients.discard(websocket)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    await handle_webhook(request)
    return JSONResponse(content={"ok": True})


app.include_router(router, prefix="/api")

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