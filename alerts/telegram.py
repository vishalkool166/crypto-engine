import httpx
import logging
from datetime import datetime, timezone, timedelta
from fastapi import Request
from config import cfg

log = logging.getLogger(__name__)

BASE   = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"
DOMAIN = cfg.DOMAIN

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def _now_ist_full() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %I:%M %p IST")


def _dashboard_button() -> dict:
    return {
        "inline_keyboard": [[{
            "text":    "Open Dashboard",
            "web_app": {"url": DOMAIN + "/app.html"}
        }]]
    }


async def _post(endpoint: str, payload: dict):
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured")
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/{endpoint}", json=payload, timeout=10)
            if r.status_code != 200:
                log.error(f"Telegram {endpoint} failed: {r.text}")
    except Exception as e:
        log.error(f"Telegram error: {e}")


async def send(message: str, reply_markup: dict = None):
    chunks = _split_message(message)
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id":    cfg.TELEGRAM_CHAT_ID,
            "text":       chunk,
            "parse_mode": "Markdown"
        }
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        await _post("sendMessage", payload)


def _split_message(text: str, limit: int = 4000) -> list[str]:
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


async def register_webhook():
    webhook_url = f"{DOMAIN}/webhook/telegram"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/setWebhook",
                json={
                    "url":          webhook_url,
                    "secret_token": cfg.WEBHOOK_SECRET
                },
                timeout=10
            )
            data = r.json()
            if data.get("ok"):
                log.info(f"Webhook registered: {webhook_url}")
            else:
                log.error(f"Webhook failed: {data}")
    except Exception as e:
        log.error(f"Webhook register error: {e}")


async def register_commands():
    commands = [
        {"command": "start", "description": "Open Signal Engine dashboard"},
        {"command": "help",  "description": "Show help"},
    ]
    try:
        async with httpx.AsyncClient() as client:
            r    = await client.post(
                f"{BASE}/setMyCommands",
                json={"commands": commands},
                timeout=10
            )
            data = r.json()
            if data.get("ok"):
                log.info("Telegram commands registered")
    except Exception as e:
        log.error(f"Commands register error: {e}")


async def handle_webhook(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if cfg.WEBHOOK_SECRET and secret != cfg.WEBHOOK_SECRET:
        log.warning("Webhook secret mismatch — rejected")
        return

    try:
        data    = await request.json()
        msg     = data.get("message", {})
        text    = msg.get("text", "").strip().lower()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if chat_id != str(cfg.TELEGRAM_CHAT_ID):
            return

        if text in ("/start", "/help"):
            await _cmd_start()

    except Exception as e:
        log.error(f"Webhook handler error: {e}")


async def _cmd_start():
    mode = "LIVE" if not cfg.PAPER_TRADING else "PAPER"
    await send(
        f"*Signal Engine v5*\n"
        f"_{_now_ist_full()}_\n\n"
        f"Mode: `{mode}`\n"
        f"Coins: `{len(cfg.COINS)} scanning`\n"
        f"Grades: `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n\n"
        f"Tap the button below to open your dashboard.",
        reply_markup=_dashboard_button()
    )


async def send_signal(signal: dict, coin: str, regime: str, session: str):
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return
    if signal.get("direction") not in ["LONG", "SHORT"]:
        return
    if not signal.get("entry"):
        return

    grade     = signal.get("grade", "?")
    direction = signal.get("direction", "?")
    score     = signal.get("score", 0)
    entry     = signal.get("entry", 0)
    sl        = signal.get("sl", 0)
    tp1       = signal.get("tp1", 0)
    sl_pct    = signal.get("sl_pct", 0)
    risk_amt  = signal.get("risk_amt", 0)
    tp_mult   = signal.get("tp_mult", 1.5)
    actual_rr = signal.get("actual_rr", 0)
    ml_prob   = signal.get("ml_probability")

    explanation = signal.get("explanation", {})
    thesis      = explanation.get("thesis", "")
    conf_label  = explanation.get("confidence_label", "")

    grade_icon = "A+" if grade == "A+" else "A" if grade == "A" else "B"
    dir_arrow  = "LONG" if direction == "LONG" else "SHORT"

    ml_line = ""
    if ml_prob is not None:
        ml_line = f"ML:      `{ml_prob*100:.1f}%`\n"

    conf_line = f"Conf:    `{conf_label} ({score}/100)`\n" if conf_label else f"Score:   `{score}/100`\n"

    grade_note = ""
    if grade == "B":
        grade_note = "_Grade B — paper mode only_\n\n"

    await send(
        f"*Grade {grade_icon} — {dir_arrow}*\n\n"
        f"*{coin}USDT*\n"
        f"{conf_line}"
        f"{ml_line}"
        f"Regime:  `{regime}`\n"
        f"Session: `{session}`\n"
        f"Time:    `{_now_ist()}`\n\n"
        f"Entry:   `{entry:.4f}`\n"
        f"SL:      `{sl:.4f}` ({sl_pct:.2f}%)\n"
        f"TP:      `{tp1:.4f}` ({tp_mult}x)\n"
        f"R:R:     `1:{actual_rr}`\n"
        f"Risk:    `${risk_amt:.2f}`\n\n"
        f"{grade_note}"
        f"{('_' + thesis + '_') if thesis else ''}\n\n"
        f"_Forwarded to Freqtrade._",
        reply_markup=_dashboard_button()
    )


async def send_scan_summary(results: list):
    from alerts.utils import categorize_results
    from scheduler import get_next_scan_time

    cats      = categorize_results(results)
    tradeable = cats["tradeable"]
    watching  = cats["watching"]
    next_scan = get_next_scan_time()

    if tradeable:
        lines = [
            f"*Scan Complete — {_now_ist()}*\n"
            f"{len(tradeable)} tradeable signal(s)\n\n"
        ]
        for r in tradeable[:3]:
            g         = r.get("grade", "?")
            direction = r.get("direction", "?")
            score     = r.get("score", 0)
            coin      = r.get("coin", "?")
            actual_rr = r.get("actual_rr", 0)
            ml_prob   = r.get("ml_probability")
            ml_str    = f" · ML:`{ml_prob*100:.0f}%`" if ml_prob is not None else ""
            lines.append(
                f"*{coin}* — Grade {g} ({score}/100){ml_str}\n"
                f"{direction} · R:R `1:{actual_rr}`\n"
            )
        lines.append(f"\nNext scan: `{next_scan}`")
        await send("\n".join(lines), reply_markup=_dashboard_button())
        return

    lines = [f"*No Tradeable Signals — {_now_ist()}*\n\n"]

    if watching:
        lines.append("*Closest Setups:*")
        for r in watching[:2]:
            d      = r.get("direction", "?")
            s      = r.get("score", 0)
            hards  = (r.get("no_trade", {}) or {}).get("hard_blocks", [])
            reason = hards[0]["reason"] if hards else "setup building"
            lines.append(f"`{r['coin']}` — B ({s}/100)\n_{reason}_\n")

    lines.append(f"\nNext scan: `{next_scan}`")
    await send("\n".join(lines), reply_markup=_dashboard_button())