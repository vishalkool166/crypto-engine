import httpx
import logging
from datetime import datetime, timezone, timedelta
from fastapi import Request
from config import cfg
from database import SessionLocal, Trade
from trade.state import state_manager

log = logging.getLogger(__name__)

BASE   = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"
DOMAIN = "https://small-salaried-study.ngrok-free.dev"

IST = timezone(timedelta(hours=5, minutes=30))

_sent_signals  = set()
_pending_close = {}  # chat_id → trade_id waiting for close confirmation
_skip_reasons  = {}  # signal_key → "skipped"


def now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


# ═══════════════════════════════════════════════════════
# CORE SEND
# ═══════════════════════════════════════════════════════
async def send(message: str):
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured")
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/sendMessage",
                json={
                    "chat_id":    cfg.TELEGRAM_CHAT_ID,
                    "text":       message,
                    "parse_mode": "Markdown"
                },
                timeout=10
            )
            if r.status_code != 200:
                log.error(f"Telegram failed: {r.text}")
    except Exception as e:
        log.error(f"Telegram error: {e}")


async def send_with_keyboard(message: str, keyboard: list):
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{BASE}/sendMessage",
                json={
                    "chat_id":      cfg.TELEGRAM_CHAT_ID,
                    "text":         message,
                    "parse_mode":   "Markdown",
                    "reply_markup": {
                        "inline_keyboard": keyboard
                    }
                },
                timeout=10
            )
            if r.status_code != 200:
                log.error(f"Telegram keyboard send failed: {r.text}")
    except Exception as e:
        log.error(f"Telegram keyboard error: {e}")


async def answer_callback(callback_id: str, text: str = ""):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{BASE}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text},
                timeout=5
            )
    except Exception as e:
        log.error(f"Answer callback error: {e}")


# ═══════════════════════════════════════════════════════
# WEBHOOK
# ═══════════════════════════════════════════════════════
async def register_webhook():
    webhook_url = f"{DOMAIN}/webhook/telegram"
    try:
        async with httpx.AsyncClient() as client:
            r    = await client.post(
                f"{BASE}/setWebhook",
                json={"url": webhook_url},
                timeout=10
            )
            data = r.json()
            if data.get("ok"):
                log.info(f"Webhook registered: {webhook_url}")
            else:
                log.error(f"Webhook failed: {data}")
    except Exception as e:
        log.error(f"Webhook register error: {e}")


async def handle_webhook(request: Request):
    try:
        data = await request.json()

        # Handle inline keyboard callbacks
        if "callback_query" in data:
            await _handle_callback(data["callback_query"])
            return

        msg     = data.get("message", {})
        text    = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if chat_id != str(cfg.TELEGRAM_CHAT_ID):
            return

        await _handle_command(text)

    except Exception as e:
        log.error(f"Webhook handler error: {e}")


# ═══════════════════════════════════════════════════════
# CALLBACK HANDLER — inline keyboard button presses
# ═══════════════════════════════════════════════════════
async def _handle_callback(callback: dict):
    callback_id = callback.get("id", "")
    data        = callback.get("data", "")
    chat_id     = str(callback.get("from", {}).get("id", ""))

    if chat_id != str(cfg.TELEGRAM_CHAT_ID):
        await answer_callback(callback_id, "Unauthorized")
        return

    await answer_callback(callback_id)

    if data.startswith("factors:"):
        coin = data.split(":")[1]
        await _cb_show_factors(coin)

    elif data.startswith("risks:"):
        coin = data.split(":")[1]
        await _cb_show_risks(coin)

    elif data.startswith("approve:"):
        coin = data.split(":")[1]
        await _cb_approve_signal(coin)

    elif data.startswith("skip:"):
        coin = data.split(":")[1]
        await _cb_skip_signal(coin)

    elif data == "confirm_close":
        await _cb_confirm_close()

    elif data == "cancel_close":
        await send("❌ Close cancelled — trade continues.")


async def _cb_show_factors(coin: str):
    from data.cache import cache
    cached = cache.get(f"signal_{coin}")
    if not cached:
        await send(f"⚠️ No cached data for {coin}. Run /scan first.")
        return

    wconf   = cached.get("wconf", {})
    factors = wconf.get("factors", [])
    score   = cached.get("score", 0)

    if not factors:
        await send(f"No factor data for {coin}.")
        return

    lines = [f"📊 *Confluence Factors — {coin}USDT*\n"]
    lines.append(f"Score: `{score}/100` · Earned: `{wconf.get('total_earned',0)}/{wconf.get('max_possible',0)}`\n")

    for f in factors:
        pct   = round(f["earned"] / f["max"] * 100) if f["max"] > 0 else 0
        icon  = "✅" if f["pass"] else "❌"
        bar   = "█" * (pct // 10) + "░" * (10 - pct // 10)
        lines.append(
            f"{icon} *{f['label']}*\n"
            f"`{bar}` {f['earned']}/{f['max']}\n"
            f"_{f.get('detail', '')}_\n"
        )

    await send("\n".join(lines))


async def _cb_show_risks(coin: str):
    from data.cache import cache
    cached = cache.get(f"signal_{coin}")
    if not cached:
        await send(f"⚠️ No cached data for {coin}.")
        return

    expl        = cached.get("explanation", {})
    risk_thesis = expl.get("risk_thesis", "")
    no_trade    = cached.get("no_trade", {})
    softs       = no_trade.get("soft_blocks", []) if no_trade else []

    lines = [f"⚠️ *Risk Analysis — {coin}USDT*\n"]

    if risk_thesis:
        lines.append("*Risk Factors:*")
        lines.append(risk_thesis)

    if softs:
        lines.append("\n*Score Penalties:*")
        for s in softs:
            lines.append(f"⚠ {s['reason']} `(-{s.get('penalty',0)}pts)`")

    if not risk_thesis and not softs:
        lines.append("No significant risk factors identified.")

    await send("\n".join(lines))


async def _cb_approve_signal(coin: str):
    from data.cache import cache
    from trade.manager import trade_manager

    cached = cache.get(f"signal_{coin}")
    if not cached:
        await send(f"⚠️ Signal for {coin} expired. Run /scan for fresh data.")
        return

    signal = cached.get("signal", {})
    grade  = signal.get("grade", "F")
    dir_   = signal.get("direction", "")

    if grade not in cfg.MIN_GRADE_TO_TRADE:
        await send(f"⚠️ Grade {grade} no longer meets minimum. Signal expired.")
        return

    if dir_ not in ["LONG", "SHORT"]:
        await send(f"⚠️ Signal direction invalid: {dir_}")
        return

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        await send(
            f"⚠️ Already in trade: `{trade.coin}USDT {trade.direction}`\n"
            f"Close current trade first."
        )
        return

    await send(f"✅ *Approved* — Opening `{coin}USDT {dir_}`...")

    signal["coin"] = coin
    result = await trade_manager.open_trade(
        signal    = signal,
        signal_id = signal.get("db_id")
    )

    if not result["success"]:
        await send(f"❌ Trade failed: `{result['reason']}`")


async def _cb_skip_signal(coin: str):
    _skip_reasons[coin] = "skipped_via_telegram"
    await send(
        f"⏭ *{coin} signal skipped*\n\n"
        f"Signal will not auto-execute this scan.\n"
        f"Use /scan to get fresh signals."
    )
    log.info(f"Signal skipped via Telegram: {coin}")


async def _cb_confirm_close():
    from trade.manager import trade_manager

    if state_manager.is_idle:
        await send("⚠️ No active trade to close.")
        return

    trade = state_manager.current_trade
    await send(f"⏳ Closing `{trade.coin}USDT {trade.direction}`...")

    result = await trade_manager.manual_close()
    if result["success"]:
        await send("✅ Trade closed manually.")
    else:
        await send(f"❌ Close failed: `{result['reason']}`")


# ═══════════════════════════════════════════════════════
# COMMAND HANDLER
# ═══════════════════════════════════════════════════════
async def _handle_command(text: str):
    text_lower = text.lower().strip()

    # Named commands
    if text_lower == "/status": await _cmd_status(); return
    if text_lower == "/pnl":    await _cmd_pnl();    return
    if text_lower == "/close":  await _cmd_close();  return
    if text_lower == "/queue":  await _cmd_queue();  return
    if text_lower == "/daily":  await _cmd_daily();  return
    if text_lower == "/scan":   await _cmd_scan();   return
    if text_lower == "/help":   await _cmd_help();   return

    # Natural language fallback
    await _handle_natural_language(text_lower)


async def _handle_natural_language(text: str):
    # Trade status queries
    if any(w in text for w in ["how's the trade", "trade going", "whats happening", "what's happening", "status"]):
        await _cmd_status()
        return

    # Why this trade
    if any(w in text for w in ["why", "reason", "thesis", "explain"]):
        if not state_manager.is_idle:
            trade = state_manager.current_trade
            await _show_active_thesis(trade.coin)
        else:
            await send("No active trade. Use /queue to see pending signals.")
        return

    # PnL queries
    if any(w in text for w in ["pnl", "profit", "loss", "how much", "performance"]):
        await _cmd_pnl()
        return

    # BTC queries
    if any(w in text for w in ["btc", "bitcoin"]):
        await _show_coin_summary("BTC")
        return

    # Coin queries — "how's eth", "what's sol doing"
    for coin in cfg.COINS:
        if coin.lower() in text:
            await _show_coin_summary(coin)
            return

    # Scan queries
    if any(w in text for w in ["scan", "signal", "setup", "opportunity"]):
        await _cmd_scan()
        return

    # Close queries
    if any(w in text for w in ["close", "exit", "get out"]):
        await _cmd_close()
        return

    # Unknown
    await send(
        "🤖 I didn't understand that.\n\n"
        "Try: /help for commands\n"
        "Or ask: _'how's the trade'_, _'why this trade'_, _'how's BTC'_"
    )


async def _show_active_thesis(coin: str):
    from data.cache import cache
    cached = cache.get(f"signal_{coin}")
    if not cached:
        await send(f"No cached data for {coin}.")
        return

    expl   = cached.get("explanation", {})
    thesis = expl.get("thesis", "")
    risk   = expl.get("risk_thesis", "")
    conf   = expl.get("confidence_label", "")

    await send(
        f"📋 *Trade Thesis — {coin}USDT*\n\n"
        f"Confidence: `{conf}`\n\n"
        f"*Why This Trade:*\n{thesis or 'No thesis data'}\n\n"
        f"*Risk Factors:*\n{risk or 'No risk data'}"
    )


async def _show_coin_summary(coin: str):
    from data.cache import cache
    cached = cache.get(f"signal_{coin}")
    if not cached:
        await send(f"No data for {coin}. Run /scan first.")
        return

    market  = cached.get("market", {})
    grade   = cached.get("grade", "F")
    dir_    = cached.get("direction", "--")
    score   = cached.get("score", 0)
    regime  = cached.get("regime", "--")
    session = cached.get("session", "--")
    price   = market.get("price", 0)
    change  = market.get("change24", 0)
    sign    = "+" if change >= 0 else ""
    em      = "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁"

    await send(
        f"📊 *{coin}USDT Summary*\n\n"
        f"Price:   `${price:,.4f}` ({sign}{change:.2f}%)\n"
        f"Grade:   `{grade}` · Score `{score}/100`\n"
        f"Signal:  {em} `{dir_}`\n"
        f"Regime:  `{regime}`\n"
        f"Session: `{session}`\n\n"
        f"Tap the radar card on dashboard for full breakdown."
    )


# ═══════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════
async def _cmd_status():
    if state_manager.is_idle:
        await send(
            "📊 *Bot Status*\n\n"
            "State: `IDLE`\n"
            "No active trade.\n"
            "Scanning every 15 minutes.\n\n"
            "Use /scan to trigger manual scan."
        )
        return

    trade = state_manager.current_trade
    if not trade:
        await send("📊 *Status*\nNo active trade.")
        return

    from trade.orders import get_current_price
    from trade.risk import risk_guard
    current  = get_current_price(trade.coin)
    upnl     = risk_guard.calculate_unrealized_pnl(
        direction     = trade.direction,
        entry_price   = trade.entry_price,
        current_price = current,
        pos_size      = trade.position_size
    )
    pnl_emoji    = "📈" if upnl >= 0 else "📉"
    health_state = state_manager.health_state
    health_emoji = "✅" if health_state == "HEALTHY" else "⚠️" if health_state == "WARNING" else "🚨"

    await send(
        f"📊 *Bot Status — IN TRADE*\n\n"
        f"Coin:    `{trade.coin}USDT`\n"
        f"Dir:     `{trade.direction}`\n"
        f"Grade:   `{trade.grade}`\n"
        f"State:   `{trade.state}`\n\n"
        f"Entry:   `{trade.entry_price}`\n"
        f"Current: `{current}`\n"
        f"SL:      `{trade.sl_price}`\n"
        f"TP1:     `{trade.tp1_price}`\n"
        f"TP2:     `{trade.tp2_price}`\n\n"
        f"{pnl_emoji} uPnL: `${upnl}`\n"
        f"Risk:    `${trade.risk_amt}`\n"
        f"{health_emoji} Health: `{health_state}`\n"
    )


async def _cmd_pnl():
    from trade.risk import risk_guard
    stats     = risk_guard.get_daily_stats()
    pnl_emoji = "📈" if stats["total_pnl"] >= 0 else "📉"

    db = SessionLocal()
    try:
        all_trades = db.query(Trade).filter(
            Trade.outcome != "pending"
        ).all()
        total_pnl = sum(t.pnl or 0 for t in all_trades)
        wins      = len([t for t in all_trades if t.outcome == "win"])
        losses    = len([t for t in all_trades if t.outcome == "loss"])
        total     = len(all_trades)
        wr        = round(wins / total * 100, 1) if total else 0
    finally:
        db.close()

    await send(
        f"💰 *PnL Report*\n\n"
        f"*Today*\n"
        f"Trades:  `{stats['trades_taken']}`\n"
        f"{pnl_emoji} PnL: `${stats['total_pnl']}`\n"
        f"Loss:    `${stats['total_loss']}`\n"
        f"Cap Hit: `{'YES 🚫' if stats['cap_hit'] else 'NO ✅'}`\n\n"
        f"*All Time*\n"
        f"Total:   `{total}` trades\n"
        f"Wins:    `{wins}` · Losses: `{losses}`\n"
        f"WR:      `{wr}%`\n"
        f"PnL:     `${round(total_pnl, 2)}`\n"
    )


async def _cmd_close():
    if state_manager.is_idle:
        await send("⚠️ No active trade to close.")
        return

    trade = state_manager.current_trade
    if not trade:
        await send("⚠️ No active trade.")
        return

    from trade.orders import get_current_price
    from trade.risk import risk_guard
    current = get_current_price(trade.coin)
    upnl    = risk_guard.calculate_unrealized_pnl(
        direction     = trade.direction,
        entry_price   = trade.entry_price,
        current_price = current,
        pos_size      = trade.position_size
    )
    pnl_str = f"+${upnl:.4f}" if upnl >= 0 else f"-${abs(upnl):.4f}"

    await send_with_keyboard(
        f"⚠️ *Close {trade.coin}USDT {trade.direction}?*\n\n"
        f"Entry:   `{trade.entry_price}`\n"
        f"Current: `{current}`\n"
        f"uPnL:    `{pnl_str}`\n"
        f"Health:  `{state_manager.health_state}`\n\n"
        f"This cancels all SL/TP orders.",
        keyboard=[
            [
                {"text": "✅ Yes, Close", "callback_data": "confirm_close"},
                {"text": "❌ Cancel",     "callback_data": "cancel_close"}
            ]
        ]
    )


async def _cmd_queue():
    from data.cache import cache
    best       = None
    best_score = 0

    for coin in cfg.COINS:
        if coin in _skip_reasons:
            continue
        cached = cache.get(f"signal_{coin}")
        if cached:
            score = cached.get("score", 0)
            grade = cached.get("grade", "F")
            if score > best_score and grade in ["A+", "A"]:
                best       = cached
                best_score = score

    if not best:
        await send(
            "📋 *Signal Queue*\n\n"
            "No A/A+ signals in cache.\n"
            "Use /scan to scan now."
        )
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
            "Waiting for current trade to close."
            if not state_manager.is_idle else
            "Bot is idle — tap Approve to execute."
        ),
        keyboard=[
            [
                {"text": "📊 Factors",    "callback_data": f"factors:{coin}"},
                {"text": "⚠️ Risks",      "callback_data": f"risks:{coin}"}
            ],
            [
                {"text": "✅ Approve",    "callback_data": f"approve:{coin}"},
                {"text": "❌ Skip",       "callback_data": f"skip:{coin}"}
            ]
        ]
    )


async def _cmd_daily():
    from trade.risk import risk_guard
    stats = risk_guard.get_daily_stats()
    await send(
        f"📅 *Daily Summary*\n\n"
        f"Date:      `{stats['date']}`\n"
        f"Trades:    `{stats['trades_taken']}/{cfg.MAX_TRADES_PER_DAY}`\n"
        f"PnL:       `${stats['total_pnl']}`\n"
        f"Loss:      `${stats['total_loss']}`\n\n"
        f"Remaining trades: `{stats['remaining_trades']}`\n"
        f"Remaining loss:   `${stats['remaining_loss']}`\n"
        f"Cap hit: `{'YES 🚫' if stats['cap_hit'] else 'NO ✅'}`\n"
    )


async def _cmd_scan():
    await send(
        "🔍 *Manual Scan Started*\n\n"
        "Scanning all coins...\n"
        "This takes 1-2 minutes.\n"
        "You'll get alerts for any A/A+ signals."
    )
    try:
        from alerts.scanner import scan_all_coins
        results   = await scan_all_coins()
        tradeable = [
            r for r in results
            if r.get("grade") in ["A+", "A"] and
            r.get("direction") in ["LONG", "SHORT"]
        ]
        aplus   = [r for r in tradeable if r.get("grade") == "A+"]
        a       = [r for r in tradeable if r.get("grade") == "A"]
        summary = (
            f"✅ *Scan Complete*\n\n"
            f"Coins scanned: `{len(results)}`\n"
            f"A+ signals:    `{len(aplus)}`\n"
            f"A signals:     `{len(a)}`\n\n"
        )
        if aplus:         summary += f"🏆 {len(aplus)} A+ found!\n"
        if a:             summary += f"✅ {len(a)} A found!\n"
        if not tradeable: summary += "😴 No tradeable signals found.\n"
        summary += f"\nNext auto scan at next :00/:15/:30/:45 UTC"
        await send(summary)
    except Exception as e:
        await send(f"❌ *Scan Failed*\n\n`{str(e)}`")


async def _cmd_help():
    await send(
        "🤖 *Signal Engine v5 Commands*\n\n"
        "/status — current trade state\n"
        "/pnl    — today + all time PnL\n"
        "/close  — close trade (with confirmation)\n"
        "/queue  — best signal + approve/skip\n"
        "/daily  — daily risk summary\n"
        "/scan   — trigger manual scan\n"
        "/help   — this message\n\n"
        "*Natural Language:*\n"
        "_'how's the trade'_ — trade status\n"
        "_'why this trade'_ — thesis\n"
        "_'how's BTC'_ — coin summary\n"
        "_'show risks'_ — risk factors\n"
    )


# ═══════════════════════════════════════════════════════
# SIGNAL ALERT — with inline keyboard
# ═══════════════════════════════════════════════════════
async def send_signal(
    signal:  dict,
    coin:    str,
    regime:  str,
    session: str
):
    if signal.get("grade") not in ["A+", "A"]:
        return
    if signal.get("direction") not in ["LONG", "SHORT"]:
        return
    if coin in _skip_reasons:
        return

    sig_key = (
        f"{coin}_"
        f"{signal.get('direction')}_"
        f"{signal.get('grade')}_"
        f"{round(signal.get('entry', 0), 0)}"
    )
    if sig_key in _sent_signals:
        return
    _sent_signals.add(sig_key)
    if len(_sent_signals) > 100:
        _sent_signals.pop()

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

    thesis_block = f"\n*Why This Trade?*\n{thesis}\n" if thesis else ""
    conf_block   = f"Confidence: `{conf_label} ({score}/100)`\n" if conf_label else ""

    await send_with_keyboard(
        f"{emoji} *Grade {grade} — {direction}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*{coin}USDT — {dir_emoji} {direction}*\n"
        f"{conf_block}"
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
        f"Lev:     `{cfg.LEVERAGE}x`\n"
        f"{thesis_block}",
        keyboard=[
            [
                {"text": "📊 Show Factors", "callback_data": f"factors:{coin}"},
                {"text": "⚠️ Show Risks",   "callback_data": f"risks:{coin}"}
            ],
            [
                {"text": "✅ Approve",       "callback_data": f"approve:{coin}"},
                {"text": "❌ Skip",          "callback_data": f"skip:{coin}"}
            ]
        ]
    )


# ═══════════════════════════════════════════════════════
# SCAN SUMMARY — shows closest setups even when no signals
# ═══════════════════════════════════════════════════════
async def send_scan_summary(results: list):
    tradeable = [
        r for r in results
        if r.get("grade") in ["A+", "A"] and
        r.get("direction") in ["LONG", "SHORT"]
    ]

    if tradeable:
        lines = [
            f"🔍 *Scan Complete — {now_ist()}*\n"
            f"{len(tradeable)} tradeable signal(s)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        ]
        for r in tradeable[:3]:
            g         = r.get("grade", "?")
            emoji     = "🏆" if g == "A+" else "✅"
            direction = r.get("direction", "?")
            dir_emoji = "📈" if direction == "LONG" else "📉"
            score     = r.get("score", 0)
            coin      = r.get("coin", "?")
            expl      = r.get("explanation", {})
            conf      = expl.get("confidence_label", "")
            conf_str  = f" · {conf}" if conf else ""
            lines.append(
                f"{emoji} *{coin}* — Grade {g} ({score}/100){conf_str}\n"
                f"{dir_emoji} {direction}\n"
            )

        if not state_manager.is_idle:
            trade = state_manager.current_trade
            lines.append(f"\n⚡ Active trade: {trade.coin} {trade.direction}")
        else:
            lines.append(f"\n💤 Bot idle — will execute best signal")

        lines.append(f"\nNext scan: next :00/:15/:30/:45 UTC")
        await send("\n".join(lines))
        return

    # No tradeable signals — show closest setups
    watching = [
        r for r in results
        if r.get("grade") == "B" and
        r.get("direction") in ["LONG", "SHORT"]
    ]
    building = [
        r for r in results
        if r.get("grade") == "C"
    ]

    lines = [
        f"😴 *No Tradeable Signals — {now_ist()}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    if watching:
        lines.append("*Closest Setups:*")
        for r in watching[:3]:
            d      = r.get("direction", "?")
            s      = r.get("score", 0)
            em     = "📈" if d == "LONG" else "📉"
            no_t   = r.get("no_trade", {})
            hards  = no_t.get("hard_blocks", []) if no_t else []
            reason = hards[0]["reason"] if hards else "setup building"
            lines.append(
                f"{em} `{r['coin']}` — B ({s}/100)\n"
                f"_{reason}_\n"
            )

    if building and not watching:
        lines.append("*Building:*")
        for r in building[:2]:
            lines.append(f"👁 `{r['coin']}` — C ({r.get('score',0)}/100)")

    if not watching and not building:
        lines.append("No setups building across all coins.")

    lines.append(f"\nNext scan: next :00/:15/:30/:45 UTC")
    await send("\n".join(lines))


# ═══════════════════════════════════════════════════════
# TRADE PROGRESS UPDATE
# Called from price_feed milestone tracker
# ═══════════════════════════════════════════════════════
async def send_progress_update(
    trade,
    current_price: float,
    milestone_pct: int
):
    is_long  = trade.direction == "LONG"
    entry    = trade.entry_price
    tp1      = trade.tp1_price
    sl       = trade.sl_price
    dist_tp1 = abs(tp1 - current_price) if tp1 else 0

    upnl = (
        (current_price - entry) / entry * trade.position_size
        if is_long else
        (entry - current_price) / entry * trade.position_size
    )
    pnl_str  = f"+${upnl:.4f}" if upnl >= 0 else f"-${abs(upnl):.4f}"
    health   = state_manager.health_state
    h_emoji  = "✅" if health == "HEALTHY" else "⚠️" if health == "WARNING" else "🚨"

    await send(
        f"⚡ *{trade.coin}USDT — {milestone_pct}% to TP1*\n\n"
        f"Price:   `${current_price:,.4f}`\n"
        f"Entry:   `{entry}`\n"
        f"TP1:     `{tp1}` — `${dist_tp1:,.4f}` away\n"
        f"SL:      `{sl}`\n\n"
        f"uPnL:    `{pnl_str}`\n"
        f"{h_emoji} Health: `{health}`\n\n"
        f"Type /status for full details"
    )