import logging
from datetime import date, datetime, timezone, timedelta
from alerts.telegram.client import send
from config import cfg

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> str:
    return datetime.now(IST).strftime("%I:%M %p IST")


def _now_ist_full() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %I:%M %p IST")


def _grade_emoji(grade: str) -> str:
    return {"A+": "🏆", "A": "⭐", "B": "👀"}.get(grade, "📊")


def _dir_emoji(direction: str) -> str:
    return "📈" if direction == "LONG" else "📉"


async def cmd_pnl() -> None:
    from alerts.scanner import get_db_stats

    stats    = get_db_stats()
    total    = stats.get("total_pnl", 0)
    closed   = stats.get("closed",   0)
    wins     = stats.get("wins",     0)
    losses   = stats.get("losses",   0)
    win_rate = stats.get("win_rate",  0)

    pnl_emoji = "💚" if total >= 0 else "🔴"
    pnl_sign  = "+" if total >= 0 else ""

    await send(
        f"💰 *PnL Report*\n"
        f"🕐 `{_now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_emoji} Total PnL:  `{pnl_sign}${total:.2f}`\n"
        f"🎯 Win Rate:  `{win_rate}%`\n"
        f"📊 Closed:    `{closed}` trades\n"
        f"✅ Wins:      `{wins}`\n"
        f"❌ Losses:    `{losses}`\n"
    )


async def cmd_daily() -> None:
    from database import SessionLocal, Trade as TradeModel
    from alerts.scanner import get_db_stats

    stats        = get_db_stats()
    today_pnl    = 0.0
    today_trades = 0
    today_wins   = 0
    today_losses = 0

    try:
        today_start = datetime(
            date.today().year,
            date.today().month,
            date.today().day,
            tzinfo=timezone.utc
        )
        with SessionLocal() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.closed_at >= today_start,
                TradeModel.outcome.in_(["win", "loss"])
            ).all()
            today_pnl    = sum(float(t.net_pnl or t.pnl or 0) for t in trades)
            today_trades = len(trades)
            today_wins   = sum(1 for t in trades if t.outcome == "win")
            today_losses = sum(1 for t in trades if t.outcome == "loss")
    except Exception:
        pass

    pnl_emoji = "💚" if today_pnl >= 0 else "🔴"
    pnl_sign  = "+" if today_pnl >= 0 else ""
    all_pnl   = stats.get("total_pnl", 0)
    all_sign  = "+" if all_pnl >= 0 else ""

    await send(
        f"📅 *Daily Summary*\n"
        f"🕐 `{_now_ist_full()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Today:*\n"
        f"📊 Trades:    `{today_trades}`\n"
        f"✅ Wins:      `{today_wins}`\n"
        f"❌ Losses:    `{today_losses}`\n"
        f"{pnl_emoji} PnL:       `{pnl_sign}${today_pnl:.4f}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*All Time:*\n"
        f"📊 Signals:   `{stats.get('total', 0)}`\n"
        f"📈 Closed:    `{stats.get('closed', 0)}`\n"
        f"🎯 Win Rate:  `{stats.get('win_rate', 0)}%`\n"
        f"💰 PnL:       `{all_sign}${all_pnl:.2f}`\n"
    )


async def cmd_stats() -> None:
    from alerts.scanner import get_db_stats

    stats = get_db_stats()
    if not stats:
        await send("📊 No stats yet.")
        return

    bg       = stats.get("by_grade", {})
    total    = stats.get("total_pnl", 0)
    pnl_sign = "+" if total >= 0 else ""
    pnl_emoji= "💚" if total >= 0 else "🔴"

    def grade_line(grade: str) -> str:
        g    = bg.get(grade, {})
        tot  = g.get("total",    0)
        wr   = g.get("win_rate", 0)
        pnl  = g.get("total_pnl", 0)
        sign = "+" if pnl >= 0 else ""
        emoji= _grade_emoji(grade)
        if tot == 0:
            return f"{emoji} `{grade}`:  No trades yet"
        return f"{emoji} `{grade}`:  `{tot}` trades  `{wr}%` WR  `{sign}${pnl:.2f}`"

    await send(
        f"📊 *All Time Stats*\n"
        f"🕐 `{_now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📈 Total:     `{stats.get('total',   0)}` signals\n"
        f"✅ Closed:    `{stats.get('closed',  0)}`\n"
        f"⏳ Pending:   `{stats.get('pending', 0)}`\n"
        f"🎯 Win Rate:  `{stats.get('win_rate', 0)}%`\n"
        f"{pnl_emoji} PnL:       `{pnl_sign}${total:.2f}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*By Grade:*\n"
        f"{grade_line('A+')}\n"
        f"{grade_line('A')}\n"
        f"{grade_line('B')}\n"
    )


async def cmd_grade() -> None:
    from alerts.scanner import get_db_stats

    bg = get_db_stats().get("by_grade", {})

    def grade_block(grade: str) -> str:
        g     = bg.get(grade, {})
        tot   = g.get("total",    0)
        wins  = g.get("wins",     0)
        losses= g.get("losses",   0)
        wr    = g.get("win_rate", 0)
        pnl   = g.get("total_pnl", 0)
        sign  = "+" if pnl >= 0 else ""
        emoji = _grade_emoji(grade)
        if tot == 0:
            return f"{emoji} *Grade {grade}*\nNo trades yet\n"
        return (
            f"{emoji} *Grade {grade}*\n"
            f"📊 Trades:   `{tot}`\n"
            f"✅ Wins:     `{wins}`\n"
            f"❌ Losses:   `{losses}`\n"
            f"🎯 Win Rate: `{wr}%`\n"
            f"💰 PnL:      `{sign}${pnl:.2f}`\n"
        )

    await send(
        f"🏆 *Grade Accuracy*\n"
        f"🕐 `{_now_ist()}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{grade_block('A+')}\n"
        f"{grade_block('A')}\n"
        f"{grade_block('B')}\n"
        f"_Minimum 50 trades for reliable data_"
    )


async def cmd_history() -> None:
    from database import get_session, Trade as TradeModel

    try:
        with get_session() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(5).all()

        if not trades:
            await send("📜 No closed trades yet.")
            return

        lines = [
            f"📜 *Last 5 Trades*\n"
            f"🕐 `{_now_ist()}`\n"
        ]

        for t in trades:
            pnl       = float(t.net_pnl or t.pnl or 0)
            pnl_str   = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"
            pnl_emoji = "💚" if pnl >= 0 else "🔴"
            outcome   = "✅" if t.outcome == "win" else "❌"
            d_emoji   = _dir_emoji(t.direction)
            g_emoji   = _grade_emoji(t.grade or "--")
            ts_ist    = t.opened_at.astimezone(IST).strftime("%d %b %I:%M %p") if t.opened_at else "--"

            lines.append(
                f"\n{outcome} {d_emoji} *{t.coin}* {g_emoji} `{t.grade}`\n"
                f"{pnl_emoji} `{pnl_str}`  ·  _{ts_ist} IST_"
            )

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_history error: %s", e)
        await send("❌ Could not fetch history.")


async def cmd_performance() -> None:
    try:
        from ml.performance_tracker import (
            get_overall_stats, get_stats_by_session,
            get_recent_trend,
        )

        overall  = get_overall_stats(min_trades=1)
        sessions = get_stats_by_session(min_trades=3)
        trend    = get_recent_trend(window=20)

        if overall.get("error"):
            await send(f"📊 *Performance*\n\n{overall['error']}")
            return

        total    = overall.get("total",          0)
        wr       = overall.get("win_rate",        0)
        pnl      = overall.get("total_pnl",       0)
        pf       = overall.get("profit_factor",   0)
        dd       = overall.get("max_drawdown",    0)
        t_trend  = trend.get("trend",             "unknown")
        r_wr     = trend.get("recent_win_rate",   0)

        pnl_sign  = "+" if pnl >= 0 else ""
        pnl_emoji = "💚" if pnl >= 0 else "🔴"

        trend_emoji = (
            "📈" if t_trend == "improving"  else
            "📉" if t_trend == "degrading"  else
            "➡️"
        )

        lines = [
            f"📊 *Performance Report*\n"
            f"🕐 `{_now_ist()}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*Overall:*\n"
            f"📊 Trades:    `{total}`\n"
            f"🎯 Win Rate:  `{wr:.1f}%`\n"
            f"{pnl_emoji} PnL:       `{pnl_sign}${pnl:.2f}`\n"
            f"📈 PF:        `{pf}`\n"
            f"📉 Max DD:    `{dd:.1f}%`\n\n"
            f"{trend_emoji} *Trend:* `{t_trend}` (last 20: `{r_wr:.1f}%`)\n"
        ]

        if sessions:
            lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━\n*By Session:*")
            for session, s in sessions.items():
                swr = s.get("win_rate", 0)
                st  = s.get("total",    0)
                lines.append(f"  ⏰ `{session}`: `{swr:.1f}%` WR ({st} trades)")

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_performance: %s", e)
        await send("❌ Could not fetch performance data.")