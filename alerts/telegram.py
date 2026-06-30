import httpx
import logging
import time
import asyncio
from collections import deque
from datetime import datetime, timezone, timedelta
from fastapi import Request
from config import cfg
from database import SessionLocal, get_session
from alerts.utils import now_ist, categorize_results
from data.cache import cache
from engines.signal import get_session as get_trading_session

log = logging.getLogger(__name__)

BASE   = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}"
DOMAIN = cfg.DOMAIN

IST = timezone(timedelta(hours=5, minutes=30))

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
    results = []
    for coin in cfg.COINS:
        cached = cache.get_raw(f"signal_{coin}")
        if cached:
            results.append(cached)
    return results


def _get_stats() -> tuple[dict, dict]:
    from alerts.scanner import get_db_stats
    return get_db_stats(), {}


def _grade_block(label: str, data: dict) -> str:
    return (
        f"*Grade {label}*\n"
        f"Trades:   `{data.get('total', 0)}`\n"
        f"Wins:     `{data.get('wins', 0)}`\n"
        f"Losses:   `{data.get('losses', 0)}`\n"
        f"Win Rate: `{data.get('win_rate', 0)}%`\n"
        f"PnL:      `${data.get('total_pnl', 0)}`\n"
    )


def _build_pnl_message(stats: dict) -> str:
    return (
        f"💰 *PnL Report*\n\n"
        f"*All Time*\n"
        f"Total:   `{stats.get('closed', 0) + stats.get('pending', 0)}` signals\n"
        f"Wins:    `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"WR:      `{stats.get('win_rate', 0)}%`\n"
        f"PnL:     `${stats.get('total_pnl', 0)}`\n"
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
        {"command": "status",    "description": "Bot status overview"},
        {"command": "queue",     "description": "Top 3 signals right now"},
        {"command": "scan",      "description": "Trigger manual scan"},
        {"command": "health",    "description": "All open trades health"},
        {"command": "trades",    "description": "Open trades with live PnL"},
        {"command": "position",  "description": "Deep dive on trade — /position XLM"},
        {"command": "balance",   "description": "Account balance"},
        {"command": "profit",    "description": "Profit summary"},
        {"command": "btc",       "description": "BTC analysis"},
        {"command": "coin",      "description": "Any coin analysis — /coin ETH"},
        {"command": "funding",   "description": "Funding rates"},
        {"command": "fear",      "description": "Fear and greed index"},
        {"command": "pending",   "description": "Posts waiting"},
        {"command": "brief",     "description": "Generate market brief post"},
        {"command": "discard",   "description": "Delete a post — /discard 5"},
        {"command": "pnl",       "description": "All time PnL"},
        {"command": "daily",     "description": "Today summary"},
        {"command": "stats",     "description": "Full all time stats"},
        {"command": "grade",     "description": "Grade accuracy"},
        {"command": "history",   "description": "Last 5 signals"},
        {"command": "backtest",  "description": "Backtest a coin — /backtest BTC"},
        {"command": "backfill",  "description": "Backfill historical candle data"},
        {"command": "ml",        "description": "ML model status"},
        {"command": "mode",      "description": "Current bot config"},
        {"command": "help",      "description": "Full command list"},
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
        text    = msg.get("text", "").strip()
        chat_id = str(msg.get("chat", {}).get("id", ""))

        if chat_id != str(cfg.TELEGRAM_CHAT_ID):
            return

        await _handle_command(text, chat_id)

    except Exception as e:
        log.error(f"Webhook handler error: {e}")


async def _cmd_backfill(coin: str = None):
    if coin:
        await send(f"⏳ *Backfill started for {coin}...*")
    else:
        await send("⏳ *Backfill started for all coins...*\nTakes 3-5 minutes.")
    try:
        from backfill import run_backfill
        asyncio.create_task(run_backfill(coins=[coin] if coin else None))
    except Exception as e:
        await send(f"❌ Backfill failed: `{str(e)}`")


async def _handle_command(text: str, chat_id: str = ""):
    t = text.lower().strip()

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
            await send("⚠️ Coin universe is empty.\n\nAdd coins via the dashboard first.")
        else:
            await send(
                f"⚠️ `{coin}` not in your universe.\n\n"
                f"Your coins: `{', '.join(coins)}`\n\n"
                f"Add it via dashboard → Coin Universe."
            )
        return

    if t.startswith("/position"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if not coin:
            await send("⚠️ Usage: `/position XLM`")
            return
        await _cmd_position(coin)
        return

    if t.startswith("/backtest"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else ""
        if coin in cfg.COINS:
            await _cmd_backtest(coin)
        else:
            await send(f"⚠️ Usage: `/backtest BTC`")
        return

    if t.startswith("/backfill"):
        parts = t.split()
        coin  = parts[1].upper() if len(parts) > 1 else None
        await _cmd_backfill(coin)
        return

    if t.startswith("/discard"):
        parts = t.split()
        if len(parts) > 1:
            try:
                post_id = int(parts[1].replace("#", ""))
                await _cmd_discard(post_id)
            except ValueError:
                await send("⚠️ Usage: `/discard 5`")
        else:
            await send("⚠️ Usage: `/discard 5`")
        return

    if t.startswith("#") and len(t) > 1:
        try:
            post_id = int(t.replace("#", "").strip())
            await _cmd_show_post(post_id)
        except ValueError:
            pass
        return

    handlers = {
        "/status":   _cmd_status,
        "/pnl":      _cmd_pnl,
        "/queue":    _cmd_queue,
        "/daily":    _cmd_daily,
        "/scan":     _cmd_scan,
        "/help":     _cmd_help,
        "/btc":      _cmd_btc,
        "/funding":  _cmd_funding,
        "/fear":     _cmd_fear,
        "/history":  _cmd_history,
        "/stats":    _cmd_stats,
        "/grade":    _cmd_grade,
        "/mode":     _cmd_mode,
        "/brief":    _cmd_brief,
        "/ml":       _cmd_ml,
        "/trades":   _cmd_trades,
        "/balance":  _cmd_balance,
        "/profit":   _cmd_profit,
        "/health":   _cmd_health,
        "/pending":  _cmd_pending,
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
    from alerts.scanner import get_db_stats
    from scheduler import get_next_scan_time
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_ws_status

    stats     = get_db_stats()
    next_scan = get_next_scan_time()
    ws_status = get_ws_status()

    try:
        open_trades = await get_open_positions_enriched()
    except Exception:
        open_trades = []

    cached_results = _all_cached_signals()
    tradeable = [
        r for r in cached_results
        if r.get("grade") in cfg.MIN_GRADE_TO_TRADE and
        r.get("direction") in ["LONG", "SHORT"]
    ]

    mode     = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"
    ws_emoji = "✅" if ws_status["mark_price_connected"] else "❌"

    await send(
        f"📊 *Bot Status*\n"
        f"_{_now_ist_full()}_\n\n"
        f"State:       `RUNNING`\n"
        f"Mode:        `{mode}`\n"
        f"Coins:       `{len(cfg.COINS)} being scanned`\n"
        f"Grades:      `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Open trades: `{len(open_trades)}`\n"
        f"Signals:     `{len(cached_results)}` cached · `{len(tradeable)}` tradeable\n"
        f"WS Stream:   {ws_emoji} `{ws_status['prices_cached']} prices cached`\n\n"
        f"All-time signals: `{stats.get('total', 0)}`\n"
        f"Closed: `{stats.get('closed', 0)}`\n"
        f"Win rate: `{stats.get('win_rate', 0)}%`\n\n"
        f"Next scan: `{next_scan}`"
    )


async def _cmd_trades():
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
            grade     = t.get("grade", "--")
            regime    = t.get("regime_at_entry", "--")
            session   = t.get("session_at_entry", "--")
            duration  = t.get("duration", "--")

            live_price = get_mark_price(coin)
            if not live_price:
                live_price = float(t.get("current_price") or entry)

            if entry > 0 and live_price > 0:
                if is_short:
                    pnl_pct = (entry - live_price) / entry * leverage * 100
                    pnl_abs = (entry - live_price) / entry * margin * leverage
                else:
                    pnl_pct = (live_price - entry) / entry * leverage * 100
                    pnl_abs = (live_price - entry) / entry * margin * leverage
                pnl_abs = round(pnl_abs - margin * leverage * 0.001, 4)
            else:
                pnl_pct = 0.0
                pnl_abs = 0.0

            pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
            pnl_emoji = "🟢" if pnl_abs >= 0 else "🔴"
            side      = "📈 LONG" if direction == "LONG" else "📉 SHORT"

            health    = t.get("health", {})
            h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
            h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")

            sl  = t.get("sl_price")
            tp  = t.get("tp1_price")

            sl_dist = abs(live_price - sl) / entry * 100 if sl and entry else 0
            tp_dist = abs(tp - live_price) / entry * 100 if tp and entry else 0

            lines.append(
                f"{side} `{coin}` — Grade `{grade}`\n"
                f"Entry: `{entry:.6f}` · Live: `{live_price:.6f}`\n"
                f"PnL: {pnl_emoji} `{pnl_str}` ({pnl_pct:.2f}%)\n"
                f"SL: `{sl:.6f}` ({sl_dist:.2f}% away)\n"
                f"TP: `{tp:.6f}` ({tp_dist:.2f}% away)\n"
                f"Leverage: `{leverage}x` · Margin: `${margin:.2f}`\n"
                f"Regime: `{regime}` · Session: `{session}`\n"
                f"Health: {h_emoji} `{h_state}` · Open: `{duration}`\n"
            )

        await send("\n".join(lines))

    except Exception as e:
        log.error(f"_cmd_trades error: {e}")
        await send("❌ Could not fetch trades.")


async def _cmd_position(coin: str):
    try:
        from trade.monitor import get_open_positions_enriched
        from trade.ws import get_mark_price
        from database import get_session, Trade as TradeModel

        trades = await get_open_positions_enriched()
        trade  = next((t for t in trades if t.get("coin") == coin), None)

        if not trade:
            with get_session() as db:
                db_trade = db.query(TradeModel).filter(
                    TradeModel.coin      == coin,
                    TradeModel.is_active == True,
                ).first()
            if not db_trade:
                await send(f"⚠️ No open trade found for `{coin}`.")
                return

        entry     = float(trade.get("entry_price") or 0)
        direction = trade.get("direction", "--")
        leverage  = int(trade.get("leverage") or 1)
        margin    = float(trade.get("margin_used") or 0)
        is_short  = direction == "SHORT"
        grade     = trade.get("grade", "--")
        sl        = trade.get("sl_price")
        tp        = trade.get("tp1_price")
        duration  = trade.get("duration", "--")
        regime    = trade.get("regime_at_entry", "--")
        session   = trade.get("session_at_entry", "--")

        live_price = get_mark_price(coin)
        if not live_price:
            live_price = float(trade.get("current_price") or entry)

        if entry > 0 and live_price > 0:
            if is_short:
                pnl_pct = (entry - live_price) / entry * leverage * 100
                pnl_abs = (entry - live_price) / entry * margin * leverage
            else:
                pnl_pct = (live_price - entry) / entry * leverage * 100
                pnl_abs = (live_price - entry) / entry * margin * leverage
            pnl_abs = round(pnl_abs - margin * leverage * 0.001, 4)
        else:
            pnl_pct = 0.0
            pnl_abs = 0.0

        pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
        pnl_emoji = "🟢" if pnl_abs >= 0 else "🔴"
        side      = "📈 LONG" if direction == "LONG" else "📉 SHORT"

        sl_dist   = abs(live_price - sl) / entry * 100 if sl and entry else 0
        tp_dist   = abs(tp - live_price) / entry * 100 if tp and entry else 0
        sl_pct    = abs(entry - sl) / entry * 100 if sl and entry else 0

        health    = trade.get("health", {})
        h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
        h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")
        failures  = health.get("failures", []) if health else []
        warnings  = health.get("warnings", []) if health else []

        cached = cache.get_raw(f"signal_{coin}")
        thesis = ""
        if cached:
            thesis = cached.get("explanation", {}).get("thesis", "")

        msg = (
            f"{side} *{coin}USDT — Position Detail*\n"
            f"_{_now_ist()}_\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Grade:    `{grade}`\n"
            f"Regime:   `{regime}`\n"
            f"Session:  `{session}`\n\n"
            f"Entry:    `${entry:.6f}`\n"
            f"Live:     `${live_price:.6f}`\n"
            f"PnL:      {pnl_emoji} `{pnl_str}` ({pnl_pct:.2f}%)\n\n"
            f"SL:       `${sl:.6f}` ({sl_pct:.2f}% from entry)\n"
            f"          `{sl_dist:.2f}%` away from current\n"
            f"TP:       `${tp:.6f}`\n"
            f"          `{tp_dist:.2f}%` away from current\n\n"
            f"Leverage: `{leverage}x` · Margin: `${margin:.2f}`\n"
            f"Position: `${margin * leverage:.2f}`\n"
            f"Open:     `{duration}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Health: {h_emoji} `{h_state}`\n"
        )

        if failures:
            msg += "\n*Failures:*\n"
            for f in failures[:2]:
                msg += f"✘ _{f}_\n"
        elif warnings:
            msg += "\n*Warnings:*\n"
            for w in warnings[:2]:
                msg += f"⚠ _{w}_\n"

        if thesis:
            msg += f"\n*Original Thesis:*\n_{thesis[:200]}_\n"

        msg += "\n_Use dashboard Force Sell to close._"

        await send(msg)

    except Exception as e:
        log.error(f"_cmd_position error {coin}: {e}")
        await send(f"❌ Could not fetch position for `{coin}`.")


async def _cmd_balance():
    try:
        from trade.exchange import get_balance
        from trade.ws import get_ws_status
        balance   = await get_balance()
        mode      = "DEMO" if cfg.PAPER_TRADING else "LIVE"
        ws_status = get_ws_status()
        await send(
            f"💰 *Balance — {mode}*\n"
            f"_{_now_ist()}_\n\n"
            f"Total:      `${balance['total']:.2f} USDT`\n"
            f"Free:       `${balance['free']:.2f} USDT`\n"
            f"Used:       `${balance['used']:.2f} USDT`\n"
            f"Unrealized: `${balance.get('unrealized', 0):.4f} USDT`\n\n"
            f"WS: `{'✅ Connected' if ws_status['user_data_connected'] else '❌ Disconnected'}`"
        )
    except Exception as e:
        log.error(f"_cmd_balance error: {e}")
        await send("❌ Could not fetch balance.")


async def _cmd_profit():
    try:
        from trade.monitor import get_profit_summary
        data       = get_profit_summary()
        profit     = float(data.get("profit_all_coin", 0))
        profit_str = f"+${profit:.4f}" if profit >= 0 else f"-${abs(profit):.4f}"
        win_rate   = float(data.get("winrate", 0)) * 100
        trades     = data.get("trade_count", 0)

        await send(
            f"💰 *Profit Summary*\n"
            f"_{_now_ist()}_\n\n"
            f"Total PnL:    `{profit_str}`\n"
            f"Win Rate:     `{win_rate:.1f}%`\n"
            f"Total Trades: `{trades}`\n"
            f"Wins:         `{data.get('wins', 0)}`\n"
            f"Losses:       `{data.get('losses', 0)}`\n\n"
            f"Best:  `{data.get('best_pair', '--')}` `${data.get('best_pair_profit_ratio', 0):.4f}`\n"
            f"Worst: `{data.get('worst_pair', '--')}` `${data.get('worst_pair_profit_ratio', 0):.4f}`\n"
        )
    except Exception as e:
        log.error(f"_cmd_profit error: {e}")
        await send("❌ Could not fetch profit.")


async def _cmd_health():
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
            side      = "📈" if direction == "LONG" else "📉"

            live_price = get_mark_price(coin)
            if not live_price:
                live_price = float(t.get("current_price") or entry)

            if entry > 0 and live_price > 0:
                if is_short:
                    pnl_abs = (entry - live_price) / entry * margin * leverage
                else:
                    pnl_abs = (live_price - entry) / entry * margin * leverage
                pnl_abs = round(pnl_abs - margin * leverage * 0.001, 4)
            else:
                pnl_abs = 0.0

            pnl_str  = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
            health   = t.get("health", {})
            h_state  = health.get("state", "UNKNOWN") if health else "Checking..."
            h_emoji  = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")
            failures = health.get("failures", []) if health else []
            warnings = health.get("warnings", []) if health else []

            lines.append(f"{side} `{coin}` — {h_emoji} `{h_state}` · `{pnl_str}`")

            if failures:
                lines.append(f"  ✘ _{failures[0]}_")
            elif warnings:
                lines.append(f"  ⚠ _{warnings[0]}_")

            lines.append("")

        await send("\n".join(lines))

    except Exception as e:
        log.error(f"_cmd_health error: {e}")
        await send("❌ Could not fetch health.")


async def _cmd_btc():
    await _cmd_coin("BTC")


async def _cmd_coin(coin: str):
    cached = _get_cached(coin)
    if not cached:
        await send(f"No data for `{coin}`. Run /scan first.")
        return

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

    from trade.ws import get_mark_price
    live_price = get_mark_price(coin)
    price      = live_price if live_price else market.get("price", 0)
    change     = market.get("change24", 0)
    funding    = market.get("funding", 0) * 100
    sign       = "+" if change >= 0 else ""
    em         = "📈" if dir_ == "LONG" else "📉" if dir_ == "SHORT" else "👁"
    rsi        = d1d.get("rsi")
    adx        = d1d.get("adx")

    sig   = cached.get("signal", {})
    entry = sig.get("entry")
    sl    = sig.get("sl")
    tp1   = sig.get("tp1")

    base = (
        f"📊 *{coin}USDT Analysis*\n"
        f"_{_now_ist()}_\n\n"
        f"Price:   `${price:,.4f}` ({sign}{change:.2f}%)\n"
        f"Grade:   `{grade}` · Score `{score}/100`\n"
        f"Signal:  {em} `{dir_}`\n"
        f"Conf:    `{expl.get('confidence_label', '--')}`\n"
    )

    if ml_prob is not None:
        ml_icon = "✅" if ml_prob >= 0.65 else "❌"
        base += f"ML Prob: {ml_icon} `{ml_prob*100:.1f}%`\n"

    base += (
        f"\nRegime:  `{cached.get('regime', '--')}`\n"
        f"Session: `{cached.get('session', '--')}`\n\n"
    )

    if rsi and adx:
        base += (
            f"RSI:     `{rsi:.1f}`\n"
            f"ADX:     `{adx:.1f}`\n"
            f"Funding: `{funding:.4f}%`\n\n"
        )

    if entry and sl and tp1:
        base += (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Entry:   `{entry:.4f}`\n"
            f"SL:      `{sl:.4f}`\n"
            f"TP:      `{tp1:.4f}` ({tp_mult}x risk)\n"
            f"R:R:     `1:{actual_rr}`\n\n"
        )

    base += (
        f"Sweep:   `{'✅' if sweep.get('confirmed') else '❌'} {sweep.get('score',0)}/12`\n"
        f"Disp:    `{'✅' if disp.get('confirmed') else '❌'} {disp.get('score',0)}/11`\n"
        f"Retest:  `{'✅' if retest.get('confirmed') else '❌'} {retest.get('score',0)}/12`\n"
    )

    await send(base)


async def _cmd_funding():
    lines = [f"💸 *Funding Rates*\n_{_now_ist()}_\n"]
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
            f"{emoji} *Fear & Greed Index*\n"
            f"_{_now_ist()}_\n\n"
            f"Value: `{val}/100`\n"
            f"Label: `{label}`\n"
            f"{'⚠️ _Stale data — API unavailable_' if stale else ''}"
        )
    except Exception as e:
        await send(f"❌ Fear & Greed fetch failed: `{e}`")


async def _cmd_pnl():
    stats, _ = _get_stats()
    await send(_build_pnl_message(stats))


async def _cmd_daily():
    from alerts.scanner import get_db_stats
    from datetime import date
    stats = get_db_stats()

    today_pnl    = 0.0
    today_trades = 0
    try:
        with SessionLocal() as db:
            from database import Signal as SignalModel
            today_str  = date.today().isoformat()
            today_sigs = db.query(SignalModel).filter(
                SignalModel.timestamp >= today_str,
                SignalModel.outcome.in_(["win", "loss"])
            ).all()
            today_pnl    = sum(float(s.pnl or 0) for s in today_sigs)
            today_trades = len(today_sigs)
    except Exception:
        pass

    pnl_str = f"+${today_pnl:.4f}" if today_pnl >= 0 else f"-${abs(today_pnl):.4f}"

    await send(
        f"📅 *Daily Summary*\n"
        f"_{_now_ist_full()}_\n\n"
        f"Today closed: `{today_trades}` trades\n"
        f"Today PnL: `{pnl_str}`\n\n"
        f"All-time signals: `{stats.get('total', 0)}`\n"
        f"Closed: `{stats.get('closed', 0)}`\n"
        f"Pending: `{stats.get('pending', 0)}`\n\n"
        f"Wins: `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"Win Rate: `{stats.get('win_rate', 0)}%`\n"
        f"PnL: `${stats.get('total_pnl', 0)}`\n"
    )


async def _cmd_history():
    from database import Signal as SignalModel
    with get_session() as db:
        signals = db.query(SignalModel).filter(
            SignalModel.outcome.in_(["win", "loss"])
        ).order_by(SignalModel.timestamp.desc()).limit(5).all()

    if not signals:
        await send("📜 No closed signals yet.")
        return

    lines = [f"📜 *Last 5 Signals*\n_{_now_ist()}_\n"]
    for s in signals:
        emoji   = "✅" if s.outcome == "win" else "❌"
        dir_em  = "📈" if s.direction == "LONG" else "📉"
        pnl_str = f"+${s.pnl:.4f}" if (s.pnl or 0) >= 0 else f"-${abs(s.pnl or 0):.4f}"
        ts_ist  = s.timestamp.astimezone(IST).strftime("%d %b %I:%M %p") if s.timestamp else "--"
        lines.append(
            f"{emoji} {dir_em} `{s.coin}` {s.direction} Grade `{s.grade}` — `{pnl_str}`\n"
            f"_{ts_ist} IST_\n"
        )
    await send("\n".join(lines))


async def _cmd_stats():
    stats, _ = _get_stats()
    if not stats:
        await send("📊 No stats yet.")
        return

    bg = stats.get("by_grade", {})
    ap = bg.get("A+", {})
    a  = bg.get("A",  {})
    b  = bg.get("B",  {})

    await send(
        f"📊 *All Time Stats*\n"
        f"_{_now_ist()}_\n\n"
        f"Total signals: `{stats.get('total', 0)}`\n"
        f"Closed:        `{stats.get('closed', 0)}`\n"
        f"Wins:    `{stats.get('wins', 0)}`\n"
        f"Losses:  `{stats.get('losses', 0)}`\n"
        f"WR:      `{stats.get('win_rate', 0)}%`\n"
        f"PnL:     `${stats.get('total_pnl', 0)}`\n\n"
        f"*Grade A+*\n"
        f"Trades: `{ap.get('total',0)}` · WR: `{ap.get('win_rate',0)}%` · PnL: `${ap.get('total_pnl',0)}`\n\n"
        f"*Grade A*\n"
        f"Trades: `{a.get('total',0)}` · WR: `{a.get('win_rate',0)}%` · PnL: `${a.get('total_pnl',0)}`\n\n"
        f"*Grade B* _(paper only)_\n"
        f"Trades: `{b.get('total',0)}` · WR: `{b.get('win_rate',0)}%` · PnL: `${b.get('total_pnl',0)}`\n"
    )


async def _cmd_grade():
    stats, _ = _get_stats()
    bg       = stats.get("by_grade", {}) if stats else {}
    await send(
        f"🏆 *Grade Accuracy*\n\n"
        f"{_grade_block('A+', bg.get('A+', {}))}\n"
        f"{_grade_block('A',  bg.get('A',  {}))}\n"
        f"{_grade_block('B',  bg.get('B',  {}))}\n"
        f"_Minimum 50 trades for reliable data_\n"
        f"_Grade B: paper mode only_"
    )


async def _cmd_mode():
    from trade.ws import get_ws_status
    mode      = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"
    grades    = ', '.join(cfg.MIN_GRADE_TO_TRADE)
    ws_status = get_ws_status()

    await send(
        f"⚙️ *Bot Configuration*\n\n"
        f"Mode:        `{mode}`\n"
        f"Coins:       `{len(cfg.COINS)} coins`\n"
        f"Grades:      `{grades}`\n"
        f"B grade:     `{'paper only' if cfg.PAPER_TRADING else 'disabled in live'}`\n"
        f"Scan:        `every :00/:15/:30/:45 UTC`\n"
        f"ML:          `{'✅ Active' if cfg.ML_ENABLED else '⏳ Collecting data'}`\n"
        f"Content:     `{'✅ Enabled' if cfg.CONTENT_ENABLED else '❌ Disabled'}`\n"
        f"WS Prices:   `{'✅ Live' if ws_status['mark_price_connected'] else '❌ Disconnected'}`\n"
        f"WS UserData: `{'✅ Live' if ws_status['user_data_connected'] else '❌ Disconnected'}`\n"
    )


async def _cmd_brief():
    await send("⏳ Generating market brief...")
    try:
        from data.fetcher import get_fear_greed
        from data.cache import cache

        fg = {"value": 50, "label": "Neutral"}
        try:
            fg = await get_fear_greed()
        except Exception:
            pass

        cached_results = _all_cached_signals()
        cached_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        top_coins = []
        for r in cached_results[:3]:
            top_coins.append({
                "coin":  r.get("coin", "--"),
                "grade": r.get("grade", "F"),
                "score": r.get("score", 0)
            })

        btc_cached = cache.get_raw("signal_BTC")
        btc_change = 0.0
        if btc_cached:
            btc_change = btc_cached.get("market", {}).get("change24", 0)

        regimes = [r.get("regime", "") for r in cached_results if r.get("regime")]
        regime  = max(set(regimes), key=regimes.count) if regimes else "Unknown"

        sessions = [r.get("session", "") for r in cached_results if r.get("session")]
        session  = sessions[0] if sessions else "Unknown"

        now        = datetime.now(timezone.utc)
        hour       = now.hour
        time_label = "Morning" if hour < 12 else "Evening" if hour >= 17 else "Midday"

        context = {
            "regime":     regime,
            "session":    session,
            "fg_val":     fg.get("value", 50),
            "fg_label":   fg.get("label", "Neutral"),
            "btc_change": btc_change,
            "top_coins":  top_coins,
            "time_label": time_label
        }

        from content.groq_writer import generate_brief_post
        draft = await generate_brief_post(context)

        if not draft:
            await send("❌ Brief generation failed.")
            return

        from content.approval_flow import send_brief_for_approval
        await send_brief_for_approval(draft)

    except Exception as e:
        log.error(f"Brief command error: {e}")
        await send(f"❌ Brief failed: `{str(e)}`")


async def _cmd_ml():
    from ml.eligibility import get_ml_status
    status = get_ml_status()

    closed   = status.get("closed_trades", 0)
    required = status.get("required", 100)
    enabled  = status.get("ml_enabled", False)
    message  = status.get("message", "")

    progress_pct = min(100, int(closed / required * 100))
    bar_filled   = progress_pct // 10
    bar          = "█" * bar_filled + "░" * (10 - bar_filled)

    top_features = status.get("top_features", [])
    top_str = ""
    if top_features:
        top_str = "\n*Top Features:*\n" + "\n".join(
            f"  `{f['feature']}` — `{f['importance']}`"
            for f in top_features[:3]
        )

    await send(
        f"🤖 *ML Status*\n\n"
        f"Status: `{'✅ ACTIVE' if enabled else '⏳ Collecting data'}`\n\n"
        f"Progress: `{closed}/{required}` trades\n"
        f"`{bar}` {progress_pct}%\n\n"
        f"{message}\n"
        f"{top_str}\n\n"
        f"Grades tracked: `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Auto-trains at: `{required} trades`\n"
        f"Retrains every: `50 new trades`"
    )


async def _cmd_pending():
    from content.approval_flow import get_pending_posts
    posts = await get_pending_posts()

    if not posts:
        await send("📋 *Pending Posts*\n\nNo posts waiting.\n\nUse /brief to generate a market post.")
        return

    lines = [f"📋 *Pending Posts — {len(posts)}*\n"]
    lines.append("_Reply `#N` to see full text of post N_\n")

    for p in posts:
        post_type = p.get("post_type", "signal")
        icon      = "📊" if post_type == "signal" else "💬"
        coin      = p.get("coin", "MARKET")
        direction = p.get("direction", "--")
        grade     = p.get("grade", "--")
        post_text = p.get("post", "")
        preview   = post_text[:80] + "..." if len(post_text) > 80 else post_text

        lines.append(
            f"{icon} *#{p['post_id']}*"
            f"{f' — `{coin}USDT {direction}` Grade `{grade}`' if post_type == 'signal' else ' — Market Commentary'}\n"
            f"_{preview}_\n"
        )

    lines.append("_Use `/discard N` to delete a post_")
    await send("\n".join(lines))


async def _cmd_show_post(post_id: int):
    from content.approval_flow import get_post_text
    text = await get_post_text(post_id)

    if not text:
        await send(f"⚠️ Post #{post_id} not found.")
        return

    char_count = len(text)
    char_color = "✅" if char_count <= 270 else "⚠️"

    await send(
        f"📝 *Post #{post_id}* {char_color} `{char_count}/270`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"_Copy and post manually on Twitter._\n"
        f"_Use `/discard {post_id}` to delete._"
    )


async def _cmd_discard(post_id: int):
    from content.approval_flow import discard_post
    success = await discard_post(post_id)
    if success:
        await send(f"🗑️ Post #{post_id} deleted.")
    else:
        await send(f"⚠️ Post #{post_id} not found.")


async def _cmd_backtest(coin: str):
    from backtest.engine import run_backtest
    await send(f"⏳ Running backtest for `{coin}`...")
    try:
        loop   = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None, lambda: run_backtest(
                    coin    = coin,
                    capital = cfg.CAPITAL,
                    leverage= 10
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
            f"TP hit: `{pb.get('tp1_hit_rate', 0)}%`\n\n"
            f"A+: `{bg.get('A+',{}).get('win_rate',0)}% WR` · `{bg.get('A+',{}).get('trades',0)} trades`\n"
            f"A:  `{bg.get('A',{}).get('win_rate',0)}% WR` · `{bg.get('A',{}).get('trades',0)} trades`\n"
            f"B:  `{bg.get('B',{}).get('win_rate',0)}% WR` · `{bg.get('B',{}).get('trades',0)} trades`\n"
        )
    except asyncio.TimeoutError:
        await send(f"❌ Backtest timed out after 120s")
    except Exception as e:
        await send(f"❌ Backtest error: `{str(e)}`")


async def _cmd_scan():
    await send("🔍 *Manual Scan Started*\n\nScanning all coins...\nThis takes 1-2 minutes.")
    try:
        from data.cache import cache
        cache.clear_all()
        from alerts.scanner import scan_all_coins
        await scan_all_coins()
    except Exception as e:
        await send(f"❌ *Scan Failed*\n\n`{str(e)}`")


async def _cmd_queue():
    cached_results = _all_cached_signals()
    tradeable = [
        r for r in cached_results
        if r.get("grade") in cfg.MIN_GRADE_TO_TRADE and
        r.get("direction") in ["LONG", "SHORT"] and
        not _is_skipped(r.get("coin", ""))
    ]
    tradeable.sort(key=lambda x: x.get("score", 0), reverse=True)
    top3 = tradeable[:3]

    if not top3:
        await send("📋 *Signal Queue*\n\nNo signals in cache.\nUse /scan to scan now.")
        return

    lines = [f"📋 *Signal Queue — {len(top3)} Signal(s)*\n_{_now_ist()}_\n"]

    for r in top3:
        sig       = r.get("signal", {})
        coin      = r.get("coin", "?")
        grade     = r.get("grade", "?")
        direction = r.get("direction", "?")
        score     = r.get("score", 0)
        ml_prob   = r.get("ml_probability")
        actual_rr = r.get("actual_rr", 0)
        tp_mult   = r.get("tp_mult", 1.5)
        emoji     = "🏆" if grade == "A+" else "✅" if grade == "A" else "👀"
        dir_emoji = "📈" if direction == "LONG" else "📉"

        ml_line = ""
        if ml_prob is not None:
            ml_icon = "✅" if ml_prob >= 0.65 else "❌"
            ml_line = f"ML: {ml_icon} `{ml_prob*100:.1f}%` · "

        lines.append(
            f"{emoji} *{coin}USDT* — Grade `{grade}` ({score}/100)\n"
            f"{dir_emoji} {direction} · {ml_line}R:R `1:{actual_rr}`\n"
            f"Entry: `{sig.get('entry', '--')}` · SL: `{sig.get('sl', '--')}` · TP: `{sig.get('tp1', '--')}` ({tp_mult}x)\n"
        )

    await send("\n".join(lines))


async def _cmd_help():
    await send(
        "🤖 *Signal Engine v5 — Commands*\n\n"
        "*ESSENTIALS*\n"
        "/status   — bot status + WS connection\n"
        "/queue    — top 3 signals right now\n"
        "/scan     — trigger manual scan\n\n"
        "*TRADING*\n"
        "/trades          — all open positions\n"
        "/position XLM   — deep dive on trade\n"
        "/health          — health check all trades\n"
        "/balance         — account balance\n"
        "/profit          — profit summary\n\n"
        "*MARKET*\n"
        "/btc         — BTC analysis\n"
        "/coin ETH    — any coin analysis\n"
        "/funding     — funding rates\n"
        "/fear        — fear & greed index\n\n"
        "*CONTENT*\n"
        "/pending     — posts waiting\n"
        "/brief       — generate market post\n"
        "#N           — see full text of post N\n"
        "/discard N   — delete post N\n\n"
        "*PERFORMANCE*\n"
        "/pnl     — all time PnL\n"
        "/daily   — today summary\n"
        "/stats   — full all time stats\n"
        "/grade   — grade accuracy\n"
        "/history — last 5 signals\n"
        "/backtest BTC — backtest a coin\n\n"
        "*OTHER*\n"
        "/ml      — ML model status\n"
        "/mode    — bot config + WS status\n"
        "/help    — this message\n"
    )


async def send_signal(signal: dict, coin: str, regime: str, session: str):
    if signal.get("grade") not in cfg.MIN_GRADE_TO_TRADE:
        return
    if signal.get("direction") not in ["LONG", "SHORT"]:
        return
    if not signal.get("entry"):
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
    sl_pct    = signal.get("sl_pct", 0)
    risk_amt  = signal.get("risk_amt", 0)
    pos_size  = signal.get("pos_size", 0)
    tp_mult   = signal.get("tp_mult", 1.5)
    actual_rr = signal.get("actual_rr", 0)
    emoji     = "🏆" if grade == "A+" else "✅" if grade == "A" else "👀"
    dir_emoji = "📈" if direction == "LONG" else "📉"
    ml_prob   = signal.get("ml_probability")

    explanation = signal.get("explanation", {})
    thesis      = explanation.get("thesis", "")
    conf_label  = explanation.get("confidence_label", "")

    ml_line = ""
    if ml_prob is not None:
        ml_icon = "✅" if ml_prob >= 0.65 else "❌"
        ml_line = f"ML Prob: {ml_icon} `{ml_prob*100:.1f}%`\n"

    grade_note = ""
    if grade == "B":
        grade_note = "_Grade B — paper mode only · quality filter passed_\n\n"

    await send(
        f"{emoji} *Grade {grade} — {direction}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*{coin}USDT — {dir_emoji} {direction}*\n"
        f"{'Confidence: `' + conf_label + ' (' + str(score) + '/100)`' + chr(10) if conf_label else ''}"
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
        f"{chr(10) + '*Why:* ' + thesis + chr(10) if thesis else ''}"
        f"_Signal forwarded to execution engine._"
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
            f"🔍 *Scan Complete — {_now_ist()}*\n"
            f"{len(tradeable)} tradeable signal(s)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        ]
        for r in tradeable[:3]:
            g         = r.get("grade", "?")
            direction = r.get("direction", "?")
            score     = r.get("score", 0)
            coin      = r.get("coin", "?")
            conf      = r.get("explanation", {}).get("confidence_label", "")
            ml_prob   = r.get("ml_probability")
            actual_rr = r.get("actual_rr", 0)
            emoji     = "🏆" if g == "A+" else "✅" if g == "A" else "👀"
            dir_emoji = "📈" if direction == "LONG" else "📉"
            ml_str    = f" · ML:`{ml_prob*100:.0f}%`" if ml_prob is not None else ""
            lines.append(
                f"{emoji} *{coin}* — Grade {g} ({score}/100){' · ' + conf if conf else ''}{ml_str}\n"
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