import uvicorn
import logging
import json
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from api.routes       import router
from database         import init_db
from scheduler        import start_scheduler, stop_scheduler
from trade.state      import state_manager
from trade.price_feed import price_feed
from trade.manager    import trade_manager
from trade.risk       import risk_guard
from alerts.telegram  import send, register_webhook, handle_webhook
from config           import cfg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

_ws_clients: set = set()


async def broadcast_price(coin: str, price: float):
    log.info(f"broadcast called: {coin} {price:.4f} clients:{len(_ws_clients)}")
    if not _ws_clients:
        return

    trade = state_manager.current_trade
    if not trade:
        return

    from api.formatters import fmt_price, fmt_pnl, fmt_pct, pnl_color

    is_long = trade.direction == "LONG"
    upnl    = risk_guard.calculate_unrealized_pnl(
        direction     = trade.direction,
        entry_price   = trade.entry_price,
        current_price = price,
        pos_size      = trade.position_size
    )
    pnl_pct  = (upnl / cfg.CAPITAL * 100) if cfg.CAPITAL else 0
    move_pct = (price - trade.entry_price) / trade.entry_price * 100

    payload = json.dumps({
        "type":          "price",
        "coin":          coin,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Signal Engine v5...")

    price_feed.on_price(trade_manager.on_price_update)
    price_feed.on_price(broadcast_price)

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        log.info(f"Resumed trade: {trade.coin} {trade.direction} {trade.state}")
        await price_feed.start(trade.coin)
        await send(
            f"🔄 *Bot Restarted*\n\n"
            f"Resumed active trade:\n"
            f"`{trade.coin}USDT {trade.direction}`\n"
            f"State: `{trade.state}`\n"
            f"Entry: `{trade.entry_price}`\n"
            f"SL:    `{trade.sl_price}`"
        )
    else:
        log.info("No active trade — idle")

    start_scheduler()
    await register_webhook()

    await send(
        f"✅ *Signal Engine v5 Started*\n\n"
        f"Mode:     `{'PAPER' if cfg.PAPER_TRADING else 'LIVE'}`\n"
        f"Capital:  `${cfg.CAPITAL}`\n"
        f"Leverage: `{cfg.LEVERAGE}x`\n"
        f"Coins:    `{', '.join(cfg.COINS)}`\n"
        f"Grades:   `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Max/day:  `{cfg.MAX_TRADES_PER_DAY} trades`\n"
        f"Daily cap:`${cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT:.2f}`\n"
        f"Webhook:  `✅ Active`\n\n"
        f"Type /help for commands"
    )

    yield

    stop_scheduler()
    await price_feed.stop()

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        await send(
            f"⚠️ *Bot Shutting Down*\n\n"
            f"Active trade NOT closed:\n"
            f"`{trade.coin}USDT {trade.direction}`\n"
            f"Entry: `{trade.entry_price}`\n"
            f"SL:    `{trade.sl_price}`\n\n"
            f"Bot will resume on restart."
        )
    else:
        await send("🔴 *Signal Engine v5 Stopped*")

    log.info("Signal Engine stopped")


app = FastAPI(
    title       = "Signal Engine v5",
    description = "Automated crypto signal + trade engine",
    version     = "5.0.0",
    lifespan    = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.middleware("http")
async def no_cache_js(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.endswith(('.js', '.css')):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"]        = "no-cache"
        response.headers["Expires"]       = "0"
    return response


@app.websocket("/ws/price")
async def price_websocket(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    log.info(f"Frontend WS connected — clients: {len(_ws_clients)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)
        log.info(f"Frontend WS disconnected — clients: {len(_ws_clients)}")


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