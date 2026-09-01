import logging
from alerts.telegram.client import send

log = logging.getLogger(__name__)


async def cmd_india() -> None:
    try:
        from engines.indian.data import is_market_open, is_orb_ready
        from engines.indian.scanner import get_orb_levels, get_today_signals
        from engines.indian.instruments import get_instruments
        from datetime import datetime, timezone, timedelta

        IST = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(IST)

        market_open = is_market_open()
        orb_ready   = is_orb_ready()
        instruments = get_instruments()
        signals     = get_today_signals()

        status_emoji = "🟢" if market_open else "🔴"
        status_text  = "Open" if market_open else "Closed"

        lines = [
            f"🇮🇳 *Indian Market — {now.strftime('%I:%M %p IST')}*\n",
            f"Status: {status_emoji} `{status_text}`",
        ]

        for name, inst in instruments.items():
            orb = get_orb_levels(name)
            if orb:
                lines.append(
                    f"\n*{name}* — `{inst['symbol']}`\n"
                    f"ORB: `{orb['low']:.2f} — {orb['high']:.2f}`\n"
                    f"Range: `{orb['size']:.2f} points`"
                )
            else:
                lines.append(f"\n*{name}* — ORB not set yet")

        if signals:
            lines.append(f"\n*Today's Signals ({len(signals)}):*")
            for s in signals:
                dir_emoji = "📈" if s["direction"] == "LONG" else "📉"
                lines.append(
                    f"{dir_emoji} `{s['instrument']}` {s['direction']} "
                    f"Entry:`{s['entry']:.2f}` SL:`{s['sl']:.2f}` TP:`{s['tp1']:.2f}`"
                )
        else:
            lines.append("\n_No signals today yet_")

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_india: %s", e)
        await send(f"❌ Indian market error: `{e}`")


async def cmd_orb() -> None:
    try:
        from engines.indian.scanner import get_orb_levels, setup_orb
        from engines.indian.instruments import get_instruments
        from engines.indian.data import is_orb_ready
        from config import cfg

        instruments = get_instruments()

        if not instruments:
            await send("⚠️ No Indian instruments configured.")
            return

        lines = ["📊 *Opening Range Levels*\n"]

        for name in cfg.INDIAN_INSTRUMENTS:
            orb = get_orb_levels(name)
            if orb:
                lines.append(
                    f"*{name}*\n"
                    f"High:  `{orb['high']:.2f}`\n"
                    f"Low:   `{orb['low']:.2f}`\n"
                    f"Range: `{orb['size']:.2f} points`\n"
                    f"Date:  `{orb.get('date', '--')}`"
                )
            else:
                if is_orb_ready():
                    result = setup_orb()
                    if result and name in result:
                        o = result[name]
                        lines.append(
                            f"*{name}* (just fetched)\n"
                            f"High:  `{o['high']:.2f}`\n"
                            f"Low:   `{o['low']:.2f}`\n"
                            f"Range: `{o['size']:.2f} points`"
                        )
                    else:
                        lines.append(f"*{name}*: ORB not available")
                else:
                    lines.append(f"*{name}*: Market not open yet")

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_orb: %s", e)
        await send(f"❌ ORB error: `{e}`")


async def cmd_indianstats() -> None:
    try:
        from engines.indian.tracker import get_performance

        perf = get_performance()

        if not perf or perf.get("total", 0) == 0:
            await send(
                "📊 *Indian Market Stats*\n\n"
                "No closed signals yet.\n"
                "_Stats will appear after first signal closes._"
            )
            return

        lines = [
            f"📊 *Indian Market Performance*\n",
            f"Total signals: `{perf['total']}`",
            f"Wins:          `{perf['wins']}`",
            f"Losses:        `{perf['losses']}`",
            f"Timeouts:      `{perf.get('timeouts', 0)}`",
            f"Win rate:      `{perf['win_rate']}%`",
            f"Total pts:     `{perf['total_pts']:+.2f}`",
            f"Avg win:       `{perf['avg_win_pts']:+.2f} pts`",
            f"Avg loss:      `{perf['avg_loss_pts']:+.2f} pts`",
            f"Profit factor: `{perf['profit_factor']}`",
        ]

        by_day = perf.get("by_day", {})
        if by_day:
            lines.append(f"\n*By Day:*")
            for day, stats in by_day.items():
                lines.append(
                    f"  {day}: `{stats['win_rate']}%` WR "
                    f"({stats['total']} signals)"
                )

        by_dir = perf.get("by_direction", {})
        if by_dir:
            lines.append(f"\n*By Direction:*")
            for direction, stats in by_dir.items():
                lines.append(
                    f"  {direction}: `{stats['win_rate']}%` WR "
                    f"({stats['total']} signals) "
                    f"`{stats['pnl_pts']:+.2f} pts`"
                )

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_indianstats: %s", e)
        await send(f"❌ Stats error: `{e}`")