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
            result = r.json()
            if r.status_code != 200 or not result.get("ok"):
                log.error(
                    "Telegram %s failed: HTTP %s; %s",
                    endpoint,
                    r.status_code,
                    result.get("description", "provider returned an unsuccessful response"),
                )
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
    # Keep the command's emoji and line breaks. Remove only control characters
    # Telegram cannot use safely, then escape text before restoring our markup.
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", message)
    clean = re.sub(r"[━─═]{3,}", "—", clean)
    clean = "\n".join(line.strip() for line in clean.splitlines())
    escaped = html.escape(clean)
    escaped = re.sub(r"\x60([^\x60\n]+)\x60", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<i>\1</i>", escaped)
    when = datetime.now(timezone(timedelta(hours=5,minutes=30))).strftime("%d %b %Y · %H:%M IST")
    return escaped + "\n\n<i>Signal Engine · " + cfg.TRADING_MODE.upper() + " · " + when + "</i>"

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


async def register_webhook() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/setWebhook",
                json    = {
                    "url":          f"{cfg.DOMAIN}/webhook/telegram",
                    "secret_token": cfg.WEBHOOK_SECRET,
                    "drop_pending_updates": False,
                    "allowed_updates": ["message"],
                },
                timeout = 10,
            )
            data = r.json()
            if data.get("ok"):
                log.info("Webhook registered: %s/webhook/telegram", cfg.DOMAIN)
                return True
            else:
                log.error("Webhook registration failed: %s", data.get("description", "Telegram rejected the request"))
                return False
    except Exception as e:
        log.error("Webhook registration transport failure: %s", type(e).__name__)
        return False


async def register_commands() -> bool:
    commands = [
        {"command": "start", "description": "Start here and view the command menu"},
        {"command": "ping", "description": "Test inbound command and reply delivery"},
        {"command": "help", "description": "Show every available operator command"},
        {"command": "health", "description": "Dependency health and data freshness"},
        {"command": "queue", "description": "Current signal queue"},
        {"command": "grade", "description": "Recorded performance by grade"},
        {"command": "status",       "description": "Bot status overview"},
        {"command": "scan",         "description": "Trigger manual scan"},
        {"command": "trades",       "description": "Active-account positions with observed P&L"},
        {"command": "position",     "description": "Deep dive on trade — /position ETH"},
        {"command": "journey",      "description": "Recorded price path — /journey 42"},
        {"command": "pending",      "description": "Review pending content drafts"},
        {"command": "discard",      "description": "Discard a draft — /discard 5"},
        {"command": "balance",      "description": "Account balance"},
        {"command": "profit",       "description": "Profit summary"},
        {"command": "coin",         "description": "Any coin analysis — /coin ETH"},
        {"command": "btc",          "description": "Bitcoin market overview"},
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
    ]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/setMyCommands",
                json    = {"commands": commands},
                timeout = 10,
            )
            result = r.json()
            if result.get("ok"):
                log.info("Telegram commands registered")
                return True
            log.error("Telegram command registration failed: %s", result.get("description", "Telegram rejected the request"))
            return False
    except Exception as e:
        log.error("Command registration transport failure: %s", type(e).__name__)
        return False
