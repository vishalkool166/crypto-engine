import logging
from datetime import datetime, timezone
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist, now_ist_full, get_stats, get_in_trade_count
from config import cfg

log = logging.getLogger(__name__)


async def cmd_status() -> None:
    from alerts.scanner import get_db_stats
    from scheduler import get_next_scan_time
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_ws_status
    from engines.state import get as get_coin_state

    stats = get_db_stats()
    ws    = get_ws_status()

    try:
        open_trades = await get_open_positions_enriched()
    except Exception:
        open_trades = []

    in_trade_db  = get_in_trade_count()
    state_counts = {}
    for coin in cfg.COINS:
        s = get_coin_state(coin)["status"]
        state_counts[s] = state_counts.get(s, 0) + 1

    mode     = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"
    ws_emoji = "✅" if ws["mark_price_connected"] else "❌"
    frozen   = " 🔴 FROZEN" if cfg.ADAPTATION_FROZEN else ""

    await send(
        f"📊 *Bot Status*\n_{now_ist_full()}_\n\n"
        f"Mode:        `{mode}`\n"
        f"Version:     `{cfg.SYSTEM_VERSION}`{frozen}\n"
        f"Coins:       `{len(cfg.COINS)} scanned`\n"
        f"Grades:      `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Open trades: `{in_trade_db}`\n"
        f"WS Stream:   {ws_emoji} `{ws['prices_cached']} prices`\n\n"
        f"Coin States:\n"
        f"  Watching:  `{state_counts.get('watching',  0)}`\n"
        f"  In Trade:  `{in_trade_db}`\n"
        f"  Cooldown:  `{state_counts.get('cooldown',  0)}`\n"
        f"  Idle:      `{state_counts.get('idle',      0)}`\n\n"
        f"All-time: `{stats.get('total', 0)}` signals · "
        f"`{stats.get('closed', 0)}` closed · "
        f"`{stats.get('win_rate', 0)}%` WR\n\n"
        f"Next scan: `{get_next_scan_time()}`"
    )


async def cmd_mode() -> None:
    from trade.ws import get_ws_status
    ws = get_ws_status()
    await send(
        f"⚙️ *Bot Configuration*\n\n"
        f"Mode:        `{'🔴 LIVE' if not cfg.PAPER_TRADING else '🔵 PAPER'}`\n"
        f"Version:     `{cfg.SYSTEM_VERSION}`\n"
        f"Adaptation:  `{'🔴 Frozen' if cfg.ADAPTATION_FROZEN else '🟢 Active'}`\n"
        f"Coins:       `{len(cfg.COINS)} coins`\n"
        f"Grades:      `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Scan:        `every :00/:15/:30/:45 UTC`\n"
        f"ML:          `{'✅ Active' if cfg.ML_ENABLED else '⏳ Collecting data'}`\n"
        f"Content:     `{'✅ Enabled' if cfg.CONTENT_ENABLED else '❌ Disabled'}`\n"
        f"WS Prices:   `{'✅ Live' if ws['mark_price_connected'] else '❌ Down'}`\n"
        f"WS Kline:    `{'✅ Live' if ws.get('kline_ws_connected') else '❌ Down'}`\n"
        f"WS UserData: `{'✅ Live' if ws['user_data_connected'] else '❌ Down'}`\n"
    )


async def cmd_health() -> None:
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_mark_price
    try:
        trades = await get_open_positions_enriched()
    except Exception:
        trades = []

    if not trades:
        await send(f"💚 *Trade Health*\n_{now_ist()}_\n\nNo open trades.")
        return

    lines = [f"💚 *Trade Health — {len(trades)} Open*\n_{now_ist()}_\n"]
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


async def cmd_balance() -> None:
    from trade.exchange import get_balance
    from trade.ws import get_ws_status
    try:
        b  = await get_balance()
        ws = get_ws_status()
        await send(
            f"💰 *Balance — {'DEMO' if cfg.PAPER_TRADING else 'LIVE'}*\n_{now_ist()}_\n\n"
            f"Total:      `${b['total']:.2f} USDT`\n"
            f"Free:       `${b['free']:.2f} USDT`\n"
            f"Used:       `${b['used']:.2f} USDT`\n"
            f"Unrealized: `${b.get('unrealized', 0):.4f} USDT`\n\n"
            f"WS: `{'✅ Connected' if ws['user_data_connected'] else '❌ Disconnected'}`"
        )
    except Exception as e:
        log.error("cmd_balance error: %s", e)
        await send("❌ Could not fetch balance.")


async def cmd_profit() -> None:
    try:
        from trade.monitor import get_profit_summary
        d      = get_profit_summary()
        profit = float(d.get("profit_all_coin", 0))
        await send(
            f"💰 *Profit Summary*\n_{now_ist()}_\n\n"
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
        log.error("cmd_profit error: %s", e)
        await send("❌ Could not fetch profit.")