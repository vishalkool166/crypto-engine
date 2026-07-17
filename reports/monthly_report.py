import logging
from datetime import datetime, timezone, timedelta, date

log = logging.getLogger(__name__)


def generate_monthly_report(year: int = None, month: int = None) -> dict:
    now = datetime.now(timezone.utc)
    if not year:
        year = now.year
    if not month:
        month = now.month

    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            trades = db.query(TradeModel).filter(
                TradeModel.closed_at >= start,
                TradeModel.closed_at <  end,
                TradeModel.outcome.in_(["win", "loss"]),
            ).order_by(TradeModel.opened_at.asc()).all()

        if not trades:
            return {
                "period":  f"{year}-{month:02d}",
                "error":   "No closed trades this month",
                "trades":  0,
            }

        wins   = [t for t in trades if t.outcome == "win"]
        losses = [t for t in trades if t.outcome == "loss"]
        total  = len(trades)

        pnls      = [float(t.binance_net_pnl or t.net_pnl or t.pnl or 0) for t in trades]
        total_pnl = round(sum(pnls), 4)
        win_rate  = round(len(wins) / total * 100, 1) if total > 0 else 0

        gross_p = sum(p for p in pnls if p > 0)
        gross_l = abs(sum(p for p in pnls if p < 0))
        pf      = round(gross_p / gross_l, 2) if gross_l > 0 else 0

        avg_win  = round(sum(float(t.binance_net_pnl or t.net_pnl or t.pnl or 0) for t in wins)   / len(wins),   4) if wins   else 0
        avg_loss = round(sum(float(t.binance_net_pnl or t.net_pnl or t.pnl or 0) for t in losses) / len(losses), 4) if losses else 0

        expectancy = round((win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss), 4)

        durations = [float(t.duration_hours or 0) for t in trades if t.duration_hours]
        avg_hold  = round(sum(durations) / len(durations), 1) if durations else 0

        total_fee  = round(sum(float(t.total_commission  or 0) for t in trades), 4)
        total_fund = round(sum(float(t.funding_fees_paid or 0) for t in trades), 4)

        by_regime  = _breakdown(trades, "regime_at_entry")
        by_session = _breakdown(trades, "session_at_entry")
        by_grade   = _breakdown(trades, "grade")
        by_day     = _breakdown_by_day(trades)

        best_trade  = max(pnls)
        worst_trade = min(pnls)

        best_t  = next((t for t in trades if float(t.binance_net_pnl or t.net_pnl or t.pnl or 0) == best_trade),  None)
        worst_t = next((t for t in trades if float(t.binance_net_pnl or t.net_pnl or t.pnl or 0) == worst_trade), None)

        equity   = 0.0
        peak     = 0.0
        max_dd   = 0.0
        for t in trades:
            equity += float(t.binance_net_pnl or t.net_pnl or t.pnl or 0)
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        best_regime  = max(by_regime,  key=lambda x: by_regime[x]["win_rate"])  if by_regime  else "--"
        worst_regime = min(by_regime,  key=lambda x: by_regime[x]["win_rate"])  if by_regime  else "--"
        best_session = max(by_session, key=lambda x: by_session[x]["win_rate"]) if by_session else "--"

        from data.rejection_stats import get_daily_stats
        daily_stats = get_daily_stats(days=31)
        month_rejections = {}
        for day_data in daily_stats:
            day_str = day_data.get("date", "")
            if day_str.startswith(f"{year}-{month:02d}"):
                for reason, count in day_data.get("by_reason", {}).items():
                    month_rejections[reason] = month_rejections.get(reason, 0) + count

        top_rejection = max(month_rejections, key=month_rejections.get) if month_rejections else "--"

        tp1_hits = sum(1 for t in trades if t.tp1_hit)

        return {
            "period":        f"{year}-{month:02d}",
            "period_label":  start.strftime("%B %Y"),
            "trades":        total,
            "wins":          len(wins),
            "losses":        len(losses),
            "win_rate":      win_rate,
            "total_pnl":     total_pnl,
            "total_pnl_pos": total_pnl >= 0,
            "gross_profit":  round(gross_p,  4),
            "gross_loss":    round(gross_l,  4),
            "profit_factor": pf,
            "avg_win":       avg_win,
            "avg_loss":      avg_loss,
            "expectancy":    expectancy,
            "avg_hold_hours":avg_hold,
            "max_drawdown":  round(max_dd, 2),
            "total_fees":    total_fee,
            "total_funding": total_fund,
            "best_trade":    round(best_trade,  4),
            "worst_trade":   round(worst_trade, 4),
            "best_coin":     best_t.coin  if best_t  else "--",
            "worst_coin":    worst_t.coin if worst_t else "--",
            "tp1_hit_rate":  round(tp1_hits / total * 100, 1) if total > 0 else 0,
            "best_regime":   best_regime,
            "worst_regime":  worst_regime,
            "best_session":  best_session,
            "top_rejection": top_rejection,
            "by_regime":     by_regime,
            "by_session":    by_session,
            "by_grade":      by_grade,
            "by_day":        by_day,
            "generated_at":  datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error("generate_monthly_report: %s", e)
        return {"error": str(e)}


def _breakdown(trades: list, field: str) -> dict:
    groups = {}
    for t in trades:
        val = getattr(t, field, None) or "Unknown"
        if val not in groups:
            groups[val] = {"wins": 0, "losses": 0, "pnl": 0.0}
        pnl = float(getattr(t, "binance_net_pnl", None) or getattr(t, "net_pnl", None) or getattr(t, "pnl", None) or 0)
        groups[val]["pnl"] += pnl
        if t.outcome == "win":
            groups[val]["wins"] += 1
        else:
            groups[val]["losses"] += 1

    result = {}
    for val, data in groups.items():
        total = data["wins"] + data["losses"]
        result[val] = {
            "total":    total,
            "wins":     data["wins"],
            "losses":   data["losses"],
            "win_rate": round(data["wins"] / total * 100, 1) if total > 0 else 0,
            "pnl":      round(data["pnl"], 4),
        }
    return result


def _breakdown_by_day(trades: list) -> dict:
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    groups = {}
    for t in trades:
        if not t.opened_at:
            continue
        day = days[t.opened_at.weekday()]
        if day not in groups:
            groups[day] = {"wins": 0, "losses": 0, "pnl": 0.0}
        pnl = float(getattr(t, "binance_net_pnl", None) or getattr(t, "net_pnl", None) or getattr(t, "pnl", None) or 0)
        groups[day]["pnl"] += pnl
        if t.outcome == "win":
            groups[day]["wins"] += 1
        else:
            groups[day]["losses"] += 1

    result = {}
    for day, data in groups.items():
        total = data["wins"] + data["losses"]
        result[day] = {
            "total":    total,
            "wins":     data["wins"],
            "losses":   data["losses"],
            "win_rate": round(data["wins"] / total * 100, 1) if total > 0 else 0,
            "pnl":      round(data["pnl"], 4),
        }
    return result


async def send_monthly_report_telegram(year: int = None, month: int = None) -> None:
    try:
        from alerts.telegram import send
        report = generate_monthly_report(year, month)

        if report.get("error"):
            await send(f"📊 *Monthly Report*\n\n{report['error']}")
            return

        pnl_sign = "+" if report["total_pnl"] >= 0 else ""
        emoji    = "✅" if report["total_pnl"] >= 0 else "❌"

        lines = [
            f"📊 *Monthly Report — {report['period_label']}*\n",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"Trades:         `{report['trades']}`",
            f"Win Rate:       `{report['win_rate']}%`",
            f"Total PnL:      `{pnl_sign}${report['total_pnl']}` {emoji}",
            f"Profit Factor:  `{report['profit_factor']}`",
            f"Expectancy:     `${report['expectancy']}`",
            f"Max Drawdown:   `{report['max_drawdown']}%`",
            f"",
            f"Avg Hold:       `{report['avg_hold_hours']}h`",
            f"TP1 Hit Rate:   `{report['tp1_hit_rate']}%`",
            f"Fees Paid:      `${report['total_fees']}`",
            f"",
            f"Best Trade:     `+${report['best_trade']}` ({report['best_coin']})",
            f"Worst Trade:    `${report['worst_trade']}` ({report['worst_coin']})",
            f"",
            f"Best Regime:    `{report['best_regime']}`",
            f"Worst Regime:   `{report['worst_regime']}`",
            f"Best Session:   `{report['best_session']}`",
            f"Top Rejection:  `{report['top_rejection']}`",
        ]

        by_grade = report.get("by_grade", {})
        if by_grade:
            lines.append(f"")
            lines.append(f"*By Grade:*")
            for grade in ["A+", "A", "B"]:
                if grade in by_grade:
                    g = by_grade[grade]
                    lines.append(
                        f"  {grade}: `{g['win_rate']}% WR` "
                        f"`{g['total']} trades` "
                        f"`${g['pnl']}`"
                    )

        await send("\n".join(lines))

    except Exception as e:
        log.error("send_monthly_report_telegram: %s", e)


def get_last_n_months(n: int = 3) -> list:
    results = []
    now     = datetime.now(timezone.utc)
    for i in range(n):
        month = now.month - i
        year  = now.year
        while month <= 0:
            month += 12
            year  -= 1
        results.append(generate_monthly_report(year, month))
    return results