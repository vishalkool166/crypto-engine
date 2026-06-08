import asyncio
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

_ws_clients:           set   = set()
_dashboard_clients:    set   = set()
_last_dashboard_data:  dict  = {}
_dashboard_push_task:  asyncio.Task = None


async def broadcast_price(coin: str, price: float):
    if not _ws_clients:
        return

    trade = state_manager.current_trade
    if not trade:
        return

    from api.formatters import fmt_price, fmt_pnl, fmt_pct, pnl_color

    is_long  = trade.direction == "LONG"
    upnl     = risk_guard.calculate_unrealized_pnl(
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


async def _build_dashboard_payload() -> dict:
    from datetime import datetime, timezone
    from database import SessionLocal, Trade as TradeModel
    from alerts.scanner import get_db_stats
    from data.cache import cache
    from scheduler import get_next_scan_epoch
    from api.formatters import (
        make_serializable, build_trade_data, build_risk_data,
        build_performance_data, build_radar_data, build_signal_queue,
        build_history_data, build_header_data
    )
    from trade.orders import get_current_price

    try:
        trade_state = "idle"
        trade_data  = None

        if not state_manager.is_idle:
            state_manager.refresh()
            trade = state_manager.current_trade
            if trade and trade.is_active:
                current     = get_current_price(trade.coin)
                trade_state = trade.state
                trade_data  = build_trade_data(trade, current)

        risk_stats = risk_guard.get_daily_stats()
        risk_data  = build_risk_data(risk_stats)
        stats      = get_db_stats()

        db = SessionLocal()
        try:
            trades_raw = db.query(TradeModel).filter(
                TradeModel.is_active == False
            ).order_by(TradeModel.closed_at.desc()).limit(10).all()

            trades_list = [{
                "coin":         t.coin,
                "direction":    t.direction,
                "grade":        t.grade,
                "pnl":          t.pnl,
                "outcome":      t.outcome,
                "close_reason": t.close_reason,
                "closed_at":    t.closed_at.isoformat() if t.closed_at else None
            } for t in trades_raw]
        finally:
            db.close()

        perf_data    = build_performance_data(stats, trades_list)
        history_data = build_history_data(trades_list)

        radar_data = []
        queue_data = []
        last_scan  = "--"

        cached_results = []
        for coin in cfg.COINS:
            cached = cache.get(f"signal_{coin}")
            if cached:
                cached_results.append(cached)

        if cached_results:
            cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            radar_data = build_radar_data(cached_results)
            queue_data = build_signal_queue(cached_results)
            last_scan  = "From cache"

        header_data = build_header_data(risk_stats, stats)

        return make_serializable({
            "type":            "dashboard",
            "state":           trade_state,
            "trade":           trade_data,
            "risk":            risk_data,
            "performance":     perf_data,
            "history":         history_data,
            "radar":           radar_data,
            "queue":           queue_data,
            "header":          header_data,
            "last_scan":       last_scan,
            "next_scan_epoch": get_next_scan_epoch(),
            "timestamp":       datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        log.error(f"Dashboard build error: {e}")
        return {"type": "dashboard", "error": str(e)}


async def push_dashboard():
    global _last_dashboard_data
    if not _dashboard_clients:
        return
    try:
        data    = await _build_dashboard_payload()
        payload = json.dumps(data)

        dead = set()
        for ws in _dashboard_clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        _dashboard_clients.difference_update(dead)

        _last_dashboard_data = data
        log.debug(f"Dashboard pushed to {len(_dashboard_clients)} clients")
    except Exception as e:
        log.error(f"Dashboard push error: {e}")


async def _dashboard_push_loop():
    while True:
        await asyncio.sleep(3)
        await push_dashboard()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _dashboard_push_task
    log.info("Starting Signal Engine v5...")

    price_feed.on_price(trade_manager.on_price_update)
    price_feed.on_price(broadcast_price)

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        log.info(f"Resumed trade: {trade.coin} {trade.direction} {trade.state}")
        await asyncio.sleep(1)
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

    _dashboard_push_task = asyncio.create_task(_dashboard_push_loop())

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

    if _dashboard_push_task:
        _dashboard_push_task.cancel()
        try:
            await _dashboard_push_task
        except asyncio.CancelledError:
            pass

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
    log.info(f"Price WS connected — clients: {len(_ws_clients)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)
        log.info(f"Price WS disconnected — clients: {len(_ws_clients)}")


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    await websocket.accept()
    _dashboard_clients.add(websocket)
    log.info(f"Dashboard WS connected — clients: {len(_dashboard_clients)}")

    try:
        if _last_dashboard_data:
            await websocket.send_text(json.dumps(_last_dashboard_data))
        else:
            data = await _build_dashboard_payload()
            await websocket.send_text(json.dumps(data))
    except Exception as e:
        log.error(f"Dashboard WS initial push error: {e}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _dashboard_clients.discard(websocket)
        log.info(f"Dashboard WS disconnected — clients: {len(_dashboard_clients)}")


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