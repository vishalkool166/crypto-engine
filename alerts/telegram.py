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

_sent_signals = set()
_skip_reasons = {}


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
                json={
                    "callback_query_id": callback_id,
                    "text":              text
                },
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
# CALLBACK HANDLER
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
        await _cb_show_factors(data.split(":")[1])
    elif data.startswith("risks:"):
        await _cb_show_risks(data.split(":")[1])
    elif data.startswith("approve:"):
        await _cb_approve_signal(data.split(":")[1])
    elif data.startswith("skip:"):
        await _cb_skip_signal(data.split(":")[1])
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

    lines = [
        f"📊 *Confluence Factors — {coin}USDT*\n",
        f"Score: `{score}/100` · "
        f"Earned: `{wconf.get('total_earned',0)}"
        f"/{wconf.get('max_possible',0)}`\n"
    ]

    for f in factors:
        pct  = round(f["earned"] / f["max"] * 100) if f["max"] > 0 else 0
        icon = "✅" if f["pass"] else "❌"
        bar  = "█" * (pct // 10) + "░" * (10 - pct // 10)
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
            lines.append(
                f"⚠ {s['reason']} "
                f"`(-{s.get('penalty',0)}pts)`"
            )

    if not risk_thesis and not softs:
        lines.append("No significant risk factors identified.")

    await send("\n".join(lines))


async def _cb_approve_signal(coin: str):
    from data.cache import cache
    from trade.manager import trade_manager

    cached = cache.get(f"signal_{coin}")
    if not cached:
        await send(
            f"⚠️ Signal for {coin} expired. "
            f"Run /scan for fresh data."
        )
        return

    signal = cached.get("signal", {})
    grade  = signal.get("grade", "F")
    dir_   = signal.get("direction", "")

    if grade not in cfg.MIN_GRADE_TO_TRADE:
        await send(
            f"⚠️ Grade {grade} no longer meets minimum. "
            f"Signal expired."
        )
        return

    if dir_ not in ["LONG", "SHORT"]:
        await send(f"⚠️ Signal direction invalid: {dir_}")
        return

    if not state_manager.is_idle:
        trade = state_manager.current_trade
        await send(
            f"⚠️ Already in trade: "
            f"`{trade.coin}USDT {trade.direction}`\n"
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
    await send(
        f"⏳ Closing `{trade.coin}USDT {trade.direction}`..."
    )

    result = await trade_manager.manual_close()
    if result["success"]:
        await send("✅ Trade closed manually.")
    else:
        await send(f"❌ Close failed: `{result['reason']}`")


# ═══════════════════════════════════════════════════════
# COMMAND ROUTER
# ═══════════════════════════════════════════════════════
async def _handle_command(text: str):
    t = text.lower().strip()

    # Commands with arguments
    if t.startswith("/coin"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if coin in cfg.COINS:
            await _cmd_coin(coin)
        else:
            await send(
                f"⚠️ Unknown coin: `{coin}`\n"
                f"Supported: `{', '.join(cfg.COINS)}`"
            )
        return

    if t.startswith("/backtest"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if coin in cfg.COINS:
            await _cmd_backtest(coin)
        else:
            await send(
                f"⚠️ Usage: `/backtest BTC`\n"
                f"Supported coins: `{', '.join(cfg.TIER1)}`"
            )
        return

    # Named commands
    handlers = {
        "/status":   _cmd_status,
        "/pnl":      _cmd_pnl,
        "/close":    _cmd_close,
        "/queue":    _cmd_queue,
        "/daily":    _cmd_daily,
        "/scan":     _cmd_scan,
        "/help":     _cmd_help,
        "/thesis":   _cmd_thesis,
        "/health":   _cmd_health,
        "/levels":   _cmd_levels,
        "/btc":      _cmd_btc,
        "/regime":   _cmd_regime,
        "/funding":  _cmd_funding,
        "/fear":     _cmd_fear,
        "/history":  _cmd_history,
        "/stats":    _cmd_stats,
        "/streak":   _cmd_streak,
        "/grade":    _cmd_grade,
        "/risk":     _cmd_risk,
        "/session":  _cmd_session,
        "/next":     _cmd_next,
        "/pause":    _cmd_pause,
        "/resume":   _cmd_resume,
        "/mode":     _cmd_mode,
        "/brief":    _cmd_brief,
        "/factors":  _cmd_factors,
        "/debrief":  _cmd_debrief,
    }

    handler = handlers.get(t)
    if handler:
        await handler()
    else:
        await send(
            "🤖 Unknown command.\n\n"
            "Type /help for full command list."
        )


# ═══════════════════════════════════════════════════════
# TRADE COMMANDS
# ═══════════════════════════════════════════════════════
async def _cmd_status():
    if state_manager.is_idle:
        paused_note = (
            "\n⏸ Auto-execution is *PAUSED*\n"
            "Use /resume to re-enable."
            if state_manager.is_paused else ""
        )
        await send(
            f"📊 *Bot Status*\n\n"
            f"State: `IDLE`\n"
            f"No active trade.\n"
            f"Scanning every 15 minutes.{paused_note}\n\n"
            f"Use /scan to trigger manual scan."
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
    h_emoji      = (
        "✅" if health_state == "HEALTHY"     else
        "⚠️" if health_state == "WARNING"     else
        "🚨"
    )

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
        f"{h_emoji} Health: `{health_state}`\n"
    )


async def _cmd_thesis():
    if state_manager.is_idle:
        await send(
            "⚠️ No active trade.\n"
            "Use /queue to see pending signals."
        )
        return
    trade = state_manager.current_trade
    await _show_active_thesis(trade.coin)


async def _cmd_health():
    if state_manager.is_idle:
        await send("⚠️ No active trade — no health data.")
        return

    health = state_manager.health_data
    state  = state_manager.health_state

    h_emoji = (
        "✅" if state == "HEALTHY"     else
        "⚠️" if state == "WARNING"     else
        "🚨"
    )

    trade = state_manager.current_trade
    lines = [
        f"{h_emoji} *Trade Health — "
        f"{trade.coin if trade else '--'}*\n",
        f"Status: `{state}`\n"
    ]

    failures = health.get("failures", [])
    warnings = health.get("warnings", [])
    checks   = health.get("checks", [])

    if failures:
        lines.append("*Invalidated:*")
        for f in failures:
            lines.append(f"✘ {f}")

    if warnings:
        lines.append("\n*Warnings:*")
        for w in warnings:
            lines.append(f"⚠ {w}")

    if checks and state == "HEALTHY":
        lines.append("\n*Healthy:*")
        for c in checks:
            lines.append(f"✔ {c}")

    if state == "INVALIDATED":
        lines.append(
            "\n_Thesis invalidated. "
            "Use /close if you want to exit._"
        )
    elif state == "WARNING":
        lines.append("\n_Thesis weakening. Monitor position._")
    else:
        lines.append("\n_Thesis intact. Hold position._")

    await send("\n".join(lines))


async def _cmd_levels():
    if state_manager.is_idle:
        await send("⚠️ No active trade — no levels to show.")
        return

    trade = state_manager.current_trade
    if not trade:
        return

    from trade.orders import get_current_price
    from trade.risk import risk_guard
    from trade.price_feed import price_feed

    current  = price_feed.get_price(trade.coin) or get_current_price(trade.coin)
    is_long  = trade.direction == "LONG"
    tp1_hit  = (
        abs(trade.sl_price - trade.entry_price) /
        trade.entry_price < 0.001
        if trade.sl_price and trade.entry_price else False
    )

    upnl = risk_guard.calculate_unrealized_pnl(
        direction     = trade.direction,
        entry_price   = trade.entry_price,
        current_price = current,
        pos_size      = trade.position_size
    )

    total    = abs(trade.tp1_price - trade.entry_price) if trade.tp1_price and trade.entry_price else 0
    progress = 0
    if total > 0:
        if is_long:
            progress = (current - trade.entry_price) / total * 100
        else:
            progress = (trade.entry_price - current) / total * 100
    progress = max(0, min(100, progress))

    sl_label = "BE ✅" if tp1_hit else "SL 🛑"
    pnl_str  = f"+${upnl:.4f}" if upnl >= 0 else f"-${abs(upnl):.4f}"

    await send(
        f"📐 *Price Levels — {trade.coin}USDT*\n\n"
        f"TP2:     `{trade.tp2_price}`\n"
        f"TP1:     `{trade.tp1_price}`"
        f"{'  ✅ HIT' if tp1_hit else ''}\n"
        f"NOW:     `{current:.4f}` ← live\n"
        f"Entry:   `{trade.entry_price}`\n"
        f"{sl_label}: `{trade.sl_price}`\n\n"
        f"Progress to TP1: `{progress:.0f}%`\n"
        f"uPnL: `{pnl_str}`\n"
    )


async def _cmd_close():
    if state_manager.is_idle:
        await send("⚠️ No active trade to close.")
        return

    trade = state_manager.current_trade
    if not trade:
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


# ═══════════════════════════════════════════════════════
# MARKET COMMANDS
# ═══════════════════════════════════════════════════════
async def _cmd_btc():
    await _cmd_coin("BTC")


async def _cmd_coin(coin: str):
    from data.cache import cache
    cached = cache.get(f"signal_{coin}")
    if not cached:
        await send(
            f"No data for `{coin}`. Run /scan first."
        )
        return

    market  = cached.get("market", {})
    grade   = cached.get("grade", "F")
    dir_    = cached.get("direction", "--")
    score   = cached.get("score", 0)
    regime  = cached.get("regime", "--")
    session = cached.get("session", "--")
    sweep   = cached.get("sweep", {})
    disp    = cached.get("displacement", {})
    retest  = cached.get("retest", {})
    d1d     = cached.get("d1d", {})
    expl    = cached.get("explanation", {})

    price   = market.get("price", 0)
    change  = market.get("change24", 0)
    funding = market.get("funding", 0) * 100
    sign    = "+" if change >= 0 else ""
    em      = "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁"

    rsi     = d1d.get("rsi")
    adx     = d1d.get("adx")
    trend   = d1d.get("trend", {}).get("cls", "--")
    conf    = expl.get("confidence_label", "")

    await send(
        f"📊 *{coin}USDT Analysis*\n\n"
        f"Price:   `${price:,.4f}` ({sign}{change:.2f}%)\n"
        f"Grade:   `{grade}` · Score `{score}/100`\n"
        f"Signal:  {em} `{dir_}`\n"
        f"Conf:    `{conf}`\n\n"
        f"Regime:  `{regime}`\n"
        f"Trend:   `{trend}`\n"
        f"Session: `{session}`\n\n"
        f"RSI:     `{rsi:.1f}`\n"
        f"ADX:     `{adx:.1f}`\n"
        f"Funding: `{funding:.4f}%`\n\n"
        f"Sweep:   `{'✅' if sweep.get('confirmed') else '❌'} {sweep.get('score',0)}/12`\n"
        f"Disp:    `{'✅' if disp.get('confirmed') else '❌'} {disp.get('score',0)}/11`\n"
        f"Retest:  `{'✅' if retest.get('confirmed') else '❌'} {retest.get('score',0)}/12`\n"
    ) if rsi and adx else await send(
        f"📊 *{coin}USDT Analysis*\n\n"
        f"Price:   `${price:,.4f}` ({sign}{change:.2f}%)\n"
        f"Grade:   `{grade}` · Score `{score}/100`\n"
        f"Signal:  {em} `{dir_}`\n"
        f"Regime:  `{regime}`\n"
        f"Session: `{session}`\n\n"
        f"Sweep:   `{'✅' if sweep.get('confirmed') else '❌'}`\n"
        f"Disp:    `{'✅' if disp.get('confirmed') else '❌'}`\n"
        f"Retest:  `{'✅' if retest.get('confirmed') else '❌'}`\n"
    )


async def _cmd_regime():
    from data.cache import cache
    lines = ["📈 *Market Regime — Tier 1*\n"]
    for coin in cfg.TIER1:
        cached = cache.get(f"signal_{coin}")
        if not cached:
            lines.append(f"`{coin}` — no data")
            continue
        regime = cached.get("regime", "--")
        grade  = cached.get("grade", "F")
        dir_   = cached.get("direction", "--")
        em     = "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁"
        lines.append(f"{em} `{coin}` — {regime} · Grade {grade}")

    await send("\n".join(lines))


async def _cmd_funding():
    from data.cache import cache
    lines = ["💸 *Funding Rates*\n"]
    for coin in cfg.COINS:
        cached = cache.get(f"signal_{coin}")
        if not cached:
            continue
        market  = cached.get("market", {})
        funding = market.get("funding", 0) * 100
        flag    = (
            "🚨" if abs(funding) > 0.08 else
            "⚠️" if abs(funding) > 0.05 else
            "✅"
        )
        lines.append(
            f"{flag} `{coin}` — `{funding:.4f}%`"
        )

    if len(lines) == 1:
        lines.append("No data — run /scan first")

    await send("\n".join(lines))


async def _cmd_fear():
    from data.fetcher import get_fear_greed
    try:
        fg    = await get_fear_greed()
        val   = fg.get("value", 50)
        label = fg.get("label", "Neutral")
        emoji = (
            "🟢" if val >= 60 else
            "🔴" if val <= 30 else
            "🟡"
        )
        await send(
            f"{emoji} *Fear & Greed Index*\n\n"
            f"Value: `{val}/100`\n"
            f"Label: `{label}`\n\n"
            f"_Above 75 = Extreme Greed — caution_\n"
            f"_Below 25 = Extreme Fear — opportunity_"
        )
    except Exception as e:
        await send(f"❌ Fear & Greed fetch failed: `{e}`")


# ═══════════════════════════════════════════════════════
# PERFORMANCE COMMANDS
# ═══════════════════════════════════════════════════════
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


async def _cmd_history():
    db = SessionLocal()
    try:
        trades = db.query(Trade).filter(
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss", "manual"])
        ).order_by(Trade.closed_at.desc()).limit(5).all()
    finally:
        db.close()

    if not trades:
        await send("📜 No closed trades yet.")
        return

    lines = ["📜 *Last 5 Trades*\n"]
    for t in trades:
        emoji  = "✅" if t.outcome == "win" else "❌" if t.outcome == "loss" else "⏹"
        pnl    = t.pnl or 0
        pnl_s  = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"
        dir_em = "📈" if t.direction == "LONG" else "📉"
        lines.append(
            f"{emoji} {dir_em} `{t.coin}` {t.direction} "
            f"Grade `{t.grade}` — `{pnl_s}`\n"
            f"_{t.close_reason or '--'}_\n"
        )

    await send("\n".join(lines))


async def _cmd_stats():
    from alerts.scanner import get_db_stats
    stats = get_db_stats()

    if not stats:
        await send("📊 No stats yet — no closed trades.")
        return

    bg   = stats.get("by_grade", {})
    ap   = bg.get("A+", {})
    a    = bg.get("A", {})

    await send(
        f"📊 *All Time Stats*\n\n"
        f"Total signals: `{stats.get('total', 0)}`\n"
        f"Closed:        `{stats.get('closed', 0)}`\n"
        f"Pending:       `{stats.get('pending', 0)}`\n\n"
        f"Wins:    `{stats.get('wins', 0)}`\n"
        f"Losses:  `{stats.get('losses', 0)}`\n"
        f"WR:      `{stats.get('win_rate', 0)}%`\n"
        f"PnL:     `${stats.get('total_pnl', 0)}`\n\n"
        f"*Grade A+*\n"
        f"Trades: `{ap.get('total',0)}` · "
        f"WR: `{ap.get('win_rate',0)}%` · "
        f"PnL: `${ap.get('total_pnl',0)}`\n\n"
        f"*Grade A*\n"
        f"Trades: `{a.get('total',0)}` · "
        f"WR: `{a.get('win_rate',0)}%` · "
        f"PnL: `${a.get('total_pnl',0)}`\n"
    )


async def _cmd_streak():
    db = SessionLocal()
    try:
        trades = db.query(Trade).filter(
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss"])
        ).order_by(Trade.closed_at.desc()).all()
    finally:
        db.close()

    if not trades:
        await send("📊 No closed trades yet.")
        return

    # Current streak
    current_streak = 0
    current_type   = trades[0].outcome if trades else None
    for t in trades:
        if t.outcome == current_type:
            current_streak += 1
        else:
            break

    # Max streaks
    max_wins   = 0
    max_losses = 0
    cur_w      = 0
    cur_l      = 0
    for t in reversed(trades):
        if t.outcome == "win":
            cur_w += 1
            cur_l  = 0
        else:
            cur_l += 1
            cur_w  = 0
        max_wins   = max(max_wins, cur_w)
        max_losses = max(max_losses, cur_l)

    streak_emoji = "🔥" if current_type == "win" else "❄️"

    await send(
        f"🔢 *Streak Report*\n\n"
        f"Current: {streak_emoji} "
        f"`{current_streak} {current_type}s`\n\n"
        f"All Time:\n"
        f"Max wins:   `{max_wins} in a row`\n"
        f"Max losses: `{max_losses} in a row`\n"
    )


async def _cmd_grade():
    from alerts.scanner import get_db_stats
    stats = get_db_stats()
    bg    = stats.get("by_grade", {}) if stats else {}
    ap    = bg.get("A+", {})
    a     = bg.get("A", {})

    await send(
        f"🏆 *Grade Accuracy*\n\n"
        f"*Grade A+*\n"
        f"Trades:   `{ap.get('total', 0)}`\n"
        f"Wins:     `{ap.get('wins', 0)}`\n"
        f"Losses:   `{ap.get('losses', 0)}`\n"
        f"Win Rate: `{ap.get('win_rate', 0)}%`\n"
        f"PnL:      `${ap.get('total_pnl', 0)}`\n\n"
        f"*Grade A*\n"
        f"Trades:   `{a.get('total', 0)}`\n"
        f"Wins:     `{a.get('wins', 0)}`\n"
        f"Losses:   `{a.get('losses', 0)}`\n"
        f"Win Rate: `{a.get('win_rate', 0)}%`\n"
        f"PnL:      `${a.get('total_pnl', 0)}`\n\n"
        f"_Minimum 50 trades for reliable data_"
    )


# ═══════════════════════════════════════════════════════
# RISK & SESSION COMMANDS
# ═══════════════════════════════════════════════════════
async def _cmd_risk():
    from trade.risk import risk_guard
    stats     = risk_guard.get_daily_stats()
    daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
    loss_pct  = (
        abs(stats["total_loss"]) / daily_cap * 100
        if daily_cap > 0 else 0
    )
    cap_emoji = "🚫" if stats["cap_hit"] else "✅"

    await send(
        f"🛡️ *Daily Risk State*\n\n"
        f"Date:          `{stats['date']}`\n"
        f"Trades taken:  `{stats['trades_taken']}/{cfg.MAX_TRADES_PER_DAY}`\n"
        f"Trades left:   `{stats['remaining_trades']}`\n\n"
        f"Loss today:    `${abs(stats['total_loss']):.4f}`\n"
        f"Loss cap:      `${daily_cap:.4f}`\n"
        f"Used:          `{loss_pct:.1f}%`\n"
        f"Remaining:     `${stats['remaining_loss']:.4f}`\n\n"
        f"PnL today:     `${stats['total_pnl']:.4f}`\n"
        f"Cap status:    {cap_emoji} "
        f"`{'HIT' if stats['cap_hit'] else 'ACTIVE'}`\n"
    )


async def _cmd_session():
    from engines.signal import get_session
    from datetime import datetime, timezone
    session = get_session()
    now     = datetime.now(timezone.utc)

    tradeable_emoji = "✅" if session["tradeable"] else "🚫"

    # Time until London open (08:00 UTC)
    london_open = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now >= london_open:
        london_open = london_open.replace(
            day=london_open.day + 1
        )
    mins_to_london = int(
        (london_    mins_to_london = int(
        (london_open - now).total_seconds() / 60
    )
    hrs  = mins_to_london // 60
    mins = mins_to_london % 60

    await send(
        f"🕐 *Session Status*\n\n"
        f"Current:   `{session['name']}`\n"
        f"Quality:   `{session['quality']}`\n"
        f"Entries:   {tradeable_emoji} "
        f"`{'ALLOWED' if session['tradeable'] else 'BLOCKED'}`\n"
        f"Score:     `{session['score']}/9`\n\n"
        f"_{session['desc']}_\n\n"
        f"London open in: `{hrs}h {mins}m`\n"
        f"UTC now: `{now.strftime('%H:%M')}`"
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


async def _cmd_next():
    from scheduler import get_next_scan_time
    from engines.signal import get_session
    from datetime import datetime, timezone

    now     = datetime.now(timezone.utc)
    session = get_session()
    next_s  = get_next_scan_time()

    london_open = now.replace(
        hour=8, minute=0, second=0, microsecond=0
    )
    ny_open = now.replace(
        hour=13, minute=0, second=0, microsecond=0
    )

    if now >= london_open:
        london_open = london_open.replace(
            day=london_open.day + 1
        )
    if now >= ny_open:
        ny_open = ny_open.replace(
            day=ny_open.day + 1
        )

    def fmt_mins(dt):
        m = int((dt - now).total_seconds() / 60)
        return f"{m // 60}h {m % 60}m"

    await send(
        f"⏱ *Next Events*\n\n"
        f"Next scan:      `{next_s}`\n"
        f"London open:    `08:00 UTC` (in {fmt_mins(london_open)})\n"
        f"NY open:        `13:00 UTC` (in {fmt_mins(ny_open)})\n\n"
        f"Current session: `{session['name']}`\n"
        f"Entries: `{'✅ ALLOWED' if session['tradeable'] else '🚫 BLOCKED'}`"
    )


# ═══════════════════════════════════════════════════════
# BOT CONTROL COMMANDS
# ═══════════════════════════════════════════════════════
async def _cmd_pause():
    if state_manager.is_paused:
        await send(
            "⏸ Bot is already paused.\n"
            "Use /resume to re-enable auto-execution."
        )
        return
    state_manager.pause()
    await send(
        "⏸ *Auto-Execution Paused*\n\n"
        "Scanning continues every 15 minutes.\n"
        "Signals will alert you as normal.\n"
        "Bot will NOT auto-open trades.\n\n"
        "Use ✅ Approve on any signal to enter manually.\n"
        "Use /resume to re-enable auto-execution."
    )


async def _cmd_resume():
    if not state_manager.is_paused:
        await send(
            "▶️ Bot is already running.\n"
            "Auto-execution is active."
        )
        return
    state_manager.resume()
    await send(
        "▶️ *Auto-Execution Resumed*\n\n"
        "Next A+ signal will execute automatically.\n"
        "Scanning every 15 minutes."
    )


async def _cmd_mode():
    paused_str = (
        "⏸ PAUSED" if state_manager.is_paused
        else "▶️ AUTO"
    )
    trade_str = "IN TRADE" if not state_manager.is_idle else "IDLE"

    await send(
        f"⚙️ *Bot Configuration*\n\n"
        f"Mode:        `{'PAPER' if cfg.PAPER_TRADING else 'LIVE'}`\n"
        f"Execution:   `{paused_str}`\n"
        f"State:       `{trade_str}`\n\n"
        f"Capital:     `${cfg.CAPITAL}`\n"
        f"Leverage:    `{cfg.LEVERAGE}x`\n"
        f"Grades:      `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Max trades:  `{cfg.MAX_TRADES_PER_DAY}/day`\n"
        f"Daily cap:   `${cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT:.4f}`\n"
        f"Risk/trade:  `{cfg.RISK_PCT_PER_TRADE * 100:.0f}%`\n\n"
        f"Coins:       `{len(cfg.COINS)} coins`\n"
        f"Tier 1:      `{', '.join(cfg.TIER1)}`\n"
        f"Tier 2:      `{', '.join(cfg.TIER2)}`\n"
    )


async def _cmd_brief():
    from alerts.briefing import send_morning_briefing
    await send("🌅 Generating briefing...")
    await send_morning_briefing()


# ═══════════════════════════════════════════════════════
# ANALYSIS COMMANDS
# ═══════════════════════════════════════════════════════
async def _cmd_factors():
    from backtest.factor_analysis import run_factor_analysis
    await send("⏳ Running factor analysis...")
    result = run_factor_analysis()

    if "error" in result:
        await send(
            f"⚠️ *Factor Analysis*\n\n"
            f"{result['error']}\n\n"
            f"Need `{result.get('min_required', 200)}` "
            f"closed trades minimum."
        )
        return

    total    = result.get("total", 0)
    wr       = result.get("overall_wr", 0)
    reliable = result.get("reliable", False)
    rel_note = result.get("reliability", "")
    top      = result.get("top_factors", [])
    weak     = result.get("weak_factors", [])

    lines = [
        f"🔬 *Factor Analysis*\n",
        f"Trades: `{total}` · WR: `{wr}%`\n",
        f"_{rel_note}_\n"
    ]

    if top:
        lines.append("*Strong Edge:*")
        for f in top[:3]:
            lines.append(
                f"✅ `{f['factor']}` — "
                f"edge: `+{f['edge']}%` "
                f"({f['present_total']} trades)"
            )

    if weak:
        lines.append("\n*Weak/No Edge:*")
        for f in weak[:3]:
            lines.append(
                f"⚠️ `{f['factor']}` — "
                f"edge: `{f['edge']}%`"
            )

    if not reliable:
        lines.append(
            f"\n_Need {200 - total} more trades "
            f"for reliable conclusions_"
        )

    await send("\n".join(lines))


async def _cmd_backtest(coin: str):
    from backtest.engine import run_backtest
    await send(f"⏳ Running backtest for `{coin}`...")
    try:
        result = run_backtest(
            coin     = coin,
            capital  = cfg.CAPITAL,
            leverage = cfg.LEVERAGE
        )

        if "error" in result:
            await send(f"❌ Backtest failed: `{result['error']}`")
            return

        await send(
            f"📊 *Backtest — {coin}USDT*\n\n"
            f"Period: `{result.get('period_start')} → "
            f"{result.get('period_end')}`\n\n"
            f"Signals:  `{result.get('total_signals', 0)}`\n"
            f"Trades:   `{result.get('total_trades', 0)}`\n"
            f"Wins:     `{result.get('wins', 0)}`\n"
            f"Losses:   `{result.get('losses', 0)}`\n"
            f"Win Rate: `{result.get('win_rate', 0)}%`\n\n"
            f"PnL:      `${result.get('total_pnl', 0)}`\n"
            f"Return:   `{result.get('total_return', 0)}%`\n"
            f"PF:       `{result.get('profit_factor', 0)}`\n"
            f"Max DD:   `{result.get('max_drawdown', 0)}%`\n"
            f"Expect:   `${result.get('expectancy', 0)}`\n\n"
            f"*By Grade*\n"
            f"A+: `{result.get('by_grade',{}).get('A+',{}).get('win_rate',0)}% WR` · "
            f"`{result.get('by_grade',{}).get('A+',{}).get('trades',0)} trades`\n"
            f"A:  `{result.get('by_grade',{}).get('A',{}).get('win_rate',0)}% WR` · "
            f"`{result.get('by_grade',{}).get('A',{}).get('trades',0)} trades`\n"
        )
    except Exception as e:
        await send(f"❌ Backtest error: `{str(e)}`")


async def _cmd_debrief():
    db = SessionLocal()
    try:
        trade = db.query(Trade).filter(
            Trade.is_active == False,
            Trade.outcome.in_(["win", "loss", "manual"])
        ).order_by(Trade.closed_at.desc()).first()
    finally:
        db.close()

    if not trade:
        await send("📋 No closed trades yet.")
        return

    from alerts.briefing import send_post_trade_debrief
    await send_post_trade_debrief(
        trade           = trade,
        outcome         = trade.outcome,
        pnl             = trade.pnl or 0,
        close_reason    = trade.close_reason or "--",
        health_at_close = trade.health_at_close or "UNKNOWN"
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
                {"text": "📊 Factors", "callback_data": f"factors:{coin}"},
                {"text": "⚠️ Risks",   "callback_data": f"risks:{coin}"}
            ],
            [
                {"text": "✅ Approve", "callback_data": f"approve:{coin}"},
                {"text": "❌ Skip",    "callback_data": f"skip:{coin}"}
            ]
        ]
    )


async def _cmd_help():
    await send(
        "🤖 *Signal Engine v5 — Commands*\n\n"
        "*TRADE*\n"
        "/status  — trade state + health\n"
        "/thesis  — why this trade exists\n"
        "/health  — full health engine output\n"
        "/levels  — price ladder + progress\n"
        "/close   — close with confirmation\n\n"
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
        "/pause   — pause auto-execution\n"
        "/resume  — resume auto-execution\n"
        "/mode    — current config\n"
        "/brief   — morning briefing now\n\n"
        "*ANALYSIS*\n"
        "/backtest BTC — backtest a coin\n"
        "/factors      — factor analysis\n"
        "/debrief      — last trade debrief\n"
        "/help         — this message\n"
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

    explanation  = signal.get("explanation", {})
    thesis       = explanation.get("thesis", "")
    conf_label   = explanation.get("confidence_label", "")
    thesis_block = f"\n*Why This Trade?*\n{thesis}\n" if thesis else ""
    conf_block   = f"Confidence: `{conf_label} ({score}/100)`\n" if conf_label else ""

    paused_note = (
        "\n⏸ _Auto-execution paused — tap Approve to enter_\n"
        if state_manager.is_paused else ""
    )

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
        f"{thesis_block}"
        f"{paused_note}",
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
# SCAN SUMMARY
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
                f"{emoji} *{coin}* — Grade {g} "
                f"({score}/100){conf_str}\n"
                f"{dir_emoji} {direction}\n"
            )

        if not state_manager.is_idle:
            trade = state_manager.current_trade
            lines.append(
                f"\n⚡ Active trade: "
                f"{trade.coin} {trade.direction}"
            )
        else:
            lines.append(
                f"\n💤 Bot "
                f"{'PAUSED' if state_manager.is_paused else 'idle'}"
                f" — "
                f"{'tap Approve to enter' if state_manager.is_paused else 'will execute best signal'}"
            )

        lines.append(
            f"\nNext scan: next :00/:15/:30/:45 UTC"
        )
        await send("\n".join(lines))
        return

    # No tradeable signals — show closest
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
            lines.append(
                f"👁 `{r['coin']}` — "
                f"C ({r.get('score',0)}/100)"
            )

    if not watching and not building:
        lines.append(
            "No setups building across all coins."
        )

    lines.append(
        f"\nNext scan: next :00/:15/:30/:45 UTC"
    )
    await send("\n".join(lines))


# ═══════════════════════════════════════════════════════
# PROGRESS UPDATE — called from price_feed milestones
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
    pnl_str = f"+${upnl:.4f}" if upnl >= 0 else f"-${abs(upnl):.4f}"
    health  = state_manager.health_state
    h_emoji = (
        "✅" if health == "HEALTHY"     else
        "⚠️" if health == "WARNING"     else
        "🚨"
    )

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


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════
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
        f"*Why This Trade:*\n"
        f"{thesis or 'No thesis data'}\n\n"
        f"*Risk Factors:*\n"
        f"{risk or 'No risk data'}"
    )