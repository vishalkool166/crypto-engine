import logging
from datetime import datetime, timezone, timedelta
from alerts.telegram.client import send

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

RUPEES_PER_POINT = 30


def _now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


async def cmd_india() -> None:
    try:
        from engines.indian.data import is_market_open, is_orb_ready
        from engines.indian.scanner import get_orb_levels, get_today_signals
        from engines.indian.instruments import get_instruments
        from engines.indian.strategy import MIN_DAY_RANGE, MIN_ORB_SIZE, MAX_ORB_SIZE
        from engines.indian.scanner import _get_day_range_so_far
        from config import cfg

        now         = datetime.now(IST)
        market_open = is_market_open()
        orb_ready   = is_orb_ready()
        instruments = get_instruments()
        signals     = get_today_signals()

        status_emoji = "🟢" if market_open else "🔴"
        status_text  = "Open" if market_open else "Closed"

        lines = [
            f"🇮🇳 *Indian Market*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{status_emoji} Market:   `{status_text}`\n"
            f"{'✅' if orb_ready else '⏳'} ORB:      `{'Ready' if orb_ready else 'Not ready'}`\n"
        ]

        for name in cfg.INDIAN_INSTRUMENTS:
            inst = instruments.get(name)
            orb  = get_orb_levels(name)

            lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━\n*{name}*")

            if orb:
                orb_size = orb.get("size", 0)
                orb_ok   = MIN_ORB_SIZE <= orb_size <= MAX_ORB_SIZE
                orb_emoji= "✅" if orb_ok else "❌"

                lines.append(
                    f"📊 ORB High:  `{orb['high']:.2f}`\n"
                    f"📊 ORB Low:   `{orb['low']:.2f}`\n"
                    f"{orb_emoji} ORB Range: `{orb_size:.0f} pts`"
                )

                if inst and market_open:
                    try:
                        day_range = _get_day_range_so_far(inst["token"])
                        dr_emoji  = "✅" if day_range >= MIN_DAY_RANGE else "❌"
                        lines.append(f"{dr_emoji} Day Range: `{day_range:.0f} pts` (need {MIN_DAY_RANGE}+)")
                    except Exception:
                        pass
            else:
                lines.append("⏳ ORB not set yet — available after 9:35am IST")

        if signals:
            lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━\n*Today's Signals — {len(signals)}*")
            for s in signals:
                direction = s.get("direction", "--")
                entry     = s.get("entry",     0)
                sl        = s.get("sl",        0)
                tp1       = s.get("tp1",       0)
                rr1       = s.get("rr1",       0)
                d_emoji   = "📈" if direction == "LONG" else "📉"
                outcome   = s.get("outcome",   "pending")
                out_emoji = "✅" if outcome == "win" else "❌" if outcome == "loss" else "⏱️" if outcome == "timeout" else "⏳"

                lines.append(
                    f"{d_emoji} `{direction}`  {out_emoji} `{outcome.upper()}`\n"
                    f"   🎯 `{entry:.2f}`  🛑 `{sl:.2f}`  ✅ `{tp1:.2f}` ({rr1:.1f}R)"
                )
        else:
            if orb_ready:
                lines.append(
                    f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⏳ No signal yet — watching from 10am IST"
                )
            else:
                lines.append(
                    f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"😴 No signals today"
                )

        lines.append(
            f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Strategy: 10am-1pm · No SHORT before 11am_\n"
            f"_SL=150pts · TP=300pts · 1:2 RR_"
        )

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_india: %s", e)
        await send(f"❌ Indian market error: `{e}`")


async def cmd_orb() -> None:
    try:
        from engines.indian.scanner import get_orb_levels, setup_orb
        from engines.indian.instruments import get_instruments
        from engines.indian.data import is_orb_ready
        from engines.indian.strategy import MIN_ORB_SIZE, MAX_ORB_SIZE
        from config import cfg

        instruments = get_instruments()

        if not instruments:
            await send("⚠️ No Indian instruments configured.")
            return

        lines = [
            f"📊 *Opening Range Levels*\n"
            f"🕐 `{_now_ist()}`\n"
        ]

        for name in cfg.INDIAN_INSTRUMENTS:
            orb = get_orb_levels(name)

            if not orb and is_orb_ready():
                result = setup_orb()
                if result and name in result:
                    orb = result[name]

            lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━\n*{name}*")

            if orb:
                orb_size  = orb.get("size", 0)
                orb_ok    = MIN_ORB_SIZE <= orb_size <= MAX_ORB_SIZE
                orb_emoji = "✅" if orb_ok else "❌"
                reason    = ""
                if orb_size < MIN_ORB_SIZE:
                    reason = f" — too tight (min {MIN_ORB_SIZE})"
                elif orb_size > MAX_ORB_SIZE:
                    reason = f" — too wide (max {MAX_ORB_SIZE})"

                lines.append(
                    f"📈 High:   `{orb['high']:.2f}`\n"
                    f"📉 Low:    `{orb['low']:.2f}`\n"
                    f"{orb_emoji} Range:  `{orb_size:.0f} pts`{reason}\n"
                    f"📅 Date:   `{orb.get('date', '--')}`\n\n"
                    f"🎯 Long entry above:  `{orb['high'] + 10:.2f}`\n"
                    f"📉 Short entry below: `{orb['low']  - 10:.2f}`"
                )
            else:
                lines.append("⏳ Not available yet — after 9:35am IST")

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
                f"📊 *Indian Market Stats*\n\n"
                f"😴 No closed signals yet.\n"
                f"_Stats appear after first signal closes._"
            )
            return

        total    = perf.get("total",         0)
        wins     = perf.get("wins",          0)
        losses   = perf.get("losses",        0)
        timeouts = perf.get("timeouts",      0)
        win_rate = perf.get("win_rate",      0)
        total_pts= perf.get("total_pts",     0)
        avg_win  = perf.get("avg_win_pts",   0)
        avg_loss = perf.get("avg_loss_pts",  0)
        pf       = perf.get("profit_factor", 0)

        total_rupees = round(total_pts * RUPEES_PER_POINT)
        pnl_emoji    = "💚" if total_pts >= 0 else "🔴"
        pnl_sign     = "+" if total_pts >= 0 else ""

        lines = [
            f"📊 *Indian Market Performance*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 Total:     `{total}` signals\n"
            f"✅ Wins:      `{wins}`\n"
            f"❌ Losses:    `{losses}`\n"
            f"⏱️ Timeouts:  `{timeouts}`\n"
            f"🎯 Win Rate:  `{win_rate}%`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} Total:     `{pnl_sign}{total_pts:.0f} pts`\n"
            f"💰 Rupees:   `{pnl_sign}₹{abs(total_rupees):,}` / lot\n"
            f"✅ Avg Win:  `+{avg_win:.0f} pts`  (`+₹{round(avg_win * RUPEES_PER_POINT):,}`)\n"
            f"❌ Avg Loss: `{avg_loss:.0f} pts`  (`₹{round(avg_loss * RUPEES_PER_POINT):,}`)\n"
            f"📈 PF:       `{pf}`\n"
        ]

        by_dir = perf.get("by_direction", {})
        if by_dir:
            lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━\n*By Direction:*")
            for direction, data in by_dir.items():
                d_emoji  = "📈" if direction == "LONG" else "📉"
                dwr      = data.get("win_rate", 0)
                dtotal   = data.get("total",    0)
                dpnl     = data.get("pnl_pts",  0)
                drupees  = round(dpnl * RUPEES_PER_POINT)
                dsign    = "+" if dpnl >= 0 else ""
                lines.append(
                    f"{d_emoji} `{direction}`: `{dwr}%` WR  `{dtotal}` signals\n"
                    f"   `{dsign}{dpnl:.0f} pts`  (`{dsign}₹{abs(drupees):,}`)"
                )

        by_day = perf.get("by_day", {})
        if by_day:
            lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━\n*By Day:*")
            DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            for day in DAY_NAMES:
                if day not in by_day:
                    continue
                data = by_day[day]
                dwr  = data.get("win_rate", 0)
                dtot = data.get("total",    0)
                wr_emoji = "✅" if dwr >= 50 else "⚠️" if dwr >= 35 else "❌"
                lines.append(f"{wr_emoji} `{day[:3]}`: `{dwr}%` WR  ({dtot} signals)")

        lines.append(
            f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_1 lot = {RUPEES_PER_POINT} rupees per point_\n"
            f"_Paper tracking only_"
        )

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_indianstats: %s", e)
        await send(f"❌ Stats error: `{e}`")