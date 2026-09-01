import logging
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
                log.error("Telegram %s failed: %s", endpoint, r.text)
    except Exception as e:
        log.error("Telegram error: %s", e)


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


async def send(message: str) -> None:
    for chunk in _split_message(message):
        await _post("sendMessage", {
            "chat_id":    cfg.TELEGRAM_CHAT_ID,
            "text":       chunk,
            "parse_mode": "Markdown",
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
                    "caption":    caption,
                    "parse_mode": "Markdown",
                },
                files   = {"photo": ("chart.png", photo_bytes, "image/png")},
                timeout = 30,
            )
            if r.status_code != 200:
                log.error("Photo send failed: %s", r.text)
    except Exception as e:
        log.error("Send photo error: %s", e)


async def register_webhook() -> None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/setWebhook",
                json    = {
                    "url":          f"{cfg.DOMAIN}/webhook/telegram",
                    "secret_token": cfg.WEBHOOK_SECRET,
                    "drop_pending_updates": True,
                },
                timeout = 10,
            )
            data = r.json()
            if data.get("ok"):
                log.info("Webhook registered: %s/webhook/telegram", cfg.DOMAIN)
            else:
                log.error("Webhook failed: %s", data)
    except Exception as e:
        log.error("Webhook register error: %s", e)


async def register_commands() -> None:
    commands = [
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
        {"command": "backtest",     "description": "Backtest a coin — /backtest BTC"},
        {"command": "backfill",     "description": "Backfill candle data — /backfill BTC"},
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
        log.error("Commands register error: %s", e)