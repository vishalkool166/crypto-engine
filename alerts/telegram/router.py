import logging
import hmac
from fastapi import Request, HTTPException
from config import cfg

log = logging.getLogger(__name__)


async def handle_webhook(request: Request) -> None:
    import os
    secret=request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
    if not cfg.WEBHOOK_SECRET or not hmac.compare_digest(secret,cfg.WEBHOOK_SECRET):
        raise HTTPException(403,"Forbidden")
    data=await request.json()
    msg=data.get("message",{})
    chat_id=str(msg.get("chat",{}).get("id",""))
    if chat_id!=str(cfg.TELEGRAM_CHAT_ID): return
    text=msg.get("text","")
    if not isinstance(text,str) or len(text)>2000: return
    allowed={x.strip() for x in os.getenv("TELEGRAM_ALLOWED_USER_IDS","").split(",") if x.strip()}
    if not allowed and not chat_id.startswith("-"): allowed={chat_id}
    if str(msg.get("from",{}).get("id","")) not in allowed: return
    from redis_client import get_redis
    redis=get_redis()
    # Deduplication and command budgets fail closed without the coordination store.
    if redis is None: raise HTTPException(503,"Command service unavailable")
    update_id=data.get("update_id")
    if not isinstance(update_id,int): return
    key="telegram:update:"+str(update_id)
    if not redis.set(key,"claimed",ex=86400,nx=True): return
    budget="telegram:budget:"+chat_id
    if redis.incr(budget)>12: return
    redis.expire(budget,60,nx=True)
    command=text.split()[0].split("@")[0].lower() if text.split() else ""
    if command in ("/scan","/backfill","/backtest"):
        if not redis.set("telegram:expensive:"+chat_id,"1",nx=True,ex=60):
            from alerts.telegram.client import send
            await send("*Request limit*\nWait one minute before starting another scan or research task.")
            return
    try:
        if text.startswith("/"):
            parts=text.strip().split()
            parts[0]=parts[0].split("@")[0]
            text=" ".join(parts)
        await _handle_command(text,chat_id)
    except Exception:
        # Keep the claim after failure: partial command effects must not replay.
        log.exception("Telegram command failed")
        from alerts.telegram.client import send
        await send("*Operation failed*\nThe command could not complete. Inspect operator logs for the recorded failure.")


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

    import re
    t = text.lower().strip()
    parts = t.split()
    if len(parts)>2 or (len(parts)==2 and not re.fullmatch(r"[a-z0-9#]{1,16}",parts[1])):
        await send("*Invalid command*\nUse /help for the accepted command format.")
        return

    if t.split(" ")[0] == "/coin":
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

    if t.split(" ")[0] == "/position":
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if not coin:
            await send("⚠️ Usage: `/position ETH`")
        else:
            await cmd_position(coin)
        return

    if t.split(" ")[0] == "/backtest":
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if coin in cfg.COINS:
            await cmd_backtest(coin)
        else:
            await send("⚠️ Usage: `/backtest ETH`")
        return

    if t.split(" ")[0] == "/backfill":
        parts = t.split()
        await cmd_backfill(parts[1].upper() if len(parts) > 1 else None)
        return

    if t.split(" ")[0] == "/discard":
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

    import os
    if os.getenv("ENABLE_TELEGRAM_ASSISTANT","false").lower() != "true":
        await send("Use /help for the operator command reference.")
        return
    try:
        from chatbot import chat
        await send(await chat(text))
    except Exception as e:
        log.error("Chatbot error: %s", e)
        await send("AI unavailable. Try /help for commands.")