import logging
from datetime import date, datetime, timezone
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist, now_ist_full, get_stats, grade_block
from config import cfg

log = logging.getLogger(__name__)


async def cmd_pnl() -> None:
    stats = get_stats()
    await send(
        f"💰 *PnL Report*\n\n"
        f"Total:   `{stats.get('closed', 0) + stats.get('pending', 0)}` signals\n"
        f"Wins:    `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"WR:      `{stats.get('win_rate', 0)}%`\n"
        f"PnL:     `${stats.get('total_pnl', 0)}`\n"
    )


async def cmd_daily() -> None:
    from database import SessionLocal, Signal as SignalModel
    stats        = get_stats()
    today_pnl    = 0.0
    today_trades = 0
    try:
        with SessionLocal() as db:
            sigs = db.query(SignalModel).filter(
                SignalModel.timestamp >= date.today().isoformat(),
                SignalModel.outcome.in_(["win", "loss"])
            ).all()
            today_pnl    = sum(float(s.pnl or 0) for s in sigs)
            today_trades = len(sigs)
    except Exception:
        pass
    pnl_str = f"+${today_pnl:.4f}" if today_pnl >= 0 else f"-${abs(today_pnl):.4f}"
    await send(
        f"📅 *Daily Summary*\n_{now_ist_full()}_\n\n"
        f"Today: `{today_trades}` trades · `{pnl_str}`\n\n"
        f"All-time: `{stats.get('total', 0)}` signals · `{stats.get('closed', 0)}` closed\n"
        f"Wins: `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"WR: `{stats.get('win_rate', 0)}%` · PnL: `${stats.get('total_pnl', 0)}`\n"
    )


async def cmd_stats() -> None:
    stats = get_stats()
    if not stats:
        await send("📊 No stats yet.")
        return
    bg = stats.get("by_grade", {})
    await send(
        f"📊 *All Time Stats*\n_{now_ist()}_\n\n"
        f"Total: `{stats.get('total', 0)}` · Closed: `{stats.get('closed', 0)}`\n"
        f"Wins: `{stats.get('wins', 0)}` · Losses: `{stats.get('losses', 0)}`\n"
        f"WR: `{stats.get('win_rate', 0)}%` · PnL: `${stats.get('total_pnl', 0)}`\n\n"
        f"{grade_block('A+', bg.get('A+', {}))}\n"
        f"{grade_block('A',  bg.get('A',  {}))}\n"
        f"{grade_block('B',  bg.get('B',  {}))}"
    )


async def cmd_grade() -> None:
    bg = get_stats().get("by_grade", {})
    await send(
        f"🏆 *Grade Accuracy*\n\n"
        f"{grade_block('A+', bg.get('A+', {}))}\n"
        f"{grade_block('A',  bg.get('A',  {}))}\n"
        f"{grade_block('B',  bg.get('B',  {}))}\n"
        f"_Minimum 50 trades for reliable data_"
    )


async def cmd_history() -> None:
    from database import get_session, Signal as SignalModel
    from datetime import timezone as tz
    IST = timezone(timezone.utc.utcoffset(None) or __import__('datetime').timedelta(hours=5, minutes=30))
    try:
        from datetime import timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        with get_session() as db:
            signals = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"])
            ).order_by(SignalModel.timestamp.desc()).limit(5).all()
        if not signals:
            await send("📜 No closed signals yet.")
            return
        lines = [f"📜 *Last 5 Signals*\n_{now_ist()}_\n"]
        for s in signals:
            pnl_str = f"+${s.pnl:.4f}" if (s.pnl or 0) >= 0 else f"-${abs(s.pnl or 0):.4f}"
            ts_ist  = s.timestamp.astimezone(IST).strftime("%d %b %I:%M %p") if s.timestamp else "--"
            lines.append(
                f"{'✅' if s.outcome == 'win' else '❌'} "
                f"{'📈' if s.direction == 'LONG' else '📉'} "
                f"`{s.coin}` {s.direction} Grade `{s.grade}` — `{pnl_str}`\n_{ts_ist} IST_\n"
            )
        await send("\n".join(lines))
    except Exception as e:
        log.error("cmd_history error: %s", e)
        await send("❌ Could not fetch history.")


async def cmd_performance() -> None:
    try:
        from ml.performance_tracker import (
            get_overall_stats, get_stats_by_session,
            get_stats_by_version, get_recent_trend,
        )
        overall  = get_overall_stats(min_trades=1)
        sessions = get_stats_by_session(min_trades=3)
        versions = get_stats_by_version()
        trend    = get_recent_trend(window=20)

        if overall.get("error"):
            await send(f"📊 *Performance*\n\n{overall['error']}")
            return

        lines = [
            f"📊 *Performance Report*\n_{now_ist()}_\n",
            f"*Overall:*",
            f"Trades: `{overall.get('total', 0)}` · WR: `{overall.get('win_rate', 0):.1f}%`",
            f"PnL: `${overall.get('total_pnl', 0):.2f}` · PF: `{overall.get('profit_factor', 0)}`",
            f"Max DD: `{overall.get('max_drawdown', 0):.1f}%`",
            f"",
        ]

        t_trend     = trend.get("trend", "unknown")
        trend_emoji = "📈" if t_trend == "improving" else "📉" if t_trend == "degrading" else "➡️"
        lines.append(
            f"{trend_emoji} Recent trend: `{t_trend}` "
            f"(last 20 trades: `{trend.get('recent_win_rate', 0):.1f}%`)\n"
        )

        if sessions:
            lines.append(f"*By Session:*")
            for session, stats in sessions.items():
                lines.append(
                    f"  {session}: `{stats.get('win_rate', 0):.1f}%` WR "
                    f"({stats.get('total', 0)} trades)"
                )
            lines.append("")

        if len(versions) > 1:
            lines.append(f"*By Version:*")
            for v in versions[-3:]:
                lines.append(
                    f"  `{v.get('version', '--')}`: "
                    f"`{v.get('win_rate', 0):.1f}%` WR "
                    f"({v.get('total', 0)} trades)"
                )

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_performance: %s", e)
        await send("❌ Could not fetch performance data.")