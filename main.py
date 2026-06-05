import uvicorn
import logging
import asyncio
import re
import os
import tempfile

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from api.routes      import router
from database        import init_db
from scheduler       import start_scheduler, stop_scheduler
from trade.state     import state_manager
from alerts.telegram import send
from alerts.scanner  import scan_all_coins
from config          import cfg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s"
)

# ── SILENCE NOISY LOGGERS ──
logging.getLogger(
    "apscheduler.executors.default"
).setLevel(logging.WARNING)
logging.getLogger(
    "apscheduler.scheduler"
).setLevel(logging.WARNING)

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# TUNNEL URL HELPER
# reads cloudflared log file
# extracts public HTTPS URL
# sends to Telegram on startup
# ═══════════════════════════════════════════════════════
async def get_tunnel_url(
    timeout: int = 15
) -> str:
    """
    Reads cloudflared log file.
    Waits up to timeout seconds for URL.
    Returns URL string or empty string.
    """
    log_path = os.path.join(
        tempfile.gettempdir(),
        "cf.log"
    )
    log.info(
        f"Looking for tunnel URL in: {log_path}"
    )

    for i in range(timeout):
        try:
            with open(log_path, "r") as f:
                content = f.read()

            match = re.search(
                r'https://[a-z0-9-]+'
                r'\.trycloudflare\.com',
                content
            )
            if match:
                url = match.group(0)
                log.info(
                    f"Tunnel URL found: {url}"
                )
                return url

        except FileNotFoundError:
            pass
        except Exception as e:
            log.warning(
                f"Tunnel log read error: {e}"
            )

        await asyncio.sleep(1)

    log.warning(
        "Tunnel URL not found — "
        "running locally only"
    )
    return ""


# ═══════════════════════════════════════════════════════
# LIFESPAN
# ═══════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):

    # ── STARTUP ──
    log.info("Starting Signal Engine v5...")

    # 1. Init database
    init_db()
    log.info("Database initialized")

    # 2. Load active trade on restart
    if not state_manager.is_idle:
        trade = state_manager.current_trade
        log.info(
            f"Resumed trade: {trade.coin} "
            f"{trade.direction} {trade.state}"
        )
        await send(
            f"🔄 *Bot Restarted*\n\n"
            f"Resumed active trade:\n"
            f"`{trade.coin}USDT "
            f"{trade.direction}`\n"
            f"State: `{trade.state}`\n"
            f"Entry: `{trade.entry_price}`\n"
            f"SL:    `{trade.sl_price}`"
        )
    else:
        log.info("No active trade — idle")

    # 3. Start scheduler
    start_scheduler()
    log.info("Scheduler started")

    # 4. Telegram startup message
    await send(
        f"✅ *Signal Engine v5 Started*\n\n"
        f"Mode:     "
        f"`{'PAPER' if cfg.PAPER_TRADING else 'LIVE'}`\n"
        f"Capital:  `${cfg.CAPITAL}`\n"
        f"Leverage: `{cfg.LEVERAGE}x`\n"
        f"Coins:    `{', '.join(cfg.COINS)}`\n"
        f"Grades:   "
        f"`{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Max/day:  `{cfg.MAX_TRADES_PER_DAY} trades`\n"
        f"Daily cap:"
        f"`${cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT:.2f}`\n\n"
        f"Type /help for commands"
    )

    # 5. Send tunnel URL to Telegram
    # Only fires if cloudflared is running
    tunnel_url = await get_tunnel_url()
    if tunnel_url:
        await send(
            f"🌐 *Dashboard URL*\n\n"
            f"`{tunnel_url}`\n\n"
            f"👤 User: "
            f"`{os.getenv('DASH_USER', 'admin')}`\n"
            f"🔑 Pass: "
            f"`{os.getenv('DASH_PASS', 'changeme')}`\n\n"
            f"⚠️ URL changes on restart.\n"
            f"Save this message."
        )
        log.info(
            f"Dashboard URL sent to Telegram: "
            f"{tunnel_url}"
        )
    else:
        log.info(
            "No tunnel detected — "
            "dashboard available locally only: "
            f"http://localhost:{cfg.PORT}"
        )

    yield

    # ── SHUTDOWN ──
    stop_scheduler()

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        await send(
            f"⚠️ *Bot Shutting Down*\n\n"
            f"Active trade NOT closed:\n"
            f"`{trade.coin}USDT "
            f"{trade.direction}`\n"
            f"Entry: `{trade.entry_price}`\n"
            f"SL:    `{trade.sl_price}`\n\n"
            f"Bot will resume on restart."
        )
    else:
        await send(
            "🔴 *Signal Engine v5 Stopped*"
        )

    log.info("Signal Engine stopped")


# ═══════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════
app = FastAPI(
    title       = "Signal Engine v5",
    description = "Automated crypto signal + trade engine",
    version     = "5.0.0",
    lifespan    = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"]
)

# ── PROTECTED API ROUTES ──
# All /api/* endpoints require Basic Auth
app.include_router(
    router,
    prefix       = "/api",
)

# ── STATIC FILES ──
# Frontend served without auth
# Auth handled by browser on API calls
app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)


# ═══════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host      = "0.0.0.0",
        port      = cfg.PORT,
        reload    = cfg.ENV == "development",
        log_level = "info"
    )