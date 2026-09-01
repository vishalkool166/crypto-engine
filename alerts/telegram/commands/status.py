import logging
from datetime import datetime, timezone, timedelta
from alerts.telegram.client import send
from config import cfg

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def _now_ist_full() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %I:%M %p IST")


async def cmd_status() -> None:
    from alerts.scanner import get_db_stats, get_scan_stats
    from scheduler import get_next_scan_time
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_ws_status
    from engines.state import get as get_coin_state

    stats      = get_db_stats()
    ws         = get_ws_status()
    scan_stats = get_scan_stats()
    mode       = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"
    next_scan  = get_next_scan_time()

    try:
        open_trades = await get_open_positions_enriched()
    except Exception:
        open_trades = []

    state_counts = {}
    for coin in cfg.COINS:
        s = get_coin_state(coin)["status"]
        state_counts[s] = state_counts.get(s, 0) + 1

    ws_emoji  = "✅" if ws["mark_price_connected"] else "❌"
    frozen    = "  🔴 *FROZEN*" if cfg.ADAPTATION_FROZEN else ""

    closed   = stats.get("closed", 0)
    wins     = stats.get("wins",   0)
    win_rate = stats.get("win_rate", 0)
    total_pnl= stats.get("total_pnl", 0)
    pnl_sign = "+" if total_pnl >= 0 else ""
    pnl_emoji= "💚" if total_pnl >= 0 else "🔴"

    await send(
        f"📊 *Signal Engine Status*\n"
        f"🕐 `{_now_ist_full()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{mode}  ·  v`{cfg.SYSTEM_VERSION}`{frozen}\n\n"
        f"*Engine:*\n"
        f"🪙 Coins:      `{len(cfg.COINS)}`\n"
        f"⚡ Watching:   `{state_counts.get('watching', 0)}`\n"
        f"🔥 In Trade:   `{len(open_trades)}`\n"
        f"💤 Cooldown:   `{state_counts.get('cooldown', 0)}`\n"
        f"😴 Idle:       `{state_counts.get('idle', 0)}`\n\n"
        f"*WebSocket:*\n"
        f"{ws_emoji} Mark Price:  `{'Live' if ws['mark_price_connected'] else 'Down'}`\n"
        f"{'✅' if ws['user_data_connected'] else '❌'} User Data:   `{'Live' if ws['user_data_connected'] else 'Down'}`\n"
        f"💲 Prices:     `{ws['prices_cached']} cached`\n\n"
        f"*Performance:*\n"
        f"📈 Closed:     `{closed}` trades\n"
        f"🎯 Win Rate:   `{win_rate}%`\n"
        f"{pnl_emoji} Total PnL:  `{pnl_sign}${total_pnl:.2f}`\n\n"
        f"*Scans:*\n"
        f"🔍 Total:      `{scan_stats.get('total_scans', 0)}`\n"
        f"🎯 Signals:    `{scan_stats.get('total_signals', 0)}`\n\n"
        f"🕐 Next scan:  `{next_scan}`"
    )


async def cmd_mode() -> None:
    from trade.ws import get_ws_status

    ws     = get_ws_status()
    mode   = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"
    grades = ", ".join(cfg.MIN_GRADE_TO_TRADE)
    frozen = "🔴 Frozen" if cfg.ADAPTATION_FROZEN else "🟢 Active"

    await send(
        f"⚙️ *Bot Configuration*\n"
        f"🕐 `{_now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔧 Mode:        `{mode}`\n"
        f"📦 Version:     `{cfg.SYSTEM_VERSION}`\n"
        f"🧠 Adaptation:  `{frozen}`\n"
        f"🪙 Coins:       `{len(cfg.COINS)}`\n"
        f"🏆 Grades:      `{grades}`\n"
        f"🕐 Scan:        `every :00/:15/:30/:45 UTC`\n\n"
        f"*WebSocket Streams:*\n"
        f"{'✅' if ws['mark_price_connected'] else '❌'} Mark Price\n"
        f"{'✅' if ws['user_data_connected']  else '❌'} User Data\n"
        f"{'✅' if ws.get('kline_ws_connected') else '❌'} Kline\n"
        f"{'✅' if ws.get('ticker_ws_connected') else '❌'} Ticker\n"
    )


async def cmd_health() -> None:
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_mark_price

    try:
        trades = await get_open_positions_enriched()
    except Exception:
        trades = []

    if not trades:
        await send(
            f"💚 *Trade Health*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"😴 No open trades"
        )
        return

    lines = [
        f"💚 *Trade Health — {len(trades)} Open*\n"
        f"🕐 `{_now_ist()}`\n"
    ]

    for t in trades:
        coin      = t.get("coin", "--")
        direction = t.get("direction", "--")
        entry     = float(t.get("entry_price") or 0)
        leverage  = int(t.get("leverage") or 1)
        margin    = float(t.get("margin_used") or 0)
        is_short  = direction == "SHORT"
        live      = get_mark_price(coin) or float(t.get("current_price") or entry)
        pnl_abs   = round(
            ((entry - live) if is_short else (live - entry)) / entry * margin * leverage
            - margin * leverage * 0.001, 4
        ) if entry > 0 else 0.0
        pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
        pnl_emoji = "💚" if pnl_abs >= 0 else "🔴"
        side      = "📈" if direction == "LONG" else "📉"
        health    = t.get("health", {})
        h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
        h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")
        failures  = health.get("failures", []) if health else []
        warnings  = health.get("warnings", []) if health else []

        lines.append(
            f"\n{side} *{coin}* `{direction}`\n"
            f"{h_emoji} Health:  `{h_state}`\n"
            f"{pnl_emoji} PnL:     `{pnl_str}`"
        )
        if failures:
            lines.append(f"❌ _{failures[0]}_")
        elif warnings:
            lines.append(f"⚠️ _{warnings[0]}_")

    await send("\n".join(lines))


async def cmd_balance() -> None:
    from trade.exchange import get_balance
    from trade.ws import get_ws_status

    try:
        b      = await get_balance()
        ws     = get_ws_status()
        mode   = "DEMO" if cfg.PAPER_TRADING else "LIVE"
        total  = b['total']
        free   = b['free']
        used   = b['used']
        unreal = b.get('unrealized', 0)

        pnl_emoji = "💚" if unreal >= 0 else "🔴"

        await send(
            f"💰 *Balance — {mode}*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Total:       `${total:.2f} USDT`\n"
            f"✅ Free:        `${free:.2f} USDT`\n"
            f"🔒 In Use:      `${used:.2f} USDT`\n"
            f"{pnl_emoji} Unrealized:  `${unreal:.4f} USDT`\n\n"
            f"{'✅' if ws['user_data_connected'] else '❌'} WS: `{'Connected' if ws['user_data_connected'] else 'Disconnected'}`"
        )
    except Exception as e:
        log.error("cmd_balance error: %s", e)
        await send("❌ Could not fetch balance.")


async def cmd_profit() -> None:
    try:
        from trade.monitor import get_profit_summary

        d      = get_profit_summary()
        profit = float(d.get("profit_all_coin", 0))
        wr     = float(d.get("winrate", 0)) * 100
        count  = d.get("trade_count", 0)
        wins   = d.get("wins",   0)
        losses = d.get("losses", 0)

        pnl_emoji = "💚" if profit >= 0 else "🔴"
        pnl_sign  = "+" if profit >= 0 else ""

        await send(
            f"💰 *Profit Summary*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} Total PnL:    `{pnl_sign}${profit:.4f}`\n"
            f"🎯 Win Rate:    `{wr:.1f}%`\n"
            f"📊 Trades:      `{count}`\n"
            f"✅ Wins:        `{wins}`\n"
            f"❌ Losses:      `{losses}`\n\n"
            f"💸 Commission:  `${d.get('total_commission', 0):.4f}`\n"
            f"💱 Funding:     `${d.get('total_funding_fees', 0):.4f}`\n\n"
            f"🏆 Best:   `{d.get('best_pair',  '--')}`\n"
            f"📉 Worst:  `{d.get('worst_pair', '--')}`"
        )
    except Exception as e:
        log.error("cmd_profit error: %s", e)
        await send("❌ Could not fetch profit.")