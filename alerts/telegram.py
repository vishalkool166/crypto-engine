import httpx
import logging
import time
import asyncio
from collections import deque
from datetime import datetime, timezone, timedelta, date
from fastapi import Request
from config import cfg
from database import SessionLocal, get_session
from alerts.utils import now_ist, categorize_results
from data.cache import cache
from engines.signal import get_session as get_trading_session

log = logging.getLogger(__name__)

BASE = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"
IST  = timezone(timedelta(hours=5, minutes=30))

_sent_signals: deque = deque(maxlen=100)
_skip_reasons: dict  = {}
_SKIP_TTL             = 3600


def _now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def _now_ist_full() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %I:%M %p IST")


def _is_skipped(coin: str) -> bool:
    ts = _skip_reasons.get(coin)
    if ts is None:
        return False
    if time.time() - ts > _SKIP_TTL:
        del _skip_reasons[coin]
        return False
    return True


def _get_cached(coin: str) -> dict | None:
    return cache.get_raw(f"signal_{coin}")


def _all_cached_signals() -> list:
    return [c for coin in cfg.COINS if (c := cache.get_raw(f"signal_{coin}"))]


def _get_stats() -> dict:
    from alerts.scanner import get_db_stats
    return get_db_stats()


def _grade_block(label: str, data: dict) -> str:
    return (
        f"*Grade {label}*\n"
        f"Trades:   `{data.get('total', 0)}`\n"
        f"Wins:     `{data.get('wins', 0)}`\n"
        f"Losses:   `{data.get('losses', 0)}`\n"
        f"Win Rate: `{data.get('win_rate', 0)}%`\n"
        f"PnL:      `${data.get('total_pnl', 0)}`\n"
    )


async def _post(endpoint: str, payload: dict) -> None:
    if not cfg.TELEGRAM_TOKEN or not cfg.TELEGRAM_CHAT_ID:
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/{endpoint}", json=payload, timeout=10)
            if r.status_code != 200:
                log.error("Telegram %s failed: %s", endpoint, r.text)
    except Exception as e:
        log.error("Telegram error: %s", e)


async def send(message: str) -> None:
    for chunk in _split_message(message):
        await _post("sendMessage", {
            "chat_id":    cfg.TELEGRAM_CHAT_ID,
            "text":       chunk,
            "parse_mode": "Markdown",
        })


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


async def register_webhook() -> None:
    try:
        async with httpx.AsyncClient() as client:
            r    = await client.post(f"{BASE}/setWebhook", json={"url": f"{cfg.DOMAIN}/webhook/telegram", "secret_token": cfg.WEBHOOK_SECRET}, timeout=10)
            data = r.json()
            if data.get("ok"):
                log.info("Webhook registered: %s/webhook/telegram", cfg.DOMAIN)
            else:
                log.error("Webhook failed: %s", data)
    except Exception as e:
        log.error("Webhook register error: %s", e)


async def register_commands() -> None:
    commands = [
        {"command": "status",   "description": "Bot status overview"},
        {"command": "queue",    "description": "Top 3 signals right now"},
        {"command": "scan",     "description": "Trigger manual scan"},
        {"command": "health",   "description": "All open trades health"},
        {"command": "trades",   "description": "Open trades with live PnL"},
        {"command": "position", "description": "Deep dive on trade — /position XLM"},
        {"command": "balance",  "description": "Account balance"},
        {"command": "profit",   "description": "Profit summary"},
        {"command": "btc",      "description": "BTC analysis"},
        {"command": "coin",     "description": "Any coin analysis — /coin ETH"},
        {"command": "funding",  "description": "Funding rates"},
        {"command": "fear",     "description": "Fear and greed index"},
        {"command": "pending",  "description": "Posts waiting"},
        {"command": "brief",    "description": "Generate market brief post"},
        {"command": "discard",  "description": "Delete a post — /discard 5"},
        {"command": "pnl",      "description": "All time PnL"},
        {"command": "daily",    "description": "Today summary"},
        {"command": "stats",    "description": "Full all time stats"},
        {"command": "grade",    "description": "Grade accuracy"},
        {"command": "history",  "description": "Last 5 signals"},
        {"command": "backtest", "description": "Backtest a coin — /backtest BTC"},
        {"command": "backfill", "description": "Backfill historical candle data"},
        {"command": "ml",       "description": "ML model status"},
        {"command": "mode",     "description": "Current bot config"},
        {"command": "help",     "description": "Full command list"},
    ]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/setMyCommands", json={"commands": commands}, timeout=10)
            if r.json().get("ok"):
                log.info("Telegram commands registered")
    except Exception as e:
        log.error("Commands register error: %s", e)


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
    t = text.lower().strip()

    if t.startswith("/coin"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if not coin:
            await send("⚠️ Usage: `/coin BTC`")
            return
        await _cmd_coin(coin) if coin in cfg.COINS else await send(
            f"⚠️ `{coin}` not in universe.\nYour coins: `{', '.join(cfg.COINS)}`"
        )
        return

    if t.startswith("/position"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        await (send("⚠️ Usage: `/position XLM`") if not coin else _cmd_position(coin))
        return

    if t.startswith("/backtest"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        await (_cmd_backtest(coin) if coin in cfg.COINS else send("⚠️ Usage: `/backtest BTC`"))
        return

    if t.startswith("/backfill"):
        parts = t.split()
        await _cmd_backfill(parts[1].upper() if len(parts) > 1 else None)
        return

    if t.startswith("/discard"):
        parts = t.split()
        if len(parts) > 1:
            try:
                await _cmd_discard(int(parts[1].replace("#", "")))
            except ValueError:
                await send("⚠️ Usage: `/discard 5`")
        else:
            await send("⚠️ Usage: `/discard 5`")
        return

    if t.startswith("#") and len(t) > 1:
        try:
            await _cmd_show_post(int(t.replace("#", "").strip()))
        except ValueError:
            pass
        return

    handlers = {
        "/status":  _cmd_status,
        "/pnl":     _cmd_pnl,
        "/queue":   _cmd_queue,
        "/daily":   _cmd_daily,
        "/scan":    _cmd_scan,
        "/help":    _cmd_help,
        "/btc":     _cmd_btc,
        "/funding": _cmd_funding,
        "/fear":    _cmd_fear,
        "/history": _cmd_history,
        "/stats":   _cmd_stats,
        "/grade":   _cmd_grade,
        "/mode":    _cmd_mode,
        "/brief":   _cmd_brief,
        "/ml":      _cmd_ml,
        "/trades":  _cmd_trades,
        "/balance": _cmd_balance,
        "/profit":  _cmd_profit,
        "/health":  _cmd_health,
        "/pending": _cmd_pending,
    }

    if t.startswith("/"):
        handler = handlers.get(t)
        await (handler() if handler else send("🤖 Unknown command. Type /help for list."))
        return

    try:
        from chatbot import chat
        await send(await chat(text))
    except Exception as e:
        log.error("Chatbot error: %s", e)
        await send("AI unavailable. Try /help for commands.")


async def _cmd_backfill(coin: str | None = None) -> None:
    await send(f"⏳ *Backfill started for {coin or 'all coins'}...*")
    try:
        from backfill import run_backfill
        asyncio.create_task(run_backfill(coins=[coin] if coin else None))
    except Exception as e:
        await send(f"❌ Backfill failed: `{e}`")


async def _cmd_status() -> None:
    from alerts.scanner import get_db_stats
    from scheduler import get_next_scan_time
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_ws_status

    stats     = get_db_stats()
    ws        = get_ws_status()
    cached    = _all_cached_signals()
    tradeable = [r for r in cached if r.get("grade") in cfg.MIN_GRADE_TO_TRADE and r.get("direction") in ["LONG", "SHORT"]]

    try:
        open_trades = await get_open_positions_enriched()
    except Exception:
        open_trades = []

    mode     = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"
    ws_emoji = "✅" if ws["mark_price_connected"] else "❌"

    await send(
        f"📊 *Bot Status*\n_{_now_ist_full()}_\n\n"
        f"State:       `RUNNING`\n"
        f"Mode:        `{mode}`\n"
        f"Coins:       `{len(cfg.COINS)} scanned`\n"
        f"Grades:      `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Open trades: `{len(open_trades)}`\n"
        f"Signals:     `{len(cached)}` cached · `{len(tradeable)}` tradeable\n"
        f"WS Stream:   {ws_emoji} `{ws['prices_cached']} prices`\n\n"
        f"All-time: `{stats.get('total', 0)}` signals · "
        f"`{stats.get('closed', 0)}` closed · "
        f"`{stats.get('win_rate', 0)}%` WR\n\n"
        f"Next scan: `{get_next_scan_time()}`"
    )


async def _cmd_trades() -> None:
    try:
        from trade.monitor import get_open_positions_enriched
        from trade.ws import get_mark_price
        trades = await get_open_positions_enriched()
        if not trades:
            await send(f"📊 *Open Trades*\n_{_now_ist()}_\n\nNo open trades.")
            return
        lines = [f"📊 *Open Trades — {len(trades)}*\n_{_now_ist()}_\n"]
        for t in trades:
            coin      = t.get("coin", "--")
            direction = t.get("direction", "--")
            entry     = float(t.get("entry_price") or 0)
            leverage  = int(t.get("leverage") or 1)
            margin    = float(t.get("margin_used") or 0)
            is_short  = direction == "SHORT"
            live      = get_mark_price(coin) or float(t.get("current_price") or entry)
            if entry > 0 and live > 0:
                pnl_abs = ((entry - live) if is_short else (live - entry)) / entry * margin * leverage
                pnl_abs = round(pnl_abs - margin * leverage * 0.001, 4)
                pnl_pct = pnl_abs / margin * 100
            else:
                pnl_abs = pnl_pct = 0.0
            pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
            pnl_emoji = "🟢" if pnl_abs >= 0 else "🔴"
            side      = "📈 LONG" if direction == "LONG" else "📉 SHORT"
            health    = t.get("health", {})
            h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
            h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")
            sl        = t.get("sl_price")
            tp        = t.get("tp1_price")
            sl_dist   = abs(live - sl) / entry * 100 if sl and entry else 0
            tp_dist   = abs(tp - live) / entry * 100 if tp and entry else 0
            lines.append(
                f"{side} `{coin}` — Grade `{t.get('grade', '--')}`\n"
                f"Entry: `{entry:.6f}` · Live: `{live:.6f}`\n"
                f"PnL: {pnl_emoji} `{pnl_str}` ({pnl_pct:.2f}%)\n"
                f"SL: `{sl:.6f}` ({sl_dist:.2f}% away)\n"
                f"TP: `{tp:.6f}` ({tp_dist:.2f}% away)\n"
                f"Lev: `{leverage}x` · Margin: `${margin:.2f}`\n"
                f"Health: {h_emoji} `{h_state}` · Open: `{t.get('duration', '--')}`\n"
            )
        await send("\n".join(lines))
    except Exception as e:
        log.error("_cmd_trades error: %s", e)
        await send("❌ Could not fetch trades.")


async def _cmd_position(coin: str) -> None:
    try:
        from trade.monitor import get_open_positions_enriched
        from trade.ws import get_mark_price
        trades = await get_open_positions_enriched()
        trade  = next((t for t in trades if t.get("coin") == coin), None)
        if not trade:
            await send(f"⚠️ No open trade for `{coin}`.")
            return
        entry     = float(trade.get("entry_price") or 0)
        direction = trade.get("direction", "--")
        leverage  = int(trade.get("leverage") or 1)
        margin    = float(trade.get("margin_used") or 0)
        is_short  = direction == "SHORT"
        sl        = trade.get("sl_price")
        tp        = trade.get("tp1_price")
        live      = get_mark_price(coin) or float(trade.get("current_price") or entry)
        if entry > 0 and live > 0:
            pnl_abs = ((entry - live) if is_short else (live - entry)) / entry * margin * leverage
            pnl_abs = round(pnl_abs - margin * leverage * 0.001, 4)
            pnl_pct = pnl_abs / margin * 100
        else:
            pnl_abs = pnl_pct = 0.0
        pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
        pnl_emoji = "🟢" if pnl_abs >= 0 else "🔴"
        side      = "📈 LONG" if direction == "LONG" else "📉 SHORT"
        sl_dist   = abs(live - sl) / entry * 100 if sl and entry else 0
        tp_dist   = abs(tp - live) / entry * 100 if tp and entry else 0
        sl_pct    = abs(entry - sl) / entry * 100 if sl and entry else 0
        health    = trade.get("health", {})
        h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
        h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")
        failures  = health.get("failures", []) if health else []
        warnings  = health.get("warnings", []) if health else []
        thesis    = cache.get_raw(f"signal_{coin}") or {}
        thesis    = thesis.get("explanation", {}).get("thesis", "")
        msg = (
            f"{side} *{coin}USDT — Position Detail*\n_{_now_ist()}_\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Grade:   `{trade.get('grade', '--')}` · Score `{trade.get('score_at_entry', 0)}`\n"
            f"Regime:  `{trade.get('regime_at_entry', '--')}`\n"
            f"Session: `{trade.get('session_at_entry', '--')}`\n\n"
            f"Entry:   `${entry:.6f}`\n"
            f"Live:    `${live:.6f}`\n"
            f"PnL:     {pnl_emoji} `{pnl_str}` ({pnl_pct:.2f}%)\n\n"
            f"SL:      `${sl:.6f}` ({sl_pct:.2f}% from entry · {sl_dist:.2f}% away)\n"
            f"TP:      `${tp:.6f}` ({tp_dist:.2f}% away)\n\n"
            f"Lev:     `{leverage}x` · Margin `${margin:.2f}` · Pos `${margin*leverage:.2f}`\n"
            f"Open:    `{trade.get('duration', '--')}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Health: {h_emoji} `{h_state}`\n"
        )
        if failures:
            msg += "\n*Failures:*\n" + "\n".join(f"✘ _{f}_" for f in failures[:2])
        elif warnings:
            msg += "\n*Warnings:*\n" + "\n".join(f"⚠ _{w}_" for w in warnings[:2])
        if thesis:
            msg += f"\n\n*Thesis:*\n_{thesis[:200]}_"
        msg += "\n\n_Use dashboard Force Sell to close._"
        await send(msg)
    except Exception as e:
        log.error("_cmd_position %s: %s", coin, e)
        await send(f"❌ Could not fetch position for `{coin}`.")


async def _cmd_balance() -> None:
    try:
        from trade.exchange import get_balance
        from trade.ws import get_ws_status
        b  = await get_balance()
        ws = get_ws_status()
        await send(
            f"💰 *Balance — {'DEMO' if cfg.PAPER_TRADING else 'LIVE'}*\n_{_now_ist()}_\n\n"
            f"Total:      `${b['total']:.2f} USDT`\n"
            f"Free:       `${b['free']:.2f} USDT`\n"
            f"Used:       `${b['used']:.2f} USDT`\n"
            f"Unrealized: `${b.get('unrealized', 0):.4f} USDT`\n\n"
            f"WS: `{'✅ Connected' if ws['user_data_connected'] else '❌ Disconnected'}`"
        )
    except Exception as e:
        log.error("_cmd_balance error: %s", e)
        await send("❌ Could not fetch balance.")


async def _cmd_profit() -> None:
    try:
        from trade.monitor import get_profit_summary
        d      = get_profit_summary()
        profit = float(d.get("profit_all_coin", 0))
        await send(
            f"💰 *Profit Summary*\n_{_now_ist()}_\n\n"
            f"Total PnL:    `{'+' if profit >= 0 else ''}${profit:.4f}`\n"
            f"Win Rate:     `{float(d.get('winrate', 0))*100:.1f}%`\n"
            f"Total Trades: `{d.get('trade_count', 0)}`\n"
            f"Wins:         `{d.get('wins', 0)}`\n"
            f"Losses:       `{d.get('losses', 0)}`\n"
            f"Commission:   `${d.get('total_commission', 0):.4f}`\n"
            f"Funding:      `${d.get('total_funding_fees', 0):.4f}`\n\n"
            f"Best:  `{d.get('best_pair', '--')}`\n"
            f"Worst: `{d.get('worst_pair', '--')}`"
        )
    except Exception as e:
        log.error("_cmd_profit error: %s", e)
        await send("❌ Could not fetch profit.")


async def _cmd_health() -> None:
    try:
        from trade.monitor import get_open_positions_enriched
        from trade.ws import get_mark_price
        trades = await get_open_positions_enriched()
        if not trades:
            await send(f"💚 *Trade Health*\n_{_now_ist()}_\n\nNo open trades.")
            return
        lines = [f"💚 *Trade Health — {len(trades)} Open*\n_{_now_ist()}_\n"]
        for t in trades:
            coin      = t.get("coin", "--")
            direction = t.get("direction", "--")
            entry     = float(t.get("entry_price") or 0)
            leverage  = int(t.get("leverage") or 1)
            margin    = float(t.get("margin_used") or 0)
            is_short  = direction == "SHORT"
            live      = get_mark_price(coin) or float(t.get("current_price") or entry)
            pnl_abs   = round(((entry - live) if is_short else (live - entry)) / entry * margin * leverage - margin * leverage * 0.001, 4) if entry > 0 else 0.0
            pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
            side      = "📈" if direction == "LONG" else "📉"
            health    = t.get("health", {})
            h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
            h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")
            failures  = health.get("failures", []) if health else []
            warnings  = health.get("warnings", []) if health else []
            lines.append(f"{side} `{coin}` — {h_emoji} `{h_state}` · `{pnl_str}`")
            if failures:
                lines.append(f"  ✘ _{failures[0]}_")
            elif warnings:
                lines.append(f"  ⚠ _{warnings[0]}_")
            lines.append("")
        await send("\n".join(lines))
    except Exception as e:
        log.error("_cmd_health error: %s", e)
        await send("❌ Could not fetch health.")


async def _cmd_btc() -> None:
    await _cmd_coin("BTC")


async def _cmd_coin(coin: str) -> None:
    cached = _get_cached(coin)
    if not cached:
        await send(f"No data for `{coin}`. Run /scan first.")
        return
    from trade.ws import get_mark_price
    market    = cached.get("market", {})
    grade     = cached.get("grade", "F")
    dir_      = cached.get("direction", "--")
    score     = cached.get("score", 0)
    sweep     = cached.get("sweep", {})
    disp      = cached.get("displacement", {})
    retest    = cached.get("retest", {})
    d1d       = cached.get("d1d", {})
    expl      = cached.get("explanation", {})
    ml_prob   = cached.get("ml_probability")
    actual_rr = cached.get("actual_rr", 0)
    tp_mult   = cached.get("tp_mult", 1.5)
    live      = get_mark_price(coin) or market.get("price", 0)
    change    = market.get("change24", 0)
    funding   = market.get("funding", 0) * 100
    sig       = cached.get("signal", {})
    em        = "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁"
    rsi       = d1d.get("rsi")
    adx       = d1d.get("adx")
    base = (
        f"📊 *{coin}USDT Analysis*\n_{_now_ist()}_\n\n"
        f"Price:   `${live:,.4f}` ({'+' if change >= 0 else ''}{change:.2f}%)\n"
        f"Grade:   `{grade}` · Score `{score}/100`\n"
        f"Signal:  {em} `{dir_}`\n"
        f"Conf:    `{expl.get('confidence_label', '--')}`\n"
    )
    if ml_prob is not None:
        base += f"ML Prob: {'✅' if ml_prob >= 0.65 else '❌'} `{ml_prob*100:.1f}%`\n"
    base += f"\nRegime:  `{cached.get('regime', '--')}`\nSession: `{cached.get('session', '--')}`\n\n"
    if rsi and adx:
        base += f"RSI: `{rsi:.1f}` · ADX: `{adx:.1f}` · Funding: `{funding:.4f}%`\n\n"
    if sig.get("entry") and sig.get("sl") and sig.get("tp1"):
        base += (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Entry: `{sig['entry']:.4f}` · SL: `{sig['sl']:.4f}` · TP: `{sig['tp1']:.4f}` ({tp_mult}x)\n"
            f"R:R:   `1:{actual_rr}`\n\n"
        )
    base += (
        f"Sweep:  `{'✅' if sweep.get('confirmed') else '❌'} {sweep.get('score',0)}/12`\n"
        f"Disp:   `{'✅' if disp.get('confirmed') else '❌'} {disp.get('score',0)}/11`\n"
        f"Retest: `{'✅' if retest.get('confirmed') else '❌'} {retest.get('score',0)}/12`\n"
    )
    await send(base)


async def _cmd_funding() -> None:
    lines = [f"💸 *Funding Rates*\n_{_now_ist()}_\n"]
    for c in _all_cached_signals():
        coin    = c.get("coin", "")
        funding = c.get("market", {}).get("funding", 0) * 100
        flag    = "🚨" if abs(funding) > 0.08 else "⚠️" if abs(funding) > 0.05 else "✅"
        lines.append(f"{flag} `{coin}` — `{funding:.4f}%`")
    if len(lines) == 1:
        lines.append("No data — run /scan first")
    await send("\n".join(lines))


async def _cmd_fear() -> None:
    from data.fetcher import get_fear_greed
    try:
        fg    = await get_fear_greed()
        val   = fg.get("value", 50)
        emoji = "🟢" if val >= 60 else "🔴" if val <= 30 else "🟡"
        await send(
            f"{emoji} *Fear & Greed Index*\n_{_now_ist()}_\n\n"
            f"Value: `{val}/100`\nLabel: `{fg.get('label', 'Neutral')}`\n"
            f"{'⚠️ _Stale data_' if fg.get('stale') else ''}"
        )
    except Exception as e:
        await send(f"❌ Fear & Greed failed: `{e}`")


async def _cmd_pnl() -> None:
    stats = _get_stats()
    await send(
        f"💰 *PnL Report*\n\n"
        f"Total:   `{stats.get('closed', 0) + stats.get('pending', 0)}` signals\n"
        f"Wins:    `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"WR:      `{stats.get('win_rate', 0)}%`\n"
        f"PnL:     `${stats.get('total_pnl', 0)}`\n"
    )


async def _cmd_daily() -> None:
    stats = _get_stats()
    today_pnl = today_trades = 0
    try:
        with SessionLocal() as db:
            from database import Signal as SignalModel
            sigs         = db.query(SignalModel).filter(SignalModel.timestamp >= date.today().isoformat(), SignalModel.outcome.in_(["win", "loss"])).all()
            today_pnl    = sum(float(s.pnl or 0) for s in sigs)
            today_trades = len(sigs)
    except Exception:
        pass
    pnl_str = f"+${today_pnl:.4f}" if today_pnl >= 0 else f"-${abs(today_pnl):.4f}"
    await send(
        f"📅 *Daily Summary*\n_{_now_ist_full()}_\n\n"
        f"Today: `{today_trades}` trades · `{pnl_str}`\n\n"
        f"All-time: `{stats.get('total', 0)}` signals · `{stats.get('closed', 0)}` closed\n"
        f"Wins: `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"WR: `{stats.get('win_rate', 0)}%` · PnL: `${stats.get('total_pnl', 0)}`\n"
    )


async def _cmd_history() -> None:
    from database import Signal as SignalModel
    with get_session() as db:
        signals = db.query(SignalModel).filter(SignalModel.outcome.in_(["win", "loss"])).order_by(SignalModel.timestamp.desc()).limit(5).all()
    if not signals:
        await send("📜 No closed signals yet.")
        return
    lines = [f"📜 *Last 5 Signals*\n_{_now_ist()}_\n"]
    for s in signals:
        pnl_str = f"+${s.pnl:.4f}" if (s.pnl or 0) >= 0 else f"-${abs(s.pnl or 0):.4f}"
        ts_ist  = s.timestamp.astimezone(IST).strftime("%d %b %I:%M %p") if s.timestamp else "--"
        lines.append(
            f"{'✅' if s.outcome == 'win' else '❌'} "
            f"{'📈' if s.direction == 'LONG' else '📉'} "
            f"`{s.coin}` {s.direction} Grade `{s.grade}` — `{pnl_str}`\n_{ts_ist} IST_\n"
        )
    await send("\n".join(lines))


async def _cmd_stats() -> None:
    stats = _get_stats()
    if not stats:
        await send("📊 No stats yet.")
        return
    bg = stats.get("by_grade", {})
    await send(
        f"📊 *All Time Stats*\n_{_now_ist()}_\n\n"
        f"Total: `{stats.get('total', 0)}` · Closed: `{stats.get('closed', 0)}`\n"
        f"Wins: `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"WR: `{stats.get('win_rate', 0)}%` · PnL: `${stats.get('total_pnl', 0)}`\n\n"
        f"{_grade_block('A+', bg.get('A+', {}))}\n"
        f"{_grade_block('A',  bg.get('A',  {}))}\n"
        f"{_grade_block('B',  bg.get('B',  {}))}"
    )


async def _cmd_grade() -> None:
    bg = _get_stats().get("by_grade", {})
    await send(
        f"🏆 *Grade Accuracy*\n\n"
        f"{_grade_block('A+', bg.get('A+', {}))}\n"
        f"{_grade_block('A',  bg.get('A',  {}))}\n"
        f"{_grade_block('B',  bg.get('B',  {}))}\n"
        f"_Minimum 50 trades for reliable data_"
    )


async def _cmd_mode() -> None:
    from trade.ws import get_ws_status
    ws = get_ws_status()
    await send(
        f"⚙️ *Bot Configuration*\n\n"
        f"Mode:        `{'🔴 LIVE' if not cfg.PAPER_TRADING else '🔵 PAPER'}`\n"
        f"Coins:       `{len(cfg.COINS)} coins`\n"
        f"Grades:      `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Scan:        `every :00/:15/:30/:45 UTC`\n"
        f"ML:          `{'✅ Active' if cfg.ML_ENABLED else '⏳ Collecting data'}`\n"
        f"Content:     `{'✅ Enabled' if cfg.CONTENT_ENABLED else '❌ Disabled'}`\n"
        f"WS Prices:   `{'✅ Live' if ws['mark_price_connected'] else '❌ Down'}`\n"
        f"WS UserData: `{'✅ Live' if ws['user_data_connected'] else '❌ Down'}`\n"
    )


async def _cmd_brief() -> None:
    await send("⏳ Generating market brief...")
    try:
        from data.fetcher import get_fear_greed
        fg      = {"value": 50, "label": "Neutral"}
        try:
            fg = await get_fear_greed()
        except Exception:
            pass

        cached = _all_cached_signals()
        cached.sort(key=lambda x: x.get("score", 0), reverse=True)

        btc_cached = cache.get_raw("signal_BTC")
        btc_change = btc_cached.get("market", {}).get("change24", 0) if btc_cached else 0.0
        regimes    = [r.get("regime", "") for r in cached if r.get("regime")]
        sessions   = [r.get("session", "") for r in cached if r.get("session")]
        hour       = datetime.now(timezone.utc).hour

        context = {
            "regime":     max(set(regimes), key=regimes.count) if regimes else "Unknown",
            "session":    sessions[0] if sessions else "Unknown",
            "fg_val":     fg.get("value", 50),
            "fg_label":   fg.get("label", "Neutral"),
            "btc_change": btc_change,
            "top_coins":  [{"coin": r.get("coin"), "grade": r.get("grade"), "score": r.get("score", 0)} for r in cached[:3]],
            "time_label": "Morning" if hour < 12 else "Evening" if hour >= 17 else "Midday",
        }

        from content.groq_writer import generate_brief_post
        draft = await generate_brief_post(context)
        if not draft:
            await send("❌ Brief generation failed.")
            return
        from content.approval_flow import send_brief_for_approval
        await send_brief_for_approval(draft)

    except Exception as e:
        log.error("Brief command error: %s", e)
        await send(f"❌ Brief failed: `{e}`")


async def _cmd_ml() -> None:
    from ml.eligibility import get_ml_status
    s            = get_ml_status()
    closed       = s.get("closed_trades", 0)
    required     = s.get("required", 100)
    pct          = min(100, int(closed / required * 100))
    bar          = "█" * (pct // 10) + "░" * (10 - pct // 10)
    top_features = s.get("top_features", [])
    top_str      = (
        "\n*Top Features:*\n" + "\n".join(f"  `{f['feature']}` — `{f['importance']}`" for f in top_features[:3])
        if top_features else ""
    )
    await send(
        f"🤖 *ML Status*\n\n"
        f"Status: `{'✅ ACTIVE' if s.get('ml_enabled') else '⏳ Collecting data'}`\n\n"
        f"Progress: `{closed}/{required}` trades\n"
        f"`{bar}` {pct}%\n\n"
        f"{s.get('message', '')}\n"
        f"{top_str}\n\n"
        f"Grades: `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Auto-trains at: `{required}` · Retrains every: `50 new trades`"
    )


async def _cmd_pending() -> None:
    from content.approval_flow import get_pending_posts
    posts = await get_pending_posts()
    if not posts:
        await send("📋 *Pending Posts*\n\nNo posts waiting.\n\nUse /brief to generate a market post.")
        return
    lines = [f"📋 *Pending Posts — {len(posts)}*\n", "_Reply `#N` to see full text_\n"]
    for p in posts:
        pt       = p.get("post_type", "signal")
        icon     = "📊" if pt == "signal" else "💬"
        preview  = p.get("post", "")[:80] + ("..." if len(p.get("post", "")) > 80 else "")
        coin_str = (
            f" — `{p.get('coin', 'MARKET')}USDT {p.get('direction', '--')}` Grade `{p.get('grade', '--')}`"
            if pt == "signal" else " — Market Commentary"
        )
        lines.append(
            f"{icon} *#{p['post_id']}*{coin_str}\n"
            f"_{preview}_\n"
        )
    lines.append("_Use `/discard N` to delete_")
    await send("\n".join(lines))


async def _cmd_show_post(post_id: int) -> None:
    from content.approval_flow import get_post_text
    text = await get_post_text(post_id)
    if not text:
        await send(f"⚠️ Post #{post_id} not found.")
        return
    char_count = len(text)
    await send(
        f"📝 *Post #{post_id}* {'✅' if char_count <= 270 else '⚠️'} `{char_count}/270`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n{text}\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"_Copy and post manually._\n_Use `/discard {post_id}` to delete._"
    )


async def _cmd_discard(post_id: int) -> None:
    from content.approval_flow import discard_post
    success = await discard_post(post_id)
    await send(f"🗑️ Post #{post_id} deleted." if success else f"⚠️ Post #{post_id} not found.")


async def _cmd_backtest(coin: str) -> None:
    from backtest.engine import run_backtest
    await send(f"⏳ Running backtest for `{coin}`...")
    try:
        loop   = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: run_backtest(coin=coin, capital=cfg.CAPITAL, leverage=10)),
            timeout=120.0,
        )
        if "error" in result:
            await send(f"❌ Backtest failed: `{result['error']}`")
            return
        bg = result.get("by_grade", {})
        pb = result.get("phase_breakdown", {})
        await send(
            f"📊 *Backtest — {coin}USDT*\n\n"
            f"Period: `{result.get('period_start')} → {result.get('period_end')}`\n\n"
            f"Signals: `{result.get('total_signals', 0)}` · Trades: `{result.get('total_trades', 0)}`\n"
            f"WR: `{result.get('win_rate', 0)}%` · PnL: `${result.get('total_pnl', 0)}`\n"
            f"Max DD: `{result.get('max_drawdown', 0)}%` · TP hit: `{pb.get('tp1_hit_rate', 0)}%`\n\n"
            f"A+: `{bg.get('A+',{}).get('win_rate',0)}% WR` · `{bg.get('A+',{}).get('trades',0)} trades`\n"
            f"A:  `{bg.get('A',{}).get('win_rate',0)}% WR` · `{bg.get('A',{}).get('trades',0)} trades`\n"
            f"B:  `{bg.get('B',{}).get('win_rate',0)}% WR` · `{bg.get('B',{}).get('trades',0)} trades`\n"
        )
    except asyncio.TimeoutError:
        await send("❌ Backtest timed out after 120s")
    except Exception as e:
        await send(f"❌ Backtest error: `{e}`")


async def _cmd_scan() -> None:
    await send("🔍 *Manual Scan Started*\n\nScanning all coins...\nThis takes 1-2 minutes.")
    try:
        from data.cache import cache as _cache
        _cache.clear_all()
        from alerts.scanner import scan_all_coins
        await scan_all_coins()
    except Exception as e:
        await send(f"❌ *Scan Failed*\n\n`{e}`")


async def _cmd_queue() -> None:
    cached    = _all_cached_signals()
    tradeable = sorted(
        [r for r in cached if r.get("grade") in cfg.MIN_GRADE_TO_TRADE and r.get("direction") in ["LONG", "SHORT"] and not _is_skipped(r.get("coin", ""))],
        key=lambda x: x.get("score", 0), reverse=True,
    )[:3]

    if not tradeable:
        await send("📋 *Signal Queue*\n\nNo signals in cache.\nUse /scan to scan now.")
        return

    lines = [f"📋 *Signal Queue — {len(tradeable)} Signal(s)*\n_{_now_ist()}_\n"]
    for r in tradeable:
        sig       = r.get("signal", {})
        grade     = r.get("grade", "?")
        direction = r.get("direction", "?")
        score     = r.get("score", 0)
        ml_prob   = r.get("ml_probability")
        actual_rr = r.get("actual_rr", 0)
        tp_mult   = r.get("tp_mult", 1.5)
        emoji     = "🏆" if grade == "A+" else "✅" if grade == "A" else "👀"
        dir_emoji = "📈" if direction == "LONG" else "📉"
        ml_line   = f"ML: {'✅' if ml_prob >= 0.65 else '❌'} `{ml_prob*100:.1f}%` · " if ml_prob is not None else ""
        lines.append(
            f"{emoji} *{r.get('coin', '?')}USDT* — Grade `{grade}` ({score}/100)\n"
            f"{dir_emoji} {direction} · {ml_line}R:R `1:{actual_rr}`\n"
            f"Entry: `{sig.get('entry', '--')}` · SL: `{sig.get('sl', '--')}` · TP: `{sig.get('tp1', '--')}` ({tp_mult}x)\n"
        )
    await send("\n".join(lines))


async def _cmd_help() -> None:
    await send(
        "🤖 *Signal Engine v5 — Commands*\n\n"
        "*ESSENTIALS*\n"
        "/status   — bot status + WS\n"
        "/queue    — top 3 signals\n"
        "/scan     — manual scan\n\n"
        "*TRADING*\n"
        "/trades          — open positions\n"
        "/position XLM   — deep dive\n"
        "/health          — health check\n"
        "/balance         — account balance\n"
        "/profit          — profit summary\n\n"
        "*MARKET*\n"
        "/btc · /coin ETH · /funding · /fear\n\n"
        "*CONTENT*\n"
        "/pending · /brief · #N · /discard N\n\n"
        "*PERFORMANCE*\n"
        "/pnl · /daily · /stats · /grade · /history\n"
        "/backtest BTC\n\n"
        "*OTHER*\n"
        "/ml · /mode · /help\n"
    )


async def send_signal(signal: dict, coin: str, regime: str, session: str) -> None:
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return
    if signal.get("direction") not in ["LONG", "SHORT"]:
        return
    if not signal.get("entry") or _is_skipped(coin):
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
    sl_pct    = signal.get("sl_pct", 0)
    risk_amt  = signal.get("risk_amt", 0)
    pos_size  = signal.get("pos_size", 0)
    tp_mult   = signal.get("tp_mult", 1.5)
    actual_rr = signal.get("actual_rr", 0)
    ml_prob   = signal.get("ml_probability")
    expl      = signal.get("explanation", {})
    thesis    = expl.get("thesis", "")
    conf_line   = f"Confidence: `{conf_label} ({score}/100)`\n" if conf_label else ""
    ml_line     = f"ML Prob: {'✅' if ml_prob >= 0.65 else '❌'} `{ml_prob*100:.1f}%`\n" if ml_prob is not None else ""
    grade_note  = "_Grade B — paper mode only_\n\n" if grade == "B" else ""
    thesis_line = f"\n*Why:* {thesis}\n" if thesis else ""

    await send(
        f"{emoji} *Grade {grade} — {direction}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*{coin}USDT — {dir_emoji} {direction}*\n"
        f"{conf_line}"
        f"{ml_line}"
        f"Regime:  `{regime}`\n"
        f"Session: `{session}`\n"
        f"Time:    `{_now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Entry:   `{entry:.4f}`\n"
        f"SL:      `{sl:.4f}` ({sl_pct:.2f}%)\n"
        f"TP:      `{tp1:.4f}` ({tp_mult}x risk)\n"
        f"R:R:     `1:{actual_rr}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Risk:    `${risk_amt:.2f}`\n"
        f"Size:    `${pos_size:.2f}`\n\n"
        f"{grade_note}"
        f"{thesis_line}"
        f"_Signal forwarded to execution engine._"
    )


async def send_scan_summary(results: list) -> None:
    from scheduler import get_next_scan_time
    cats      = categorize_results(results)
    tradeable = cats["tradeable"]
    watching  = cats["watching"]
    building  = cats["building"]
    next_scan = get_next_scan_time()

    if tradeable:
        lines = [f"🔍 *Scan Complete — {_now_ist()}*\n{len(tradeable)} tradeable signal(s)\n━━━━━━━━━━━━━━━━━━━━━━\n"]
        for r in tradeable[:3]:
            g         = r.get("grade", "?")
            direction = r.get("direction", "?")
            score     = r.get("score", 0)
            coin      = r.get("coin", "?")
            conf_label = r.get("explanation", {}).get("confidence_label", "")
            ml_prob   = r.get("ml_probability")
            actual_rr = r.get("actual_rr", 0)
            emoji     = "🏆" if g == "A+" else "✅" if g == "A" else "👀"
            dir_emoji = "📈" if direction == "LONG" else "📉"
            ml_str    = f" · ML:`{ml_prob*100:.0f}%`" if ml_prob is not None else ""
            lines.append(
                f"{emoji} *{coin}* — Grade {g} ({score}/100){' · ' + conf_label if conf_label else ''}{ml_str}\n"
                f"{dir_emoji} {direction} · R:R `1:{actual_rr}`\n"
            )
        lines.append(f"\nNext scan: `{next_scan}`")
        await send("\n".join(lines))
        return

    lines = [f"😴 *No Tradeable Signals — {_now_ist()}*\n━━━━━━━━━━━━━━━━━━━━━━\n"]
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