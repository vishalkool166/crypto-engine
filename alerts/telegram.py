import httpx
import logging
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from fastapi import Request
from config import cfg
from database import SessionLocal, Trade, get_session
from trade.state import state_manager
from alerts.utils import now_ist, grade_accuracy_str, categorize_results

log = logging.getLogger(__name__)

BASE   = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"
DOMAIN = "https://small-salaried-study.ngrok-free.dev"

_sent_signals: deque = deque(maxlen=100)
_skip_reasons: dict  = {}
_SKIP_TTL             = 3600


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


def _active_trade_guard(msg: str = "⚠️ No active trade.") -> Trade | None:
    if state_manager.is_idle:
        return None
    return state_manager.current_trade


def _get_current_and_upnl(trade) -> tuple[float, float]:
    from trade.orders import get_current_price
    from trade.risk import risk_guard
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
    await _post("sendMessage", {
        "chat_id":    cfg.TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "Markdown"
    })


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
            r    = await client.post(f"{BASE}/setWebhook", json={"url": webhook_url}, timeout=10)
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
        f"Score: `{score}/100` · Earned: `{wconf.get('total_earned',0)}/{wconf.get('max_possible',0)}`\n"
    ]
    for f in factors:
        pct  = round(f["earned"] / f["max"] * 100) if f["max"] > 0 else 0
        icon = "✅" if f["pass"] else "❌"
        bar  = "█" * (pct // 10) + "░" * (10 - pct // 10)
        lines.append(f"{icon} *{f['label']}*\n`{bar}` {f['earned']}/{f['max']}\n_{f.get('detail', '')}_\n")

    await send("\n".join(lines))


async def _cb_show_risks(coin: str):
    from data.cache import cache
    cached = cache.get(f"signal_{coin}")
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
        await send(f"⚠️ Grade {grade} no longer meets minimum.")
        return
    if dir_ not in ["LONG", "SHORT"]:
        await send(f"⚠️ Signal direction invalid: {dir_}")
        return
    if not state_manager.is_idle:
        trade = state_manager.current_trade
        await send(f"⚠️ Already in trade: `{trade.coin}USDT {trade.direction}`\nClose current trade first.")
        return

    await send(f"✅ *Approved* — Opening `{coin}USDT {dir_}`...")
    signal["coin"] = coin
    result = await trade_manager.open_trade(signal=signal, signal_id=signal.get("db_id"))
    if not result["success"]:
        await send(f"❌ Trade failed: `{result['reason']}`")


async def _cb_skip_signal(coin: str):
    _skip_reasons[coin] = time.time()
    await send(f"⏭ *{coin} signal skipped*\n\nSignal expires in 1 hour.\nUse /scan to get fresh signals.")
    log.info(f"Signal skipped via Telegram: {coin}")


async def _cb_confirm_close():
    from trade.manager import trade_manager
    if state_manager.is_idle:
        await send("⚠️ No active trade to close.")
        return
    trade = state_manager.current_trade
    await send(f"⏳ Closing `{trade.coin}USDT {trade.direction}`...")
    result = await trade_manager.manual_close()
    await send("✅ Trade closed manually." if result["success"] else f"❌ Close failed: `{result['reason']}`")


async def _handle_command(text: str):
    t = text.lower().strip()

    if t.startswith("/coin"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if coin in cfg.COINS:
            await _cmd_coin(coin)
        else:
            await send(f"⚠️ Unknown coin: `{coin}`\nSupported: `{', '.join(cfg.COINS)}`")
        return

    if t.startswith("/backtest"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if coin in cfg.COINS:
            await _cmd_backtest(coin)
        else:
            await send(f"⚠️ Usage: `/backtest BTC`\nSupported: `{', '.join(cfg.TIER1)}`")
        return

    handlers = {
        "/status":  _cmd_status,
        "/pnl":     _cmd_pnl,
        "/close":   _cmd_close,
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
        "/pause":   _cmd_pause,
        "/resume":  _cmd_resume,
        "/mode":    _cmd_mode,
        "/brief":   _cmd_brief,
        "/factors": _cmd_factors,
        "/debrief": _cmd_debrief,
    }

    handler = handlers.get(t)
    if handler:
        await handler()
    else:
        await send("🤖 Unknown command.\n\nType /help for full command list.")


async def _cmd_status():
    if state_manager.is_idle:
        paused_note = (
            "\n⏸ Auto-execution is *PAUSED*\nUse /resume to re-enable."
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

    current, upnl = _get_current_and_upnl(trade)
    h_emoji = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(state_manager.health_state, "—")

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
        f"{'📈' if upnl >= 0 else '📉'} uPnL: `${upnl}`\n"
        f"Risk:    `${trade.risk_amt}`\n"
        f"{h_emoji} Health: `{state_manager.health_state}`\n"
    )


async def _cmd_thesis():
    trade = _active_trade_guard()
    if not trade:
        await send("⚠️ No active trade.\nUse /queue to see pending signals.")
        return
    await _show_active_thesis(trade.coin)


async def _cmd_health():
    if state_manager.is_idle:
        await send("⚠️ No active trade — no health data.")
        return

    health  = state_manager.health_data
    state   = state_manager.health_state
    trade   = state_manager.current_trade
    h_emoji = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(state, "—")

    lines = [f"{h_emoji} *Trade Health — {trade.coin if trade else '--'}*\n", f"Status: `{state}`\n"]

    for label, items, icon in [
        ("*Invalidated:*", health.get("failures", []), "✘"),
        ("\n*Warnings:*",  health.get("warnings", []), "⚠"),
    ]:
        if items:
            lines.append(label)
            lines.extend(f"{icon} {i}" for i in items)

    if health.get("checks") and state == "HEALTHY":
        lines.append("\n*Healthy:*")
        lines.extend(f"✔ {c}" for c in health["checks"])

    lines.append(
        "\n_Thesis invalidated. Use /close if you want to exit._" if state == "INVALIDATED" else
        "\n_Thesis weakening. Monitor position._"                 if state == "WARNING"     else
        "\n_Thesis intact. Hold position._"
    )

    await send("\n".join(lines))


async def _cmd_levels():
    trade = _active_trade_guard()
    if not trade:
        await send("⚠️ No active trade — no levels to show.")
        return

    from trade.price_feed import price_feed
    current, upnl = _get_current_and_upnl(trade)
    current       = price_feed.get_price(trade.coin) or current
    is_long       = trade.direction == "LONG"
    tp1_hit       = (
        abs(trade.sl_price - trade.entry_price) / trade.entry_price < 0.002
        if trade.sl_price and trade.entry_price else False
    )

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


async def _cmd_close():
    trade = _active_trade_guard()
    if not trade:
        await send("⚠️ No active trade to close.")
        return

    current, upnl = _get_current_and_upnl(trade)

    await send_with_keyboard(
        f"⚠️ *Close {trade.coin}USDT {trade.direction}?*\n\n"
        f"Entry:   `{trade.entry_price}`\n"
        f"Current: `{current}`\n"
        f"uPnL:    `{_pnl_str(upnl)}`\n"
        f"Health:  `{state_manager.health_state}`\n\n"
        f"This cancels all SL/TP orders.",
        keyboard=[[
            {"text": "✅ Yes, Close", "callback_data": "confirm_close"},
            {"text": "❌ Cancel",     "callback_data": "cancel_close"}
        ]]
    )


async def _cmd_btc():
    await _cmd_coin("BTC")


async def _cmd_coin(coin: str):
    from data.cache import cache
    cached = cache.get(f"signal_{coin}")
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
    ob      = d4h.get("order_blocks", {})

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

    if ob:
        base += f"OB:      `{ob.get('label', '--')}`\n"
        base += f"OB Score:`{ob.get('score', 0)}/10`\n"

    await send(base)


async def _cmd_regime():
    from data.cache import cache
    lines = ["📈 *Market Regime — Tier 1*\n"]
    for coin in cfg.TIER1:
        cached = cache.get(f"signal_{coin}")
        if not cached:
            lines.append(f"`{coin}` — no data")
            continue
        dir_   = cached.get("direction", "--")
        em     = "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁"
        lines.append(f"{em} `{coin}` — {cached.get('regime','--')} · Grade {cached.get('grade','F')}")
    await send("\n".join(lines))


async def _cmd_funding():
    from data.cache import cache
    lines = ["💸 *Funding Rates*\n"]
    for coin in cfg.COINS:
        cached = cache.get(f"signal_{coin}")
        if not cached:
            continue
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
        emoji = "🟢" if val >= 60 else "🔴" if val <= 30 else "🟡"
        await send(
            f"{emoji} *Fear & Greed Index*\n\n"
            f"Value: `{val}/100`\n"
            f"Label: `{label}`\n\n"
            f"_Above 75 = Extreme Greed — caution_\n"
            f"_Below 25 = Extreme Fear — opportunity_"
        )
    except Exception as e:
        await send(f"❌ Fear & Greed fetch failed: `{e}`")


async def _cmd_pnl():
    from trade.risk import risk_guard
    stats = risk_guard.get_daily_stats()

    with get_session() as db:
        all_trades = db.query(Trade).filter(Trade.outcome != "pending").all()
        total_pnl  = sum(t.pnl or 0 for t in all_trades)
        wins       = sum(1 for t in all_trades if t.outcome == "win")
        losses     = sum(1 for t in all_trades if t.outcome == "loss")
        total      = len(all_trades)
        wr         = round(wins / total * 100, 1) if total else 0

    await send(
        f"💰 *PnL Report*\n\n"
        f"*Today*\n"
        f"Trades:  `{stats['trades_taken']}`\n"
        f"{'📈' if stats['total_pnl'] >= 0 else '📉'} PnL: `${stats['total_pnl']}`\n"
        f"Loss:    `${stats['total_loss']}`\n"
        f"Cap Hit: `{'YES 🚫' if stats['cap_hit'] else 'NO ✅'}`\n\n"
        f"*All Time*\n"
        f"Total:   `{total}` trades\n"
        f"Wins:    `{wins}` · Losses: `{losses}`\n"
        f"WR:      `{wr}%`\n"
        f"PnL:     `${round(total_pnl, 2)}`\n"
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
    from alerts.scanner import get_db_stats
    stats = get_db_stats()
    if not stats:
        await send("📊 No stats yet — no closed trades.")
        return

    bg = stats.get("by_grade", {})
    ap = bg.get("A+", {})
    a  = bg.get("A", {})

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

    def grade_block(label, data):
        return (
            f"*Grade {label}*\n"
            f"Trades:   `{data.get('total', 0)}`\n"
            f"Wins:     `{data.get('wins', 0)}`\n"
            f"Losses:   `{data.get('losses', 0)}`\n"
            f"Win Rate: `{data.get('win_rate', 0)}%`\n"
            f"PnL:      `${data.get('total_pnl', 0)}`\n"
        )

    await send(
        f"🏆 *Grade Accuracy*\n\n"
        f"{grade_block('A+', ap)}\n"
        f"{grade_block('A', a)}\n"
        f"_Minimum 50 trades for reliable data_"
    )


async def _cmd_risk():
    from trade.risk import risk_guard
    stats     = risk_guard.get_daily_stats()
    daily_cap = cfg.CAPITAL * cfg.DAILY_LOSS_CAP_PCT
    loss_pct  = abs(stats["total_loss"]) / daily_cap * 100 if daily_cap > 0 else 0

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
        f"Cap status:    `{'🚫 HIT' if stats['cap_hit'] else '✅ ACTIVE'}`\n"
    )


async def _cmd_session():
    from engines.signal import get_session
    session   = get_session()
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
    session = get_session()
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


async def _cmd_pause():
    if state_manager.is_paused:
        await send("⏸ Bot is already paused.\nUse /resume to re-enable auto-execution.")
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
        await send("▶️ Bot is already running.\nAuto-execution is active.")
        return
    state_manager.resume()
    await send(
        "▶️ *Auto-Execution Resumed*\n\n"
        "Next A+ signal will execute automatically.\n"
        "Scanning every 15 minutes."
    )


async def _cmd_mode():
    paused_str = "⏸ PAUSED" if state_manager.is_paused else "▶️ AUTO"
    trade_str  = "IN TRADE" if not state_manager.is_idle else "IDLE"
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


async def _cmd_factors():
    from backtest.factor_analysis import run_factor_analysis
    await send("⏳ Running factor analysis...")
    result = run_factor_analysis()

    if "error" in result:
        await send(
            f"⚠️ *Factor Analysis*\n\n"
            f"{result['error']}\n\n"
            f"Need `{result.get('min_required', 200)}` closed trades minimum."
        )
        return

    total    = result.get("total", 0)
    wr       = result.get("overall_wr", 0)
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
            lines.append(f"✅ `{f['factor']}` — edge: `+{f['edge']}%` ({f['present_total']} trades)")

    if weak:
        lines.append("\n*Weak/No Edge:*")
        for f in weak[:3]:
            lines.append(f"⚠️ `{f['factor']}` — edge: `{f['edge']}%`")

    if not result.get("reliable"):
        lines.append(f"\n_Need {200 - total} more trades for reliable conclusions_")

    await send("\n".join(lines))


async def _cmd_backtest(coin: str):
    from backtest.engine import run_backtest
    await send(f"⏳ Running backtest for `{coin}`...")
    try:
        result = run_backtest(coin=coin, capital=cfg.CAPITAL, leverage=cfg.LEVERAGE)
        if "error" in result:
            await send(f"❌ Backtest failed: `{result['error']}`")
            return

        bg = result.get("by_grade", {})
        await send(
            f"📊 *Backtest — {coin}USDT*\n\n"
            f"Period: `{result.get('period_start')} → {result.get('period_end')}`\n\n"
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
            f"A+: `{bg.get('A+',{}).get('win_rate',0)}% WR` · `{bg.get('A+',{}).get('trades',0)} trades`\n"
            f"A:  `{bg.get('A',{}).get('win_rate',0)}% WR` · `{bg.get('A',{}).get('trades',0)} trades`\n"
        )
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
        tradeable = [r for r in results if r.get("grade") in ["A+", "A"] and r.get("direction") in ["LONG", "SHORT"]]
        aplus     = [r for r in tradeable if r.get("grade") == "A+"]
        a         = [r for r in tradeable if r.get("grade") == "A"]

        summary = f"✅ *Scan Complete*\n\nCoins scanned: `{len(results)}`\nA+ signals:    `{len(aplus)}`\nA signals:     `{len(a)}`\n\n"
        if aplus:         summary += f"🏆 {len(aplus)} A+ found!\n"
        if a:             summary += f"✅ {len(a)} A found!\n"
        if not tradeable: summary += "😴 No tradeable signals found.\n"
        summary += "\nNext auto scan at next :00/:15/:30/:45 UTC"
        await send(summary)
    except Exception as e:
        await send(f"❌ *Scan Failed*\n\n`{str(e)}`")


async def _cmd_queue():
    from data.cache import cache
    best       = None
    best_score = 0

    for coin in cfg.COINS:
        if _is_skipped(coin):
            continue
        cached = cache.get(f"signal_{coin}")
        if cached:
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

    paused_note = (
        "\n⏸ _Auto-execution paused — tap Approve to enter_\n"
        if state_manager.is_paused else ""
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
        f"Lev:     `{cfg.LEVERAGE}x`\n"
        f"{chr(10) + '*Why This Trade?*' + chr(10) + thesis + chr(10) if thesis else ''}"
        f"{paused_note}",
        keyboard=[
            [
                {"text": "📊 Show Factors", "callback_data": f"factors:{coin}"},
                {"text": "⚠️ Show Risks",   "callback_data": f"risks:{coin}"}
            ],
            [
                {"text": "✅ Approve", "callback_data": f"approve:{coin}"},
                {"text": "❌ Skip",    "callback_data": f"skip:{coin}"}
            ]
        ]
    )


async def send_scan_summary(results: list):
    cats      = categorize_results(results)
    tradeable = cats["tradeable"]
    watching  = cats["watching"]
    building  = cats["building"]

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

        if not state_manager.is_idle:
            trade = state_manager.current_trade
            lines.append(f"\n⚡ Active trade: {trade.coin} {trade.direction}")
        else:
            lines.append(
                f"\n💤 Bot {'PAUSED' if state_manager.is_paused else 'idle'} — "
                f"{'tap Approve to enter' if state_manager.is_paused else 'will execute best signal'}"
            )

        lines.append("\nNext scan: next :00/:15/:30/:45 UTC")
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
        lines.append("No setups building across all coins.")

    lines.append("\nNext scan: next :00/:15/:30/:45 UTC")
    await send("\n".join(lines))


async def send_progress_update(trade, current_price: float, milestone_pct: int):
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
    h_emoji = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(state_manager.health_state, "—")

    await send(
        f"⚡ *{trade.coin}USDT — {milestone_pct}% to TP1*\n\n"
        f"Price:   `${current_price:,.4f}`\n"
        f"Entry:   `{entry}`\n"
        f"TP1:     `{tp1}` — `${dist_tp1:,.4f}` away\n"
        f"SL:      `{sl}`\n\n"
        f"uPnL:    `{_pnl_str(upnl)}`\n"
        f"{h_emoji} Health: `{state_manager.health_state}`\n\n"
        f"Type /status for full details"
    )


async def _show_active_thesis(coin: str):
    from data.cache import cache
    cached = cache.get(f"signal_{coin}")
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