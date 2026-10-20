import logging
import hmac
import hashlib
import os
from fastapi import Request, HTTPException
from config import cfg

log = logging.getLogger(__name__)


async def handle_webhook(request: Request) -> None:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not cfg.WEBHOOK_SECRET or not hmac.compare_digest(secret, cfg.WEBHOOK_SECRET):
        log.warning("Telegram webhook authentication failed")
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        data    = await request.json()
        if not isinstance(data, dict) or not _claim_update(data.get("update_id")):
            log.warning("Telegram update rejected: invalid, replayed, or dedupe unavailable")
            return
        msg     = data.get("message", {})
        if not isinstance(msg, dict):
            return
        text    = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id != str(cfg.TELEGRAM_CHAT_ID):
            return
        sender = msg.get("from", {})
        sender_id = str(sender.get("id", "")) if isinstance(sender, dict) else ""
        if not sender_id:
            log.warning("Telegram update rejected: missing sender identity")
            return
        if _is_mutating_command(text) and not _is_authorized_operator(sender_id, msg.get("chat", {})):
            _audit_command(text, sender_id, False)
            log.warning("Telegram mutating command denied for sender id hash=%s",
                        hashlib.sha256(sender_id.encode()).hexdigest()[:12])
            return
        if _is_mutating_command(text):
            if not _audit_command(text, sender_id, True):
                log.error("Telegram mutating command blocked: audit storage unavailable")
                return
        elif text.startswith("/"):
            _audit_command(text, sender_id, True)
        await _handle_command(text, chat_id)
    except Exception as e:
        log.error("Webhook handler error: %s", type(e).__name__)


def _claim_update(update_id) -> bool:
    """Claim a Telegram update exactly once through shared Redis state.

    Redis outage deliberately disables webhook command processing. The local
    process cannot safely provide replay protection across restarts/workers.
    """
    if not isinstance(update_id, int) or isinstance(update_id, bool) or update_id < 0:
        return False
    try:
        from redis_client import get_redis
        store = get_redis()
        if not store:
            return False
        result = store.set(f"telegram:webhook:update:{update_id}", "1", ex=7 * 86400, nx=True)
        return bool(result)
    except Exception:
        return False


def _command_name(text: str) -> str:
    token = (text or "").strip().split(maxsplit=1)[0].lower() if (text or "").strip() else ""
    return token.split("@", 1)[0]


def _is_mutating_command(text: str) -> bool:
    return _command_name(text) in {"/scan", "/backfill", "/discard"}


def _is_authorized_operator(sender_id: str, chat: dict) -> bool:
    configured = {
        value.strip() for value in os.getenv("TELEGRAM_ADMIN_USER_IDS", "").split(",")
        if value.strip()
    }
    if sender_id in configured:
        return True
    # A one-to-one private chat has one sender. The configured chat ID can be
    # used as a narrow legacy fallback; group members never inherit it.
    return (isinstance(chat, dict) and chat.get("type") == "private"
            and sender_id == str(cfg.TELEGRAM_CHAT_ID))


def _audit_command(text: str, sender_id: str, success: bool) -> bool:
    try:
        from database import AuditLog, get_session
        action = _command_name(text)[:32] or "unknown"
        sender_tag = hashlib.sha256(sender_id.encode()).hexdigest()[:12]
        with get_session() as db:
            db.add(AuditLog(action="telegram_command", source="telegram",
                            detail=f"{action};sender:{sender_tag}", success=success))
        return True
    except Exception:
        log.error("Telegram command audit unavailable")
        return False


async def _handle_command(text: str, chat_id: str = "") -> None:
    from alerts.telegram.client import send
    from alerts.telegram.commands.status      import (
        cmd_status, cmd_mode, cmd_health, cmd_balance, cmd_profit,
    )
    from alerts.telegram.commands.trading     import (
        cmd_trades, cmd_position, cmd_scan, cmd_queue,
    )
    from alerts.telegram.commands.signals     import (
        cmd_coin, cmd_btc, cmd_funding, cmd_fear,
    )
    from alerts.telegram.commands.performance import (
        cmd_pnl, cmd_daily, cmd_stats, cmd_grade,
        cmd_history, cmd_performance,
    )
    from alerts.telegram.commands.content     import (
        cmd_brief, cmd_pending, cmd_show_post, cmd_discard,
    )
    from alerts.telegram.commands.backtest    import (
        cmd_backtest, cmd_backfill, cmd_candle_status,
    )
    from alerts.telegram.commands.help        import cmd_help
    from alerts.telegram.commands.indian      import (
        cmd_india, cmd_orb, cmd_indianstats,
    )

    t = text.lower().strip()

    if t.startswith("/coin"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if not coin:
            await send("⚠️ Usage: `/coin BTC`")
        elif coin in cfg.COINS:
            await cmd_coin(coin)
        else:
            await send(
                f"⚠️ `{coin}` not in universe.\n"
                f"Your coins: `{', '.join(cfg.COINS)}`"
            )
        return

    if t.startswith("/position"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if not coin:
            await send("⚠️ Usage: `/position ETH`")
        else:
            await cmd_position(coin)
        return

    if t.startswith("/backtest"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if coin in cfg.COINS:
            await cmd_backtest(coin)
        else:
            await send("⚠️ Usage: `/backtest BTC`")
        return

    if t.startswith("/backfill"):
        parts = t.split()
        await cmd_backfill(parts[1].upper() if len(parts) > 1 else None)
        return

    if t.startswith("/discard"):
        parts = t.split()
        if len(parts) > 1:
            try:
                await cmd_discard(int(parts[1].replace("#", "")))
            except ValueError:
                await send("⚠️ Usage: `/discard 5`")
        else:
            await send("⚠️ Usage: `/discard 5`")
        return

    if t.startswith("#") and len(t) > 1:
        try:
            await cmd_show_post(int(t.replace("#", "").strip()))
        except ValueError:
            pass
        return

    handlers = {
        "/status":      cmd_status,
        "/pnl":         cmd_pnl,
        "/queue":       cmd_queue,
        "/daily":       cmd_daily,
        "/scan":        cmd_scan,
        "/help":        cmd_help,
        "/btc":         cmd_btc,
        "/funding":     cmd_funding,
        "/fear":        cmd_fear,
        "/history":     cmd_history,
        "/stats":       cmd_stats,
        "/grade":       cmd_grade,
        "/mode":        cmd_mode,
        "/brief":       cmd_brief,
        "/trades":      cmd_trades,
        "/balance":     cmd_balance,
        "/profit":      cmd_profit,
        "/health":      cmd_health,
        "/pending":     cmd_pending,
        "/candles":     cmd_candle_status,
        "/india":       cmd_india,
        "/orb":         cmd_orb,
        "/indianstats": cmd_indianstats,
        "/performance": cmd_performance,
    }

    if t.startswith("/"):
        handler = handlers.get(t)
        if handler:
            await handler()
        else:
            await send("🤖 Unknown command. Type /help for list.")
        return

    try:
        from chatbot import chat
        await send(await chat(text))
    except Exception as e:
        log.error("Chatbot error: %s", e)
        await send("AI unavailable. Try /help for commands.")
