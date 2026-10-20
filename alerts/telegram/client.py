import logging
import html
import re
from datetime import datetime, timezone, timedelta
import httpx
from config import cfg

log = logging.getLogger(__name__)

BASE = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"


async def _post(endpoint: str, payload: dict) -> None:
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/{endpoint}",
                json    = payload,
                timeout = 10,
            )
            if r.status_code != 200:
                log.error("Telegram %s failed: HTTP %s", endpoint, r.status_code)
    except Exception as e:
        log.error("Telegram transport failure: %s", type(e).__name__)


def _split_message(text: str, limit: int = 4000) -> list:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def render_message(message: str) -> str:
    # Escape dynamic content before converting the retained command markup.
    clean = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", message)
    clean = re.sub(r"[━─═]{3,}", "—", clean)
    clean = "\n".join(line.strip() for line in clean.splitlines())
    escaped = html.escape(clean)
    escaped = re.sub(r"\x60([^\x60\n]+)\x60", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", escaped)
    when = datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime("%d %b %Y · %H:%M IST")
    return escaped + "\n\n<i>Signal Engine · PAPER · " + when + "</i>"

async def send(message: str) -> None:
    for chunk in _split_message(message, limit=3000):
        await _post("sendMessage", {
            "chat_id": cfg.TELEGRAM_CHAT_ID,
            "text": render_message(chunk),
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        })


async def send_photo(chat_id: str, photo_path: str, caption: str = "") -> None:
    try:
        with open(photo_path, "rb") as f:
            photo_bytes = f.read()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/sendPhoto",
                data  = {
                    "chat_id":    chat_id,
                    "caption":    render_message(caption[:700]),
                    "parse_mode": "HTML",
                },
                files   = {"photo": ("chart.png", photo_bytes, "image/png")},
                timeout = 30,
            )
            if r.status_code != 200:
                log.error("Photo send failed: HTTP %s", r.status_code)
    except Exception as e:
        log.error("Photo transport failure: %s", type(e).__name__)


async def register_webhook() -> None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/setWebhook",
                json    = {
                    "url":          f"{cfg.DOMAIN}/webhook/telegram",
                    "secret_token": cfg.WEBHOOK_SECRET,
                    "drop_pending_updates": False,
                },
                timeout = 10,
            )
            data = r.json()
            if data.get("ok"):
                log.info("Webhook registered: %s/webhook/telegram", cfg.DOMAIN)
            else:
                log.error("Webhook failed: %s", data)
    except Exception as e:
        log.error("Webhook registration transport failure: %s", type(e).__name__)


async def register_commands() -> None:
    commands = [
        {"command": "health", "description": "Dependency health and data freshness"},
        {"command": "queue", "description": "Current signal queue"},
        {"command": "grade", "description": "Recorded performance by grade"},
        {"command": "status",       "description": "Bot status overview"},
        {"command": "scan",         "description": "Trigger manual scan"},
        {"command": "trades",       "description": "Open trades with live PnL"},
        {"command": "position",     "description": "Deep dive on trade — /position ETH"},
        {"command": "balance",      "description": "Account balance"},
        {"command": "profit",       "description": "Profit summary"},
        {"command": "coin",         "description": "Any coin analysis — /coin ETH"},
        {"command": "funding",      "description": "Funding rates"},
        {"command": "fear",         "description": "Fear and greed index"},
        {"command": "brief",        "description": "Full market report"},
        {"command": "pnl",          "description": "All time PnL"},
        {"command": "daily",        "description": "Today summary"},
        {"command": "stats",        "description": "Full all time stats"},
        {"command": "history",      "description": "Last 5 signals"},
        {"command": "backtest",     "description": "Backtest a coin — /backtest ETH"},
        {"command": "backfill",     "description": "Backfill candle data — /backfill ETH"},
        {"command": "candles",      "description": "Candle data status per coin"},
        {"command": "mode",         "description": "Current bot config"},
        {"command": "performance",  "description": "Performance by version and session"},
        {"command": "india",        "description": "Indian market status and signals"},
        {"command": "orb",          "description": "BANKNIFTY opening range levels"},
        {"command": "indianstats",  "description": "Indian strategy performance"},
        {"command": "help",         "description": "Full command list"},
    ]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/setMyCommands",
                json    = {"commands": commands},
                timeout = 10,
            )
            if r.json().get("ok"):
                log.info("Telegram commands registered")
    except Exception as e:
        log.error("Command registration transport failure: %s", type(e).__name__)