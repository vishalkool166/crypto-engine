import httpx
import logging
from fastapi import Request
from config import cfg
from database import SessionLocal, Trade
from trade.state import state_manager

log = logging.getLogger(__name__)

BASE    = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"
DOMAIN  = "https://small-salaried-study.ngrok-free.dev"

# Duplicate prevention for signals only
_sent_signals = set()

# ═══════════════════════════════════════════════════════
# BASE SEND
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

# ═══════════════════════════════════════════════════════
# REGISTER WEBHOOK
# ═══════════════════════════════════════════════════════
async def register_webhook():
    webhook_url = f"{DOMAIN}/webhook/telegram"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
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

# ═══════════════════════════════════════════════════════
# WEBHOOK HANDLER
# called by FastAPI route on every Telegram update
# ═══════════════════════════════════════════════════════
async def handle_webhook(request: Request):
    try:
        data    = await request.json()
        msg     = data.get("message", {})
        text    = msg.get("text", "").strip().lower()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if chat_id != str(cfg.TELEGRAM_CHAT_ID):
            return

        await _handle_command(text)
    except Exception as e:
        log.error(f"Webhook handler error: {e}")

# ═══════════════════════════════════════════════════════
# COMMAND HANDLER
# ═══════════════════════════════════════════════════════
async def _handle_command(text: str):
    if text == "/status":
        await _cmd_status()
    elif text == "/pnl":
        await _cmd_pnl()
    elif text == "/close":
        await _cmd_close()
    elif text == "/queue":
        await _cmd_queue()
    elif text == "/daily":
        await _cmd_daily()
    elif text == "/scan":
        await _cmd_scan()
    elif text == "/help":
        await _cmd_help()

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
    current = get_current_price(trade.coin)
    upnl    = risk_guard.calculate_unrealized_pnl(
        direction     = trade.direction,
        entry_price   = trade.entry_price,
        current_price = current,
        pos_size      = trade.position_size
    )
    pnl_emoji = "📈" if upnl >= 0 else "📉"
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
    )

async def _cmd_pnl():
    from trade.risk import risk_guard
    stats     = risk_guard.get_daily_stats()
    pnl_emoji = "📈" if stats["total_pnl"] >= 0 else "📉"
    db = SessionLocal()
    try:
        from database import Trade as TradeModel
        all_trades = db.query(TradeModel).filter(
            TradeModel.outcome != "pending"
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
    await send(f"⏳ Closing {trade.coin} {trade.direction}...")
    from trade.manager import trade_manager
    result = await trade_manager.manual_close()
    if result["success"]:
        await send("✅ Trade closed manually.")
    else:
        await send(f"❌ Close failed: {result['reason']}")

async def _cmd_queue():
    from data.cache import cache
    best       = None
    best_score = 0
    for coin in cfg.COINS:
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
    sig = best.get("signal", {})
    await send(
        f"📋 *Next Signal — Grade {best['grade']}*\n\n"
        f"Coin:  `{best['coin']}USDT`\n"
        f"Dir:   `{best['direction']}`\n"
        f"Score: `{best['score']}/100`\n\n"
        f"Entry: `{sig.get('entry', '--')}`\n"
        f"SL:    `{sig.get('sl', '--')}`\n"
        f"TP1:   `{sig.get('tp1', '--')}`\n"
        f"TP2:   `{sig.get('tp2', '--')}`\n\n" +
        (
            "Waiting for current trade to close."
            if not state_manager.is_idle else
            "Bot is idle — will execute on next scan."
        )
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
            if r.get("grade") in ["A+", "A"]
            and r.get("direction") in ["LONG", "SHORT"]
        ]
        aplus = [r for r in tradeable if r.get("grade") == "A+"]
        a     = [r for r in tradeable if r.get("grade") == "A"]
        summary = (
            f"✅ *Scan Complete*\n\n"
            f"Coins scanned: `{len(results)}`\n"
            f"A+ signals:    `{len(aplus)}`\n"
            f"A signals:     `{len(a)}`\n\n"
        )
        if aplus:   summary += f"🏆 {len(aplus)} A+ found!\n"
        if a:       summary += f"✅ {len(a)} A found!\n"
        if not tradeable: summary += "😴 No tradeable signals found.\n"
        summary += f"\nNext auto scan in 15 minutes."
        await send(summary)
    except Exception as e:
        await send(f"❌ *Scan Failed*\n\n`{str(e)}`")

async def _cmd_help():
    await send(
        "🤖 *Signal Engine v5 Commands*\n\n"
        "/status — current trade state\n"
        "/pnl    — today + all time PnL\n"
        "/close  — manually close trade\n"
        "/queue  — best signal waiting\n"
        "/daily  — daily risk summary\n"
        "/scan   — trigger manual scan now\n"
        "/help   — this message\n"
    )

# ═══════════════════════════════════════════════════════
# SEND SIGNAL ALERT
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
        _sent_signals.clear()

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

    await send(
        f"{emoji} *Grade {grade} — {direction}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*{coin}USDT — {dir_emoji} {direction}*\n"
        f"Score:   `{score}/100`\n"
        f"Regime:  `{regime}`\n"
        f"Session: `{session}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Entry:   `{entry:.4f}`\n"
        f"SL:      `{sl:.4f}` ({sl_pct:.2f}%)\n"
        f"TP1:     `{tp1:.4f}`\n"
        f"TP2:     `{tp2:.4f}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Risk:    `${risk_amt:.2f}`\n"
        f"Size:    `${pos_size:.2f}`\n"
        f"Lev:     `{cfg.LEVERAGE}x`\n"
    )

# ═══════════════════════════════════════════════════════
# SEND SCAN SUMMARY
# ═══════════════════════════════════════════════════════
async def send_scan_summary(results: list):
    tradeable = [
        r for r in results
        if r.get("grade") in ["A+", "A"]
        and r.get("direction") in ["LONG", "SHORT"]
    ]
    if not tradeable:
        return

    lines = [
        f"🔍 *Scan Complete*\n"
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
        lines.append(
            f"{emoji} *{coin}* — Grade {g} ({score}/100)\n"
            f"{dir_emoji} {direction}\n"
        )

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        lines.append(f"\n⚡ Active trade: {trade.coin} {trade.direction}")
    else:
        lines.append(f"\n💤 Bot idle — will execute best signal")

    await send("\n".join(lines))