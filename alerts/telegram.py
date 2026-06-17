import httpx
import logging
import time
import asyncio
from collections import deque
from datetime import datetime, timezone, timedelta
from fastapi import Request
from config import cfg
from database import SessionLocal, Trade, get_session
from trade.state import state_manager
from alerts.utils import now_ist, grade_accuracy_str, categorize_results
from data.cache import cache
from trade.risk import risk_guard
from engines.signal import get_session as get_trading_session
from trade.orders import get_current_price
import runtime_state as rs

log = logging.getLogger(__name__)

BASE   = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"
DOMAIN = cfg.DOMAIN

_sent_signals: deque = deque(maxlen=100)
_skip_reasons: dict  = {}
_SKIP_TTL             = 3600

TOTP_COMMANDS = {"/close", "/pause", "/resume", "/golive", "/gopaper"}


def _is_skipped(coin: str) -> bool:
    ts = _skip_reasons.get(coin)
    if ts is None:
        return False
    if time.time() - ts > _SKIP_TTL:
        del _skip_reasons[coin]
        return False
    return True


def _mins_until(target_hour: int, target_min: int = 0) -> tuple[int, int]:
    now  = datetime.now(timezone.utc)
    next = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
    if now >= next:
        next += timedelta(days=1)
    total = int((next - now).total_seconds() / 60)
    return total // 60, total % 60


def _fmt_mins(dt: datetime) -> str:
    now = datetime.now(timezone.utc)
    m   = int((dt - now).total_seconds() / 60)
    return f"{m // 60}h {m % 60}m"


def _next_dt(hour: int, minute: int = 0) -> datetime:
    now = datetime.now(timezone.utc)
    dt  = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= dt:
        dt += timedelta(days=1)
    return dt


def _active_trade_guard() -> Trade | None:
    if state_manager.is_idle:
        return None
    return state_manager.current_trade


def _get_current_and_upnl(trade) -> tuple[float, float]:
    current = get_current_price(trade.coin)
    upnl    = risk_guard.calculate_unrealized_pnl(
        direction     = trade.direction,
        entry_price   = trade.entry_price,
        current_price = current,
        pos_size      = trade.position_size
    )
    return current, upnl


def _pnl_str(pnl: float) -> str:
    return f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"


def _health_emoji(state: str) -> str:
    return {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(state, "—")


def _get_cached(coin: str) -> dict | None:
    return cache.get_raw(f"signal_{coin}")


def _all_cached_signals() -> list:
    results = []
    for coin in cfg.COINS:
        cached = cache.get_raw(f"signal_{coin}")
        if cached:
            results.append(cached)
    return results


def _get_stats() -> tuple[dict, dict]:
    from alerts.scanner import get_db_stats
    return get_db_stats(), risk_guard.get_daily_stats()


def _signal_keyboard(coin: str) -> list:
    return [
        [
            {"text": "📊 Factors", "callback_data": f"factors:{coin}"},
            {"text": "⚠️ Risks",   "callback_data": f"risks:{coin}"}
        ],
        [
            {"text": "✅ Approve", "callback_data": f"approve:{coin}"},
            {"text": "❌ Skip",    "callback_data": f"skip:{coin}"}
        ]
    ]


def _grade_block(label: str, data: dict) -> str:
    return (
        f"*Grade {label}*\n"
        f"Trades:   `{data.get('total', 0)}`\n"
        f"Wins:     `{data.get('wins', 0)}`\n"
        f"Losses:   `{data.get('losses', 0)}`\n"
        f"Win Rate: `{data.get('win_rate', 0)}%`\n"
        f"PnL:      `${data.get('total_pnl', 0)}`\n"
    )


def _build_pnl_message(stats: dict, risk_stats: dict) -> str:
    return (
        f"💰 *PnL Report*\n\n"
        f"*Today*\n"
        f"Trades:  `{risk_stats['trades_taken']}`\n"
        f"{'📈' if risk_stats['total_pnl'] >= 0 else '📉'} PnL: `${risk_stats['total_pnl']}`\n"
        f"Loss:    `${risk_stats['total_loss']}`\n"
        f"Cap Hit: `{'YES 🚫' if risk_stats['cap_hit'] else 'NO ✅'}`\n\n"
        f"*All Time*\n"
        f"Total:   `{stats.get('closed', 0) + stats.get('pending', 0)}` signals\n"
        f"Wins:    `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"WR:      `{stats.get('win_rate', 0)}%`\n"
        f"PnL:     `${stats.get('total_pnl', 0)}`\n"
    )


def _build_risk_message(stats: dict) -> str:
    from trade.risk import get_current_tier
    tier      = get_current_tier()
    capital   = tier["balance"] or cfg.CAPITAL
    daily_cap = capital * cfg.DAILY_LOSS_CAP_PCT
    loss_pct  = abs(stats["total_loss"]) / daily_cap * 100 if daily_cap > 0 else 0
    return (
        f"🛡️ *Daily Risk State*\n\n"
        f"Date:          `{stats['date']}`\n"
        f"Trades taken:  `{stats['trades_taken']}/{tier['max_trades']}`\n"
        f"Trades left:   `{stats['remaining_trades']}`\n\n"
        f"Loss today:    `${abs(stats['total_loss']):.4f}`\n"
        f"Loss cap:      `${daily_cap:.4f}`\n"
        f"Used:          `{loss_pct:.1f}%`\n"
        f"Remaining:     `${stats['remaining_loss']:.4f}`\n\n"
        f"PnL today:     `${stats['total_pnl']:.4f}`\n"
        f"Cap status:    `{'🚫 HIT' if stats['cap_hit'] else '✅ ACTIVE'}`\n"
        f"Tier:          `{tier['tier']}` · Balance: `${tier['balance']:.2f}`\n"
        + (f"\n⚠️ *Approaching cap — {loss_pct:.0f}% used*" if stats.get("approaching_cap") else "")
    )


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


async def send(message: str):
    chunks = _split_message(message)
    for chunk in chunks:
        await _post("sendMessage", {
            "chat_id":    cfg.TELEGRAM_CHAT_ID,
            "text":       chunk,
            "parse_mode": "Markdown"
        })


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


async def send_with_keyboard(message: str, keyboard: list):
    await _post("sendMessage", {
        "chat_id":      cfg.TELEGRAM_CHAT_ID,
        "text":         message,
        "parse_mode":   "Markdown",
        "reply_markup": {"inline_keyboard": keyboard}
    })


async def answer_callback(callback_id: str, text: str = ""):
    await _post("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text":              text
    })


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
        {"command": "status",   "description": "Trade state + health"},
        {"command": "thesis",   "description": "Why this trade exists"},
        {"command": "health",   "description": "Full health engine output"},
        {"command": "levels",   "description": "Price ladder + progress"},
        {"command": "close",    "description": "Close trade (TOTP required)"},
        {"command": "btc",      "description": "BTC analysis"},
        {"command": "regime",   "description": "Regime across Tier1"},
        {"command": "funding",  "description": "Funding rates"},
        {"command": "fear",     "description": "Fear & greed index"},
        {"command": "pnl",      "description": "Today + all time PnL"},
        {"command": "history",  "description": "Last 5 closed trades"},
        {"command": "stats",    "description": "Full all time stats"},
        {"command": "streak",   "description": "Win/loss streak"},
        {"command": "grade",    "description": "Grade accuracy"},
        {"command": "risk",     "description": "Daily risk state"},
        {"command": "session",  "description": "Current session"},
        {"command": "daily",    "description": "Daily summary"},
        {"command": "next",     "description": "Next scan + session times"},
        {"command": "scan",     "description": "Trigger manual scan"},
        {"command": "queue",    "description": "Best signal + approve/skip"},
        {"command": "pause",    "description": "Pause auto-execution (TOTP)"},
        {"command": "resume",   "description": "Resume auto-execution (TOTP)"},
        {"command": "golive",   "description": "Switch to live trading (TOTP)"},
        {"command": "gopaper",  "description": "Switch to paper trading (TOTP)"},
        {"command": "mode",     "description": "Current config"},
        {"command": "brief",    "description": "Morning briefing now"},
        {"command": "backtest", "description": "Backtest a coin"},
        {"command": "factors",  "description": "Factor analysis"},
        {"command": "debrief",  "description": "Last trade debrief"},
        {"command": "trades",   "description": "All active trades"},
        {"command": "setlevels", "description": "Set SL/TP for manual trade"},
        {"command": "help",     "description": "Full command list"},
    ]
    try:
        async with httpx.AsyncClient() as client:
            r    = await client.post(f"{BASE}/setMyCommands",
                                     json={"commands": commands}, timeout=10)
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
        data = await request.json()

        if "callback_query" in data:
            await _handle_callback(data["callback_query"])
            return

        msg     = data.get("message", {})
        text    = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if chat_id != str(cfg.TELEGRAM_CHAT_ID):
            return

        await _handle_command(text, chat_id)

    except Exception as e:
        log.error(f"Webhook handler error: {e}")


async def _handle_callback(callback: dict):
    callback_id = callback.get("id", "")
    data        = callback.get("data", "")
    chat_id     = str(callback.get("from", {}).get("id", ""))

    if chat_id != str(cfg.TELEGRAM_CHAT_ID):
        await answer_callback(callback_id, "Unauthorized")
        return

    await answer_callback(callback_id)

    if ":" in data:
        action, coin = data.split(":", 1)
        handlers = {
            "factors": _cb_show_factors,
            "risks":   _cb_show_risks,
            "approve": _cb_approve_signal,
            "skip":    _cb_skip_signal,
        }
        fn = handlers.get(action)
        if fn:
            await fn(coin)
    elif data == "confirm_close":
        await _cb_confirm_close()
    elif data == "cancel_close":
        await send("❌ Close cancelled — trade continues.")


async def _cb_show_factors(coin: str):
    cached = _get_cached(coin)
    if not cached:
        await send(f"⚠️ No cached data for {coin}. Run /scan first.")
        return

    wconf   = cached.get("wconf", {})
    factors = wconf.get("factors", [])
    score   = cached.get("score", 0)

    if not factors:
        await send(f"No factor data for {coin}.")
        return

    lines = [
        f"📊 *Confluence Factors — {coin}USDT*\n",
        f"Score: `{score}/100` · Earned: `{wconf.get('total_earned',0)}/{wconf.get('max_possible',0)}`\n"
    ]
    for f in factors:
        pct  = round(f["earned"] / f["max"] * 100) if f["max"] > 0 else 0
        icon = "✅" if f["pass"] else "❌"
        bar  = "█" * (pct // 10) + "░" * (10 - pct // 10)
        lines.append(f"{icon} *{f['label']}*\n`{bar}` {f['earned']}/{f['max']}\n_{f.get('detail', '')}_\n")

    await send("\n".join(lines))


async def _cb_show_risks(coin: str):
    cached = _get_cached(coin)
    if not cached:
        await send(f"⚠️ No cached data for {coin}.")
        return

    expl  = cached.get("explanation", {})
    softs = (cached.get("no_trade", {}) or {}).get("soft_blocks", [])
    lines = [f"⚠️ *Risk Analysis — {coin}USDT*\n"]

    if expl.get("risk_thesis"):
        lines += ["*Risk Factors:*", expl["risk_thesis"]]

    if softs:
        lines.append("\n*Score Penalties:*")
        for s in softs:
            lines.append(f"⚠ {s['reason']} `(-{s.get('penalty',0)}pts)`")

    if len(lines) == 1:
        lines.append("No significant risk factors identified.")

    await send("\n".join(lines))


async def _cb_approve_signal(coin: str):
    from trade.manager import trade_manager

    cached = _get_cached(coin)
    if not cached:
        await send(f"⚠️ Signal for {coin} expired. Run /scan for fresh data.")
        return

    signal = cached.get("signal", {})
    grade  = signal.get("grade", "F")
    dir_   = signal.get("direction", "")

    if grade not in cfg.MIN_GRADE_TO_TRADE:
        await send(f"⚠️ Grade {grade} no longer meets minimum.")
        return
    if dir_ not in ["LONG", "SHORT"]:
        await send(f"⚠️ Signal direction invalid: {dir_}")
        return
    if not state_manager.can_open_trade():
        await send(f"⚠️ Max concurrent trades reached.")
        return

    await send(f"✅ *Approved* — Opening `{coin}USDT {dir_}`...")
    signal["coin"] = coin
    result = await trade_manager.open_trade(signal=signal, signal_id=signal.get("db_id"))
    if not result["success"]:
        await send(f"❌ Trade failed: `{result['reason']}`")


async def _cb_skip_signal(coin: str):
    _skip_reasons[coin] = time.time()
    await send(f"⏭ *{coin} signal skipped*\n\nExpires in 1 hour.")


async def _cb_confirm_close():
    from trade.manager import trade_manager
    if state_manager.is_idle:
        await send("⚠️ No active trade to close.")
        return
    trade = state_manager.current_trade
    await send(f"⏳ Closing `{trade.coin}USDT {trade.direction}`...")
    result = await trade_manager.manual_close()
    await send("✅ Trade closed manually." if result["success"] else f"❌ Close failed: `{result['reason']}`")


async def _require_totp(chat_id: str, command: str) -> bool:
    from auth import verify_totp, audit
    pending = rs.get_totp_pending(chat_id)

    if pending and pending["action"] == command:
        return True

    rs.set_totp_pending(chat_id, command, time.time() + 60)
    await send(
        f"🔐 *TOTP Required*\n\n"
        f"Command: `{command}`\n"
        f"Send your 6-digit authenticator code within 60 seconds."
    )
    return False


async def _handle_totp_code(chat_id: str, code: str):
    from auth import verify_totp, audit
    pending = rs.get_totp_pending(chat_id)

    if not pending:
        await send("⚠️ No pending TOTP request. Send the command first.")
        return

    if not verify_totp(code):
        rs.clear_totp_pending(chat_id)
        audit("totp_failed", "telegram", f"chat:{chat_id} action:{pending['action']}", success=False)
        await send("❌ Invalid TOTP code. Request expired.")
        return

    action = pending["action"]
    rs.clear_totp_pending(chat_id)
    audit("totp_success", "telegram", f"chat:{chat_id} action:{action}", success=True)

    handlers = {
        "/close":   _cmd_close_confirmed,
        "/pause":   _cmd_pause_confirmed,
        "/resume":  _cmd_resume_confirmed,
        "/golive":  _cmd_golive_confirmed,
        "/gopaper": _cmd_gopaper_confirmed,
    }
    fn = handlers.get(action)
    if fn:
        await fn()
    else:
        await send(f"✅ TOTP verified for `{action}`")


async def _handle_command(text: str, chat_id: str = ""):
    t = text.lower().strip()

    if t.isdigit() and len(t) == 6:
        await _handle_totp_code(chat_id, t)
        return

    if t.startswith("/coin"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if not coin:
            await send("⚠️ Usage: `/coin BTC`")
            return
        coins = cfg.COINS
        if coin in coins:
            await _cmd_coin(coin)
        elif not coins:
            await send(
                f"⚠️ Coin universe is empty.\n\n"
                f"Add coins via the dashboard first."
            )
        else:
            await send(
                f"⚠️ `{coin}` not in your universe.\n\n"
                f"Your coins: `{', '.join(coins)}`\n\n"
                f"Add it via dashboard → Coin Universe."
            )
        return

    if t.startswith("/backtest"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if coin in cfg.COINS:
            await _cmd_backtest(coin)
        else:
            await send(f"⚠️ Usage: `/backtest BTC`")
        return
    
    if t.startswith("/setlevels"):
        parts = t.split()
        if len(parts) != 5:
            await send(
                "⚠️ Usage: `/setlevels COIN SL TP1 TP2`\n\n"
                "Example:\n`/setlevels ALGO 0.0950 0.0850 0.0800`"
            )
            return
        coin = parts[1].upper()
        try:
            sl  = float(parts[2])
            tp1 = float(parts[3])
            tp2 = float(parts[4])
        except ValueError:
            await send("⚠️ Invalid numbers. Use: `/setlevels ALGO 0.0950 0.0850 0.0800`")
            return
        await _cmd_setlevels(coin, sl, tp1, tp2)
        return

    if t in TOTP_COMMANDS:
        needs_totp = await _require_totp(chat_id, t)
        if not needs_totp:
            return
        handlers = {
            "/close":   _cmd_close_confirmed,
            "/pause":   _cmd_pause_confirmed,
            "/resume":  _cmd_resume_confirmed,
            "/golive":  _cmd_golive_confirmed,
            "/gopaper": _cmd_gopaper_confirmed,
        }
        fn = handlers.get(t)
        if fn:
            await fn()
        return

    handlers = {
        "/status":  _cmd_status,
        "/pnl":     _cmd_pnl,
        "/queue":   _cmd_queue,
        "/daily":   _cmd_daily,
        "/scan":    _cmd_scan,
        "/help":    _cmd_help,
        "/thesis":  _cmd_thesis,
        "/health":  _cmd_health,
        "/levels":  _cmd_levels,
        "/btc":     _cmd_btc,
        "/regime":  _cmd_regime,
        "/funding": _cmd_funding,
        "/fear":    _cmd_fear,
        "/history": _cmd_history,
        "/stats":   _cmd_stats,
        "/streak":  _cmd_streak,
        "/grade":   _cmd_grade,
        "/risk":    _cmd_risk,
        "/session": _cmd_session,
        "/next":    _cmd_next,
        "/mode":    _cmd_mode,
        "/brief":   _cmd_brief,
        "/factors": _cmd_factors,
        "/debrief": _cmd_debrief,
        "/trades":  _cmd_trades,
        "/setlevels": _cmd_setlevels,
    }

    if t.startswith("/"):
        handler = handlers.get(t)
        if handler:
            await handler()
        else:
            await send("🤖 Unknown command.\n\nType /help for full command list.")
        return

    try:
        from chatbot import chat
        response = await chat(text)
        await send(response)
    except Exception as e:
        log.error(f"Chatbot error: {e}")
        await send("AI is temporarily unavailable. Try /help for commands.")


async def _cmd_status():
    if state_manager.is_idle:
        paused_note = (
            "\n⏸ Auto-execution is *PAUSED*"
            if state_manager.is_paused else ""
        )
        await send(
            f"📊 *Bot Status*\n\n"
            f"State: `IDLE`\n"
            f"No active trade.{paused_note}\n\n"
            f"Use /scan to trigger manual scan."
        )
        return

    lines = [f"📊 *Bot Status — {len(state_manager.active_trades)} Active Trade(s)*\n"]
    for trade in state_manager.active_trades.values():
        current, upnl = _get_current_and_upnl(trade)
        health        = state_manager.health_state_for(trade.id)
        lines.append(
            f"*{trade.coin}USDT {trade.direction}* Grade `{trade.grade}`\n"
            f"Entry: `{trade.entry_price}` · Current: `{current}`\n"
            f"SL: `{trade.sl_price}` · TP1: `{trade.tp1_price}`\n"
            f"{'📈' if upnl >= 0 else '📉'} uPnL: `${upnl}`\n"
            f"{_health_emoji(health)} Health: `{health}`\n"
        )
    await send("\n".join(lines))


async def _cmd_trades():
    if state_manager.is_idle:
        await send("📊 No active trades.")
        return
    await _cmd_status()


async def _cmd_thesis():
    trade = _active_trade_guard()
    if not trade:
        await send("⚠️ No active trade.")
        return
    await _show_active_thesis(trade.coin)


async def _cmd_health():
    if state_manager.is_idle:
        await send("⚠️ No active trade — no health data.")
        return

    for trade in state_manager.active_trades.values():
        health = state_manager.health_data_for(trade.id)
        state  = state_manager.health_state_for(trade.id)

        lines = [f"{_health_emoji(state)} *Trade Health — {trade.coin}*\n", f"Status: `{state}`\n"]

        for label, items, icon in [
            ("*Invalidated:*", health.get("failures", []), "✘"),
            ("\n*Warnings:*",  health.get("warnings", []), "⚠"),
        ]:
            if items:
                lines.append(label)
                lines.extend(f"{icon} {i}" for i in items)

        await send("\n".join(lines))


async def _cmd_levels():
    trade = _active_trade_guard()
    if not trade:
        await send("⚠️ No active trade.")
        return

    from trade.price_feed import price_feed
    current, upnl = _get_current_and_upnl(trade)
    current       = price_feed.get_price(trade.coin) or current
    is_long       = trade.direction == "LONG"
    tp1_hit       = state_manager.is_tp1_hit_for(trade.id)

    total    = abs(trade.tp1_price - trade.entry_price) if trade.tp1_price and trade.entry_price else 0
    progress = 0
    if total > 0:
        progress = ((current - trade.entry_price) if is_long else (trade.entry_price - current)) / total * 100
    progress = max(0, min(100, progress))

    await send(
        f"📐 *Price Levels — {trade.coin}USDT*\n\n"
        f"TP2:     `{trade.tp2_price}`\n"
        f"TP1:     `{trade.tp1_price}`{'  ✅ HIT' if tp1_hit else ''}\n"
        f"NOW:     `{current:.4f}` ← live\n"
        f"Entry:   `{trade.entry_price}`\n"
        f"{'BE ✅' if tp1_hit else 'SL 🛑'}: `{trade.sl_price}`\n\n"
        f"Progress to TP1: `{progress:.0f}%`\n"
        f"uPnL: `{_pnl_str(upnl)}`\n"
    )


async def _cmd_close_confirmed():
    trade = _active_trade_guard()
    if not trade:
        await send("⚠️ No active trade to close.")
        return
    current, upnl = _get_current_and_upnl(trade)
    await send_with_keyboard(
        f"⚠️ *Close {trade.coin}USDT {trade.direction}?*\n\n"
        f"Entry:   `{trade.entry_price}`\n"
        f"Current: `{current}`\n"
        f"uPnL:    `{_pnl_str(upnl)}`\n\n"
        f"This cancels all SL/TP orders.",
        keyboard=[[
            {"text": "✅ Yes, Close", "callback_data": "confirm_close"},
            {"text": "❌ Cancel",     "callback_data": "cancel_close"}
        ]]
    )


async def _cmd_pause_confirmed():
    if state_manager.is_paused:
        await send("⏸ Already paused.")
        return
    state_manager.pause()
    await send("⏸ *Auto-Execution Paused*\n\nBot will NOT auto-open trades.\nUse /resume to re-enable.")


async def _cmd_resume_confirmed():
    if not state_manager.is_paused:
        await send("▶️ Already running.")
        return
    state_manager.resume()
    await send("▶️ *Auto-Execution Resumed*\n\nNext A+ signal will execute automatically.")


async def _cmd_golive_confirmed():
    from auth import audit
    from data.fetcher import get_live_balance
    from trade.risk import get_tier_config

    balance = await get_live_balance()
    if balance < cfg.MIN_BALANCE_LIVE:
        await send(f"❌ Balance ${balance:.2f} below minimum ${cfg.MIN_BALANCE_LIVE}")
        audit("golive_blocked", "telegram", f"balance:{balance}")
        return

    if not cfg.BINANCE_API_KEY or not cfg.BINANCE_SECRET:
        await send("❌ Binance API keys not configured.")
        return

    current_paper = rs.get_balance_cache().get("balance", cfg.CAPITAL)
    rs.set_paper_balance(current_paper)

    rs.set_trading_mode("live")
    cfg.TRADING_MODE  = "live"
    cfg.PAPER_TRADING = False
    rs.set_balance_cache(balance)
    tier = get_tier_config(balance)
    rs.set_tier_config(tier)
    cfg.CAPITAL = balance
    audit("golive", "telegram", f"balance:{balance}", success=True)

    from events import emit
    await emit("mode_changed")

    await send(
        f"🔴 *LIVE TRADING ENABLED*\n\n"
        f"Balance: `${balance:.2f}`\n"
        f"Real orders will be placed on Binance.\n"
        f"Use /gopaper to switch back."
    )


async def _cmd_gopaper_confirmed():
    from auth import audit
    from trade.risk import get_tier_config

    rs.set_trading_mode("paper")
    cfg.TRADING_MODE  = "paper"
    cfg.PAPER_TRADING = True

    saved_paper = rs.get_paper_balance()
    paper_balance = saved_paper if saved_paper > 0 else cfg.CAPITAL
    rs.set_balance_cache(paper_balance)
    tier = get_tier_config(paper_balance)
    rs.set_tier_config(tier)
    cfg.CAPITAL = paper_balance
    audit("gopaper", "telegram", success=True)

    from events import emit
    await emit("mode_changed")

    await send(
        f"🔵 *PAPER TRADING ENABLED*\n\n"
        f"Balance: `${paper_balance:.2f}`\n"
        f"No real orders will be placed."
    )


async def _cmd_btc():
    await _cmd_coin("BTC")


async def _cmd_coin(coin: str):
    cached = _get_cached(coin)
    if not cached:
        await send(f"No data for `{coin}`. Run /scan first.")
        return

    market  = cached.get("market", {})
    grade   = cached.get("grade", "F")
    dir_    = cached.get("direction", "--")
    score   = cached.get("score", 0)
    sweep   = cached.get("sweep", {})
    disp    = cached.get("displacement", {})
    retest  = cached.get("retest", {})
    d1d     = cached.get("d1d", {})
    d4h     = cached.get("d4h", {})
    expl    = cached.get("explanation", {})

    price   = market.get("price", 0)
    change  = market.get("change24", 0)
    funding = market.get("funding", 0) * 100
    sign    = "+" if change >= 0 else ""
    em      = "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁"
    rsi     = d1d.get("rsi")
    adx     = d1d.get("adx")

    base = (
        f"📊 *{coin}USDT Analysis*\n\n"
        f"Price:   `${price:,.4f}` ({sign}{change:.2f}%)\n"
        f"Grade:   `{grade}` · Score `{score}/100`\n"
        f"Signal:  {em} `{dir_}`\n"
        f"Conf:    `{expl.get('confidence_label', '--')}`\n\n"
        f"Regime:  `{cached.get('regime', '--')}`\n"
        f"Session: `{cached.get('session', '--')}`\n\n"
    )

    if rsi and adx:
        base += (
            f"RSI:     `{rsi:.1f}`\n"
            f"ADX:     `{adx:.1f}`\n"
            f"Funding: `{funding:.4f}%`\n\n"
        )

    base += (
        f"Sweep:   `{'✅' if sweep.get('confirmed') else '❌'} {sweep.get('score',0)}/12`\n"
        f"Disp:    `{'✅' if disp.get('confirmed') else '❌'} {disp.get('score',0)}/11`\n"
        f"Retest:  `{'✅' if retest.get('confirmed') else '❌'} {retest.get('score',0)}/12`\n"
    )

    await send(base)


async def _cmd_regime():
    coins = cfg.COINS[:8]
    lines = [f"📈 *Market Regime — Top {len(coins)} Coins*\n"]
    for coin in coins:
        cached = _get_cached(coin)
        if not cached:
            lines.append(f"`{coin}` — no data")
            continue
        dir_ = cached.get("direction", "--")
        em   = "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁"
        lines.append(f"{em} `{coin}` — {cached.get('regime','--')} · Grade {cached.get('grade','F')}")
    await send("\n".join(lines))


async def _cmd_funding():
    lines = ["💸 *Funding Rates*\n"]
    for cached in _all_cached_signals():
        coin    = cached.get("coin", "")
        funding = cached.get("market", {}).get("funding", 0) * 100
        flag    = "🚨" if abs(funding) > 0.08 else "⚠️" if abs(funding) > 0.05 else "✅"
        lines.append(f"{flag} `{coin}` — `{funding:.4f}%`")
    if len(lines) == 1:
        lines.append("No data — run /scan first")
    await send("\n".join(lines))


async def _cmd_fear():
    from data.fetcher import get_fear_greed
    try:
        fg    = await get_fear_greed()
        val   = fg.get("value", 50)
        label = fg.get("label", "Neutral")
        stale = fg.get("stale", False)
        emoji = "🟢" if val >= 60 else "🔴" if val <= 30 else "🟡"
        await send(
            f"{emoji} *Fear & Greed Index*\n\n"
            f"Value: `{val}/100`\n"
            f"Label: `{label}`\n"
            f"{'⚠️ _Stale data — API unavailable_' if stale else ''}"
        )
    except Exception as e:
        await send(f"❌ Fear & Greed fetch failed: `{e}`")


async def _cmd_pnl():
    stats, risk_stats = _get_stats()
    await send(_build_pnl_message(stats, risk_stats))


async def _cmd_risk():
    _, risk_stats = _get_stats()
    await send(_build_risk_message(risk_stats))


async def _cmd_daily():
    from trade.risk import get_current_tier
    _, risk_stats = _get_stats()
    tier = get_current_tier()
    await send(
        f"📅 *Daily Summary*\n\n"
        f"Date:      `{risk_stats['date']}`\n"
        f"Trades:    `{risk_stats['trades_taken']}/{tier['max_trades']}`\n"
        f"PnL:       `${risk_stats['total_pnl']}`\n"
        f"Loss:      `${risk_stats['total_loss']}`\n\n"
        f"Remaining trades: `{risk_stats['remaining_trades']}`\n"
        f"Remaining loss:   `${risk_stats['remaining_loss']}`\n"
        f"Cap hit: `{'YES 🚫' if risk_stats['cap_hit'] else 'NO ✅'}`\n"
        f"Tier: `{tier['tier']}` · Balance: `${tier['balance']:.2f}`\n"
    )


async def _cmd_history():
    with get_session() as db:
        trades = db.query(Trade).filter(
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss", "manual"])
        ).order_by(Trade.closed_at.desc()).limit(5).all()

    if not trades:
        await send("📜 No closed trades yet.")
        return

    lines = ["📜 *Last 5 Trades*\n"]
    for t in trades:
        emoji  = "✅" if t.outcome == "win" else "❌" if t.outcome == "loss" else "⏹"
        dir_em = "📈" if t.direction == "LONG" else "📉"
        lines.append(
            f"{emoji} {dir_em} `{t.coin}` {t.direction} Grade `{t.grade}` — `{_pnl_str(t.pnl or 0)}`\n"
            f"_{t.close_reason or '--'}_\n"
        )
    await send("\n".join(lines))


async def _cmd_stats():
    stats, _ = _get_stats()
    if not stats:
        await send("📊 No stats yet.")
        return

    bg = stats.get("by_grade", {})
    ap = bg.get("A+", {})
    a  = bg.get("A", {})

    await send(
        f"📊 *All Time Stats*\n\n"
        f"Total signals: `{stats.get('total', 0)}`\n"
        f"Closed:        `{stats.get('closed', 0)}`\n"
        f"Wins:    `{stats.get('wins', 0)}`\n"
        f"Losses:  `{stats.get('losses', 0)}`\n"
        f"WR:      `{stats.get('win_rate', 0)}%`\n"
        f"PnL:     `${stats.get('total_pnl', 0)}`\n\n"
        f"*Grade A+*\n"
        f"Trades: `{ap.get('total',0)}` · WR: `{ap.get('win_rate',0)}%` · PnL: `${ap.get('total_pnl',0)}`\n\n"
        f"*Grade A*\n"
        f"Trades: `{a.get('total',0)}` · WR: `{a.get('win_rate',0)}%` · PnL: `${a.get('total_pnl',0)}`\n"
    )


async def _cmd_streak():
    with get_session() as db:
        trades = db.query(Trade).filter(
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss"])
        ).order_by(Trade.closed_at.desc()).all()

    if not trades:
        await send("📊 No closed trades yet.")
        return

    current_streak = 0
    current_type   = trades[0].outcome
    for t in trades:
        if t.outcome == current_type:
            current_streak += 1
        else:
            break

    max_wins = max_losses = cur_w = cur_l = 0
    for t in reversed(trades):
        if t.outcome == "win":
            cur_w += 1; cur_l  = 0
        else:
            cur_l += 1; cur_w  = 0
        max_wins   = max(max_wins,   cur_w)
        max_losses = max(max_losses, cur_l)

    emoji = "🔥" if current_type == "win" else "❄️"
    await send(
        f"🔢 *Streak Report*\n\n"
        f"Current: {emoji} `{current_streak} {current_type}s`\n\n"
        f"Max wins:   `{max_wins} in a row`\n"
        f"Max losses: `{max_losses} in a row`\n"
    )


async def _cmd_grade():
    stats, _ = _get_stats()
    bg       = stats.get("by_grade", {}) if stats else {}
    await send(
        f"🏆 *Grade Accuracy*\n\n"
        f"{_grade_block('A+', bg.get('A+', {}))}\n"
        f"{_grade_block('A',  bg.get('A',  {}))}\n"
        f"_Minimum 50 trades for reliable data_"
    )


async def _cmd_session():
    session   = get_trading_session()
    hrs, mins = _mins_until(8)
    now       = datetime.now(timezone.utc)
    await send(
        f"🕐 *Session Status*\n\n"
        f"Current:   `{session['name']}`\n"
        f"Quality:   `{session['quality']}`\n"
        f"Entries:   {'✅' if session['tradeable'] else '🚫'} `{'ALLOWED' if session['tradeable'] else 'BLOCKED'}`\n"
        f"Score:     `{session['score']}/9`\n\n"
        f"_{session['desc']}_\n\n"
        f"London open in: `{hrs}h {mins}m`\n"
        f"UTC now: `{now.strftime('%H:%M')}`"
    )


async def _cmd_next():
    from scheduler import get_next_scan_time
    session = get_trading_session()
    next_s  = get_next_scan_time()
    london  = _next_dt(8)
    ny      = _next_dt(13)
    await send(
        f"⏱ *Next Events*\n\n"
        f"Next scan:      `{next_s}`\n"
        f"London open:    `08:00 UTC` (in {_fmt_mins(london)})\n"
        f"NY open:        `13:00 UTC` (in {_fmt_mins(ny)})\n\n"
        f"Current session: `{session['name']}`\n"
        f"Entries: `{'✅ ALLOWED' if session['tradeable'] else '🚫 BLOCKED'}`"
    )


async def _cmd_mode():
    from trade.risk import get_current_tier
    tier       = get_current_tier()
    paused_str = "⏸ PAUSED" if state_manager.is_paused else "▶️ AUTO"
    mode       = rs.get_trading_mode()
    await send(
        f"⚙️ *Bot Configuration*\n\n"
        f"Mode:        `{'🔴 LIVE' if mode == 'live' else '🔵 PAPER'}`\n"
        f"Execution:   `{paused_str}`\n"
        f"Active trades: `{len(state_manager.active_trades)}/{tier['max_trades']}`\n\n"
        f"Balance:     `${tier['balance']:.2f}`\n"
        f"Tier:        `{tier['tier']}`\n"
        f"Leverage:    `{tier['leverage']}x`\n"
        f"Risk/trade:  `{tier['risk_pct']*100:.0f}%`\n"
        f"Max trades:  `{tier['max_trades']}/day`\n"
        f"Daily cap:   `{cfg.DAILY_LOSS_CAP_PCT*100:.0f}%`\n\n"
        f"Grades:      `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Coins:       `{len(cfg.COINS)} coins`\n"
    )


async def _cmd_brief():
    from alerts.briefing import send_morning_briefing
    await send("🌅 Generating briefing...")
    await send_morning_briefing()


async def _cmd_factors():
    from backtest.factor_analysis import run_factor_analysis
    await send("⏳ Running factor analysis...")
    result = run_factor_analysis()

    if "error" in result:
        await send(f"⚠️ *Factor Analysis*\n\n{result['error']}")
        return

    total = result.get("total", 0)
    wr    = result.get("overall_wr", 0)
    top   = result.get("top_factors", [])
    weak  = result.get("weak_factors", [])

    lines = [f"🔬 *Factor Analysis*\n", f"Trades: `{total}` · WR: `{wr}%`\n"]

    if top:
        lines.append("*Strong Edge:*")
        for f in top[:3]:
            lines.append(f"✅ `{f['factor']}` — edge: `+{f['edge']}%`")

    if weak:
        lines.append("\n*Weak/No Edge:*")
        for f in weak[:3]:
            lines.append(f"⚠️ `{f['factor']}` — edge: `{f['edge']}%`")

    await send("\n".join(lines))


async def _cmd_backtest(coin: str):
    from backtest.engine import run_backtest
    from trade.risk import get_current_tier
    tier = get_current_tier()
    await send(f"⏳ Running backtest for `{coin}`...")
    try:
        loop   = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None, lambda: run_backtest(
                    coin=coin,
                    capital=tier["balance"] or cfg.CAPITAL,
                    leverage=tier["leverage"]
                )
            ),
            timeout=120.0
        )
        if "error" in result:
            await send(f"❌ Backtest failed: `{result['error']}`")
            return

        bg = result.get("by_grade", {})
        pb = result.get("phase_breakdown", {})
        await send(
            f"📊 *Backtest — {coin}USDT*\n\n"
            f"Period: `{result.get('period_start')} → {result.get('period_end')}`\n\n"
            f"Signals:  `{result.get('total_signals', 0)}`\n"
            f"Trades:   `{result.get('total_trades', 0)}`\n"
            f"Win Rate: `{result.get('win_rate', 0)}%`\n"
            f"PnL:      `${result.get('total_pnl', 0)}`\n"
            f"Max DD:   `{result.get('max_drawdown', 0)}%`\n\n"
            f"TP1 hit: `{pb.get('tp1_hit_rate', 0)}%` · TP2 hit: `{pb.get('tp2_hit_rate', 0)}%`\n\n"
            f"A+: `{bg.get('A+',{}).get('win_rate',0)}% WR` · `{bg.get('A+',{}).get('trades',0)} trades`\n"
            f"A:  `{bg.get('A',{}).get('win_rate',0)}% WR` · `{bg.get('A',{}).get('trades',0)} trades`\n"
        )
    except asyncio.TimeoutError:
        await send(f"❌ Backtest timed out after 120s")
    except Exception as e:
        await send(f"❌ Backtest error: `{str(e)}`")


async def _cmd_debrief():
    with get_session() as db:
        trade = db.query(Trade).filter(
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss", "manual"])
        ).order_by(Trade.closed_at.desc()).first()

    if not trade:
        await send("📋 No closed trades yet.")
        return

    from alerts.briefing import send_post_trade_debrief
    await send_post_trade_debrief(
        trade=trade, outcome=trade.outcome,
        pnl=trade.pnl or 0, close_reason=trade.close_reason or "--",
        health_at_close=trade.health_at_close or "UNKNOWN"
    )


async def _cmd_scan():
    await send("🔍 *Manual Scan Started*\n\nScanning all coins...\nThis takes 1-2 minutes.")
    try:
        from alerts.scanner import scan_all_coins
        await scan_all_coins()
    except Exception as e:
        await send(f"❌ *Scan Failed*\n\n`{str(e)}`")


async def _cmd_queue():
    best       = None
    best_score = 0

    for cached in _all_cached_signals():
        if _is_skipped(cached.get("coin", "")):
            continue
        score = cached.get("score", 0)
        grade = cached.get("grade", "F")
        if score > best_score and grade in ["A+", "A"]:
            best       = cached
            best_score = score

    if not best:
        await send("📋 *Signal Queue*\n\nNo A/A+ signals in cache.\nUse /scan to scan now.")
        return

    sig  = best.get("signal", {})
    coin = best.get("coin", "?")

    await send_with_keyboard(
        f"📋 *Next Signal — Grade {best['grade']}*\n\n"
        f"Coin:  `{coin}USDT`\n"
        f"Dir:   `{best['direction']}`\n"
        f"Score: `{best['score']}/100`\n\n"
        f"Entry: `{sig.get('entry', '--')}`\n"
        f"SL:    `{sig.get('sl', '--')}`\n"
        f"TP1:   `{sig.get('tp1', '--')}`\n"
        f"TP2:   `{sig.get('tp2', '--')}`\n\n" +
        (
            "Max concurrent trades reached."
            if not state_manager.can_open_trade() else
            "Bot is idle — tap Approve to execute."
        ),
        keyboard=_signal_keyboard(coin)
    )

async def _cmd_setlevels(coin: str, sl: float, tp1: float, tp2: float):
    from trade.manager import trade_manager
    result = await trade_manager.set_trade_levels(coin, sl, tp1, tp2)
    if result["success"]:
        await send(
            f"✅ *Levels Set — {coin}USDT*\n\n"
            f"SL:  `{sl}`\n"
            f"TP1: `{tp1}`\n"
            f"TP2: `{tp2}`\n\n"
            f"Bot is now monitoring this trade."
        )
    else:
        await send(f"❌ Failed: `{result['reason']}`")


async def _cmd_help():
    await send(
        "🤖 *Signal Engine v5 — Commands*\n\n"
        "*TRADE*\n"
        "/status  — all active trades\n"
        "/trades  — same as status\n"
        "/thesis  — why this trade exists\n"
        "/health  — health engine output\n"
        "/levels  — price ladder\n"
        "/close   — close trade (TOTP)\n\n"
        "/setlevels COIN SL TP1 TP2 — set levels for manual trade\n\n"
        "*MARKET*\n"
        "/btc         — BTC analysis\n"
        "/coin ETH    — any coin analysis\n"
        "/regime      — regime across Tier1\n"
        "/funding     — funding rates\n"
        "/fear        — fear & greed index\n\n"
        "*PERFORMANCE*\n"
        "/pnl     — today + all time PnL\n"
        "/history — last 5 closed trades\n"
        "/stats   — full all time stats\n"
        "/streak  — win/loss streak\n"
        "/grade   — grade accuracy\n\n"
        "*RISK & SESSION*\n"
        "/risk    — daily risk state\n"
        "/session — current session\n"
        "/daily   — daily summary\n"
        "/next    — next scan + session times\n\n"
        "*BOT CONTROL*\n"
        "/scan    — trigger manual scan\n"
        "/queue   — best signal + approve/skip\n"
        "/pause   — pause auto-execution (TOTP)\n"
        "/resume  — resume auto-execution (TOTP)\n"
        "/golive  — enable live trading (TOTP)\n"
        "/gopaper — enable paper trading (TOTP)\n"
        "/mode    — current config\n"
        "/brief   — morning briefing\n\n"
        "*ANALYSIS*\n"
        "/backtest BTC — backtest a coin\n"
        "/factors      — factor analysis\n"
        "/debrief      — last trade debrief\n"
        "/help         — this message\n"
    )


async def send_signal(signal: dict, coin: str, regime: str, session: str):
    if signal.get("grade") not in ["A+", "A"]:
        return
    if signal.get("direction") not in ["LONG", "SHORT"]:
        return
    if _is_skipped(coin):
        return

    sig_key = f"{coin}_{signal.get('direction')}_{signal.get('grade')}_{round(signal.get('entry', 0), 0)}"
    if sig_key in _sent_signals:
        return
    _sent_signals.append(sig_key)

    grade     = signal.get("grade", "?")
    direction = signal.get("direction", "?")
    score     = signal.get("score", 0)
    entry     = signal.get("entry", 0)
    sl        = signal.get("sl", 0)
    tp1       = signal.get("tp1", 0)
    tp2       = signal.get("tp2", 0)
    sl_pct    = signal.get("sl_pct", 0)
    risk_amt  = signal.get("risk_amt", 0)
    pos_size  = signal.get("pos_size", 0)
    emoji     = "🏆" if grade == "A+" else "✅"
    dir_emoji = "📈" if direction == "LONG" else "📉"

    explanation = signal.get("explanation", {})
    thesis      = explanation.get("thesis", "")
    conf_label  = explanation.get("confidence_label", "")

    from trade.risk import get_current_tier
    tier        = get_current_tier()
    paused_note = (
        "\n⏸ _Auto-execution paused — tap Approve to enter_\n"
        if state_manager.is_paused else ""
    )
    slots_note = (
        f"\n⚡ Slot `{len(state_manager.active_trades)+1}/{tier['max_trades']}` available\n"
        if state_manager.can_open_trade() else
        "\n🚫 _All trade slots full_\n"
    )

    await send_with_keyboard(
        f"{emoji} *Grade {grade} — {direction}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*{coin}USDT — {dir_emoji} {direction}*\n"
        f"{'Confidence: `' + conf_label + ' (' + str(score) + '/100)`' + chr(10) if conf_label else ''}"
        f"Regime:  `{regime}`\n"
        f"Session: `{session}`\n"
        f"Time:    `{now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Entry:   `{entry:.4f}`\n"
        f"SL:      `{sl:.4f}` ({sl_pct:.2f}%)\n"
        f"TP1:     `{tp1:.4f}`\n"
        f"TP2:     `{tp2:.4f}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Risk:    `${risk_amt:.2f}`\n"
        f"Size:    `${pos_size:.2f}`\n"
        f"Lev:     `{tier['leverage']}x`\n"
        f"{chr(10) + '*Why:* ' + thesis + chr(10) if thesis else ''}"
        f"{paused_note}{slots_note}",
        keyboard=_signal_keyboard(coin)
    )


async def send_scan_summary(results: list):
    from scheduler import get_next_scan_time
    cats      = categorize_results(results)
    tradeable = cats["tradeable"]
    watching  = cats["watching"]
    building  = cats["building"]
    next_scan = get_next_scan_time()

    if tradeable:
        lines = [
            f"🔍 *Scan Complete — {now_ist()}*\n"
            f"{len(tradeable)} tradeable signal(s)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        ]
        for r in tradeable[:3]:
            g         = r.get("grade", "?")
            direction = r.get("direction", "?")
            score     = r.get("score", 0)
            coin      = r.get("coin", "?")
            conf      = r.get("explanation", {}).get("confidence_label", "")
            emoji     = "🏆" if g == "A+" else "✅"
            dir_emoji = "📈" if direction == "LONG" else "📉"
            lines.append(
                f"{emoji} *{coin}* — Grade {g} ({score}/100){' · ' + conf if conf else ''}\n"
                f"{dir_emoji} {direction}\n"
            )

        from trade.risk import get_current_tier
        tier = get_current_tier()
        lines.append(
            f"\nActive: `{len(state_manager.active_trades)}/{tier['max_trades']}` slots"
        )
        lines.append(f"\nNext scan: `{next_scan}`")
        await send("\n".join(lines))
        return

    lines = [f"😴 *No Tradeable Signals — {now_ist()}*\n━━━━━━━━━━━━━━━━━━━━━━\n"]

    if watching:
        lines.append("*Closest Setups:*")
        for r in watching[:3]:
            d      = r.get("direction", "?")
            s      = r.get("score", 0)
            em     = "📈" if d == "LONG" else "📉"
            hards  = (r.get("no_trade", {}) or {}).get("hard_blocks", [])
            reason = hards[0]["reason"] if hards else "setup building"
            lines.append(f"{em} `{r['coin']}` — B ({s}/100)\n_{reason}_\n")
    elif building:
        lines.append("*Building:*")
        for r in building[:2]:
            lines.append(f"👁 `{r['coin']}` — C ({r.get('score',0)}/100)")
    else:
        lines.append("No setups building.")

    lines.append(f"\nNext scan: `{next_scan}`")
    await send("\n".join(lines))


async def send_progress_update(trade, current_price: float, milestone_pct: int):
    is_long  = trade.direction == "LONG"
    entry    = trade.entry_price
    tp1      = trade.tp1_price
    sl       = trade.sl_price

    upnl = (
        (current_price - entry) / entry * trade.position_size
        if is_long else
        (entry - current_price) / entry * trade.position_size
    )
    dist_tp1 = abs(tp1 - current_price) if tp1 else 0

    await send(
        f"⚡ *{trade.coin}USDT — {milestone_pct}% to TP1*\n\n"
        f"Price:   `${current_price:,.4f}`\n"
        f"Entry:   `{entry}`\n"
        f"TP1:     `{tp1}` — `${dist_tp1:,.4f}` away\n"
        f"SL:      `{sl}`\n\n"
        f"uPnL:    `{_pnl_str(upnl)}`\n"
        f"{_health_emoji(state_manager.health_state_for(trade.id))} Health: `{state_manager.health_state_for(trade.id)}`\n\n"
        f"Type /status for full details"
    )


async def _show_active_thesis(coin: str):
    cached = _get_cached(coin)
    if not cached:
        await send(f"No cached data for {coin}.")
        return

    expl = cached.get("explanation", {})
    await send(
        f"📋 *Trade Thesis — {coin}USDT*\n\n"
        f"Confidence: `{expl.get('confidence_label', '--')}`\n\n"
        f"*Why This Trade:*\n"
        f"{expl.get('thesis', 'No thesis data')}\n\n"
        f"*Risk Factors:*\n"
        f"{expl.get('risk_thesis', 'No risk data')}"
    )