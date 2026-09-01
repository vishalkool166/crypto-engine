import logging
from fastapi import Request
from config import cfg

log = logging.getLogger(__name__)


async def handle_webhook(request: Request) -> None:
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if cfg.WEBHOOK_SECRET and secret != cfg.WEBHOOK_SECRET:
        log.warning("Webhook secret mismatch — rejected")
        return
    try:
        data    = await request.json()
        msg     = data.get("message", {})
        text    = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id != str(cfg.TELEGRAM_CHAT_ID):
            return
        await _handle_command(text, chat_id)
    except Exception as e:
        log.error("Webhook handler error: %s", e)


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
    from alerts.telegram.commands.indian     import (
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

    if t.startswith("/rollback"):
        parts = t.split()
        param = parts[1] if len(parts) > 1 else ""
        if param:
            await cmd_rollback(param)
        else:
            await send("⚠️ Usage: `/rollback sweep_min_score`")
        return

    if t.startswith("/approve"):
        parts  = t.split()
        rec_id = parts[1] if len(parts) > 1 else ""
        if rec_id:
            await cmd_approve(rec_id)
        else:
            await send("⚠️ Usage: `/approve 5`")
        return

    if t.startswith("/reject"):
        parts  = t.split()
        rec_id = parts[1] if len(parts) > 1 else ""
        if rec_id:
            await cmd_reject(rec_id)
        else:
            await send("⚠️ Usage: `/reject 5`")
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


