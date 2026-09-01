import logging
from datetime import datetime, timezone, timedelta
from alerts.telegram.client import send
from config import cfg

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def _grade_emoji(grade: str) -> str:
    return {"A+": "🏆", "A": "⭐", "B": "👀"}.get(grade, "📊")


def _dir_emoji(direction: str) -> str:
    return "📈" if direction == "LONG" else "📉"


async def cmd_trades() -> None:
    from trade.monitor import get_open_positions_enriched

    try:
        trades = await get_open_positions_enriched()

        if not trades:
            await send(
                f"📊 *Open Trades*\n"
                f"🕐 `{_now_ist()}`\n\n"
                f"😴 No open trades"
            )
            return

        lines = [
            f"📊 *Open Trades — {len(trades)}*\n"
            f"🕐 `{_now_ist()}`\n"
        ]

        for t in trades:
            coin      = t.get("coin", "--")
            direction = t.get("direction", "--")
            grade     = t.get("grade", "--")
            entry     = float(t.get("entry_price") or 0)
            leverage  = int(t.get("leverage") or 1)
            margin    = float(t.get("margin_used") or 0)
            live      = float(t.get("current_price") or entry)
            pnl_abs   = float(t.get("profit_abs") or 0)
            pnl_pct   = round(pnl_abs / margin * 100, 2) if margin > 0 else 0.0
            pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
            pnl_emoji = "💚" if pnl_abs >= 0 else "🔴"
            d_emoji   = _dir_emoji(direction)
            g_emoji   = _grade_emoji(grade)
            sl        = t.get("sl_price")
            tp        = t.get("tp1_price")
            duration  = t.get("duration", "--")
            health    = t.get("health", {})
            h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
            h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")

            lines.append(
                f"\n{d_emoji} *{coin}USDT* {g_emoji} `{grade}`\n"
                f"💲 Entry:   `{entry:.6f}`\n"
                f"💲 Live:    `{live:.6f}`\n"
                f"{pnl_emoji} PnL:     `{pnl_str}` ({pnl_pct:.2f}%)\n"
                f"🛑 SL:      `{sl:.6f}`\n" if sl else ""
                f"✅ TP:      `{tp:.6f}`\n" if tp else ""
                f"⚖️ Lev:     `{leverage}x`  💰 Margin: `${margin:.2f}`\n"
                f"{h_emoji} Health:  `{h_state}`  ⏱️ `{duration}`"
            )

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_trades error: %s", e)
        await send("❌ Could not fetch trades.")


async def cmd_position(coin: str) -> None:
    from trade.monitor import get_open_positions_enriched

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
        sl        = trade.get("sl_price")
        tp        = trade.get("tp1_price")
        live      = float(trade.get("current_price") or entry)
        pnl_abs   = float(trade.get("profit_abs") or 0)
        pnl_pct   = round(pnl_abs / margin * 100, 2) if margin > 0 else 0.0
        pnl_str   = f"+${pnl_abs:.4f}" if pnl_abs >= 0 else f"-${abs(pnl_abs):.4f}"
        pnl_emoji = "💚" if pnl_abs >= 0 else "🔴"
        d_emoji   = _dir_emoji(direction)
        grade     = trade.get("grade", "--")
        g_emoji   = _grade_emoji(grade)
        duration  = trade.get("duration", "--")
        session   = trade.get("session_at_entry", "--")
        regime    = trade.get("regime_at_entry",  "--")
        score     = trade.get("score_at_entry",   0)
        version   = trade.get("system_version",   "--")
        health    = trade.get("health", {})
        h_state   = health.get("state", "UNKNOWN") if health else "Checking..."
        h_emoji   = {"HEALTHY": "✅", "WARNING": "⚠️", "INVALIDATED": "🚨"}.get(h_state, "⏳")
        failures  = health.get("failures", []) if health else []
        warnings  = health.get("warnings", []) if health else []

        sl_pct  = abs(entry - sl)  / entry * 100 if sl  and entry else 0
        sl_dist = abs(live  - sl)  / entry * 100 if sl  and entry else 0
        tp_dist = abs(tp    - live) / entry * 100 if tp  and entry else 0

        msg = (
            f"{d_emoji} *{coin}USDT — Position Detail*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{g_emoji} Grade:    `{grade}`  🎯 Score: `{score}`\n"
            f"⏰ Session:  `{session}`\n"
            f"📍 Regime:   `{regime}`\n"
            f"📦 Version:  `{version}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💲 Entry:    `${entry:.6f}`\n"
            f"💲 Live:     `${live:.6f}`\n"
            f"{pnl_emoji} PnL:      `{pnl_str}` ({pnl_pct:.2f}%)\n\n"
            f"🛑 SL:       `${sl:.6f}` ({sl_pct:.2f}% from entry)\n" if sl else ""
            f"✅ TP:       `${tp:.6f}` ({tp_dist:.2f}% away)\n\n" if tp else ""
            f"⚖️ Leverage: `{leverage}x`  💰 Margin: `${margin:.2f}`\n"
            f"⏱️ Open:     `{duration}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{h_emoji} Health:   `{h_state}`\n"
        )

        if failures:
            msg += f"\n❌ _{failures[0]}_"
        elif warnings:
            msg += f"\n⚠️ _{warnings[0]}_"

        msg += "\n\n_Use dashboard Force Sell to close._"

        await send(msg)

    except Exception as e:
        log.error("cmd_position %s: %s", coin, e)
        await send(f"❌ Could not fetch position for `{coin}`.")


async def cmd_scan() -> None:
    await send(
        f"🔍 *Manual Scan Started*\n\n"
        f"Scanning `{len(cfg.COINS)}` coins...\n"
        f"⏳ Takes 1-2 minutes."
    )
    try:
        from data.cache import cache as _cache
        _cache.clear_all()
        from alerts.scanner import scan_all_coins
        await scan_all_coins()
    except Exception as e:
        await send(f"❌ *Scan Failed*\n\n`{e}`")


async def cmd_queue() -> None:
    from engines.state import get as get_coin_state
    from data.cache import cache
    from scheduler import get_next_scan_time
    from database import SessionLocal, Trade as TradeModel

    next_scan = get_next_scan_time()
    mode      = "🔴 LIVE" if not cfg.PAPER_TRADING else "🔵 PAPER"

    try:
        with SessionLocal() as db:
            in_trade_count = db.query(TradeModel).filter(
                TradeModel.is_active == True
            ).count()
    except Exception:
        in_trade_count = 0

    watching = []
    idle     = []
    live_signals = []

    for coin in cfg.COINS:
        c      = cache.get_raw(f"signal_{coin}")
        status = get_coin_state(coin)["status"]

        if c and c.get("grade") in ("A+", "A", "B") and c.get("direction") in ("LONG", "SHORT"):
            live_signals.append(c)
        elif status == "watching":
            watching.append((coin, c))
        elif status != "in_trade":
            idle.append((coin, c))

    lines = [
        f"📋 *Signal Queue*\n"
        f"🕐 `{_now_ist()}`\n"
    ]

    if live_signals:
        lines.append(f"\n🎯 *Live Signals — {len(live_signals)}*")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        for s in live_signals[:5]:
            coin      = s.get("coin", "--")
            grade     = s.get("grade", "--")
            direction = s.get("direction", "--")
            score     = s.get("score", 0)
            signal    = s.get("signal", {})
            entry     = signal.get("entry")
            sl        = signal.get("sl")
            tp1       = signal.get("tp1")
            g_emoji   = {"A+": "🏆", "A": "⭐", "B": "👀"}.get(grade, "📊")
            d_emoji   = "📈" if direction == "LONG" else "📉"

            lines.append(
                f"{g_emoji} *{coin}*  {d_emoji} `{direction}`  Score `{score:.1f}`"
            )
            if entry:
                lines.append(
                    f"   🎯 `{entry:.4f}`  🛑 `{sl:.4f}`  ✅ `{tp1:.4f}`"
                )

    if watching:
        lines.append(f"\n⚡ *Watching — {len(watching)}*")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        for coin, c in watching[:5]:
            score     = c.get("score", 0) if c else 0
            direction = c.get("direction", "--") if c else "--"
            d_emoji   = "📈" if direction == "LONG" else "📉" if direction == "SHORT" else "➖"
            score_str = f"  Score `{score:.1f}`" if score > 0 else ""
            lines.append(f"  {d_emoji} `{coin}`{score_str}")

    if in_trade_count:
        lines.append(f"\n🔥 *In Trade — {in_trade_count}*")

    if idle:
        lines.append(f"\n😴 *Idle — {len(idle)}*")
        idle_reasons = {}
        for coin, c in idle:
            reason = c.get("reason", "scanning") if c else "scanning"
            reason = reason.replace("_", " ")
            idle_reasons[reason] = idle_reasons.get(reason, 0) + 1
        for reason, count in sorted(idle_reasons.items(), key=lambda x: x[1], reverse=True)[:4]:
            lines.append(f"  `{reason}`: {count}")

    lines.append(f"\n{mode}  ·  🕐 Next: `{next_scan}`")

    await send("\n".join(lines))