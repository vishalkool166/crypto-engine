import logging
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist, get_in_trade_count
from config import cfg

log = logging.getLogger(__name__)


async def cmd_trades() -> None:
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_mark_price
    try:
        trades = await get_open_positions_enriched()
        if not trades:
            await send(f"📊 *Open Trades*\n_{now_ist()}_\n\nNo open trades.")
            return
        lines = [f"📊 *Open Trades — {len(trades)}*\n_{now_ist()}_\n"]
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
            sl_dist   = abs(live - sl)  / entry * 100 if sl and entry else 0
            tp_dist   = abs(tp  - live) / entry * 100 if tp and entry else 0

            thesis_line = ""
            try:
                from trade.thesis_tracker import get_thesis_summary
                ts = get_thesis_summary(t.get("trade_id", 0))
                if ts:
                    thesis_line = (
                        f"Thesis: `{ts.get('thesis_strength', 0):.2f}` — "
                        f"`{ts.get('action', '--').upper()}` · "
                        f"Captured: `{ts.get('captured_move_pct', 0):.1f}%`\n"
                    )
            except Exception:
                pass

            lines.append(
                f"{side} `{coin}` — Grade `{t.get('grade', '--')}`\n"
                f"Entry: `{entry:.6f}` · Live: `{live:.6f}`\n"
                f"PnL: {pnl_emoji} `{pnl_str}` ({pnl_pct:.2f}%)\n"
                f"SL: `{sl:.6f}` ({sl_dist:.2f}% away)\n"
                f"TP: `{tp:.6f}` ({tp_dist:.2f}% away)\n"
                f"Lev: `{leverage}x` · Margin: `${margin:.2f}`\n"
                f"Health: {h_emoji} `{h_state}` · Open: `{t.get('duration', '--')}`\n"
                f"{thesis_line}"
            )
        await send("\n".join(lines))
    except Exception as e:
        log.error("cmd_trades error: %s", e)
        await send("❌ Could not fetch trades.")


async def cmd_position(coin: str) -> None:
    from trade.monitor import get_open_positions_enriched
    from trade.ws import get_mark_price
    try:
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
        tp_dist   = abs(tp  - live) / entry * 100 if tp and entry else 0
        sl_pct    = abs(entry - sl) / entry * 100 if sl and entry else 0
        health    = trade.get("health", {})
        h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
        h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")
        failures  = health.get("failures", []) if health else []
        warnings  = health.get("warnings", []) if health else []

        msg = (
            f"{side} *{coin}USDT — Position Detail*\n_{now_ist()}_\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Grade:   `{trade.get('grade', '--')}` · Score `{trade.get('score_at_entry', 0)}`\n"
            f"Session: `{trade.get('session_at_entry', '--')}`\n"
            f"Version: `{trade.get('system_version', '--')}`\n\n"
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

        thesis_section = ""
        try:
            from trade.thesis_tracker import get_thesis_summary
            ts = get_thesis_summary(trade.get("trade_id", 0))
            if ts:
                thesis_section = (
                    f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"*Thesis:* `{ts.get('thesis_strength', 0):.2f}` — `{ts.get('action', '--').upper()}`\n"
                    f"Captured: `{ts.get('captured_move_pct', 0):.1f}%` of predicted move\n"
                    f"Open: `{ts.get('hours_open', 0):.1f}h` · "
                    f"Velocity: `{ts.get('velocity', 0):.3f}`\n"
                )
                pillars = ts.get("pillars", {})
                if pillars:
                    thesis_section += "*Pillars:*\n"
                    for name, p in pillars.items():
                        icon = "✅" if p.get("valid") else "❌"
                        thesis_section += f"  {icon} `{name}` score=`{p.get('score', 0):.2f}`\n"
        except Exception:
            pass

        msg += thesis_section
        msg += "\n\n_Use dashboard Force Sell to close._"
        await send(msg)

    except Exception as e:
        log.error("cmd_position %s: %s", coin, e)
        await send(f"❌ Could not fetch position for `{coin}`.")


async def cmd_scan() -> None:
    await send("🔍 *Manual Scan Started*\n\nScanning all coins...\nThis takes 1-2 minutes.")
    try:
        from data.cache import cache as _cache
        _cache.clear_all()
        from alerts.scanner import scan_all_coins
        await scan_all_coins()
    except Exception as e:
        await send(f"❌ *Scan Failed*\n\n`{e}`")


async def cmd_queue() -> None:
    from engines.state import get as get_coin_state
    watching = [
        coin for coin in cfg.COINS
        if get_coin_state(coin)["status"] == "watching"
    ]
    in_trade = [
        coin for coin in cfg.COINS
        if get_coin_state(coin)["status"] == "in_trade"
    ]
    in_trade_db = get_in_trade_count()

    if not watching and not in_trade_db:
        await send("📋 *Signal Queue*\n\nNo active zones or trades.\nUse /scan to scan now.")
        return

    lines = [f"📋 *Signal Queue*\n_{now_ist()}_\n"]

    if watching:
        lines.append(f"*⚡ Watching Zones — {len(watching)}*")
        for coin in watching[:5]:
            s         = get_coin_state(coin)
            setup     = s.get("setup") or {}
            direction = setup.get("direction", "--")
            zone      = setup.get("zone", {}) or {}
            dist      = zone.get("distance_pct", 0)
            dir_emoji = "📈" if direction == "LONG" else "📉"
            lines.append(
                f"{dir_emoji} `{coin}` — `{direction}` · `{dist:.2f}%` from zone"
            )

    if in_trade_db:
        lines.append(f"\n*🔥 In Trade — {in_trade_db}*")
        for coin in in_trade[:3]:
            s         = get_coin_state(coin)
            setup     = s.get("setup") or {}
            direction = setup.get("direction", "--")
            dir_emoji = "📈" if direction == "LONG" else "📉"
            lines.append(f"{dir_emoji} `{coin}` — `{direction}`")

    await send("\n".join(lines))