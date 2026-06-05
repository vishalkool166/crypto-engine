import uvicorn
import logging
import asyncio
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from api.routes      import router
from database        import init_db
from scheduler       import start_scheduler, stop_scheduler
from trade.state     import state_manager
from alerts.telegram import send, register_webhook, handle_webhook
from config          import cfg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)
logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)

log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    log.info("Starting Signal Engine v5...")

    init_db()
    log.info("Database initialized")

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        log.info(f"Resumed trade: {trade.coin} {trade.direction} {trade.state}")
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
    log.info("Scheduler started")

    # Register Telegram webhook
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

    # ── SHUTDOWN ──
    stop_scheduler()
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

# ── TELEGRAM WEBHOOK ROUTE ──
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    await handle_webhook(request)
    return JSONResponse(content={"ok": True})

# ── API ROUTES ──
app.include_router(router, prefix="/api")

# ── STATIC FILES ──
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
        reload    = cfg.ENV == "development",
        log_level = "info"
    )