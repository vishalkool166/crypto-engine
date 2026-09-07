import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


def run_filter_analysis() -> dict:
    try:
        from data.rejection_stats import get_total_stats, get_daily_stats, get_weekly_stats
        from engines.decision_trace import get_recent_traces, get_rejection_summary
        from database import SessionLocal, Signal as SignalModel, Trade as TradeModel

        total_stats   = get_total_stats()
        weekly_stats  = get_weekly_stats()
        daily_stats   = get_daily_stats(days=30)
        traces        = get_recent_traces(limit=500)
        trace_summary = get_rejection_summary(traces)

        with SessionLocal() as db:
            closed_trades = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).all()

        filter_performance  = _analyze_filter_performance(closed_trades)
        correlation_matrix  = _analyze_filter_correlation(traces)
        bottleneck_analysis = _identify_bottlenecks(total_stats)
        trend_analysis      = _analyze_rejection_trends(daily_stats)

        return {
            "total_stats":          total_stats,
            "weekly_stats":         weekly_stats,
            "filter_performance":   filter_performance,
            "correlation_matrix":   correlation_matrix,
            "bottleneck_analysis":  bottleneck_analysis,
            "trend_analysis":       trend_analysis,
            "trace_summary":        trace_summary,
            "recommendations":      _generate_recommendations(
                bottleneck_analysis,
                filter_performance,
                total_stats,
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error("run_filter_analysis: %s", e)
        return {"error": str(e)}


def _analyze_filter_performance(trades: list) -> dict:
    if not trades:
        return {}

    try:
        from database import SessionLocal, Signal as SignalModel

        with SessionLocal() as db:
            signals = db.query(SignalModel).filter(
                SignalModel.outcome.in_(["win", "loss"])
            ).all()

        if not signals:
            return {}

        grade_buckets = {"A+": [], "A": [], "B": []}
        for s in signals:
            if s.grade in grade_buckets:
                grade_buckets[s.grade].append(s)

        def bucket_stats(bucket: list) -> dict:
            if not bucket:
                return {"total": 0, "win_rate": 0, "pnl": 0}
            wins = sum(1 for s in bucket if s.outcome == "win")
            pnl  = round(sum(float(s.pnl or 0) for s in bucket), 4)
            return {
                "total":    len(bucket),
                "wins":     wins,
                "win_rate": round(wins / len(bucket) * 100, 1),
                "pnl":      pnl,
            }

        return {
            "grade": {
                "A+": bucket_stats(grade_buckets["A+"]),
                "A":  bucket_stats(grade_buckets["A"]),
                "B":  bucket_stats(grade_buckets["B"]),
            },
        }

    except Exception as e:
        log.error("_analyze_filter_performance: %s", e)
        return {}


def _analyze_filter_correlation(traces: list) -> dict:
    if not traces:
        return {}

    try:
        co_occurrence = {}
        filter_counts = {}

        for trace in traces:
            steps  = trace.get("steps", [])
            failed = [s["name"] for s in steps if s.get("result") == "FAIL"]

            for f in failed:
                filter_counts[f] = filter_counts.get(f, 0) + 1

            for i, f1 in enumerate(failed):
                for f2 in failed[i + 1:]:
                    key = tuple(sorted([f1, f2]))
                    co_occurrence[key] = co_occurrence.get(key, 0) + 1

        total  = len(traces)
        result = []

        for (f1, f2), count in sorted(co_occurrence.items(), key=lambda x: x[1], reverse=True)[:10]:
            f1_count    = filter_counts.get(f1, 1)
            f2_count    = filter_counts.get(f2, 1)
            correlation = round(count / min(f1_count, f2_count), 3) if min(f1_count, f2_count) > 0 else 0
            result.append({
                "filter_1":    f1,
                "filter_2":    f2,
                "co_failures": count,
                "correlation": correlation,
                "pct_of_scans":round(count / total * 100, 1) if total > 0 else 0,
                "redundant":   correlation > 0.7,
            })

        return {
            "pairs":         result,
            "filter_counts": dict(sorted(filter_counts.items(), key=lambda x: x[1], reverse=True)),
            "total_traces":  total,
        }

    except Exception as e:
        log.error("_analyze_filter_correlation: %s", e)
        return {}


def _identify_bottlenecks(total_stats: dict) -> list:
    by_reason   = total_stats.get("by_reason", {})
    total_scans = total_stats.get("total_scans", 1)
    bottlenecks = []

    for reason, data in by_reason.items():
        pct   = data.get("pct",   0)
        count = data.get("count", 0)

        severity = "low"
        if pct > 40:
            severity = "critical"
        elif pct > 25:
            severity = "high"
        elif pct > 10:
            severity = "medium"

        action = _get_bottleneck_action(reason, pct)

        bottlenecks.append({
            "filter":   reason,
            "count":    count,
            "pct":      pct,
            "severity": severity,
            "action":   action,
        })

    bottlenecks.sort(key=lambda x: x["pct"], reverse=True)
    return bottlenecks


def _get_bottleneck_action(reason: str, pct: float) -> str:
    actions = {
        # New momentum engine filters
        "adx_too_low":        "ADX below threshold — market not trending enough. Normal in ranging markets.",
        "ema_neutral":        "Price between EMAs — no clear directional bias. Wait for trend to establish.",
        "grade_f":            "Score below 50 — weak setup. ADX, RSI, or volume not aligned.",
        "volatile_regime":    "ATR too high — market too volatile for safe entries. Wait for calm.",
        "risk_invalid":       "SL/TP geometry invalid — swing level too close or too far from entry.",
        "risk_sl_tight":      "Stop loss too tight — less than 0.3% from entry. Widen SL placement.",
        "risk_sl_wide":       "Stop loss too wide — more than 5% from entry. Tighten SL placement.",
        "risk_rr_low":        "Risk/reward ratio below minimum — TP target not far enough from entry.",
        "missing_indicators": "Insufficient candle data for indicator calculation. Run /backfill.",
        "not_near_ema50":     "Price too far from EMA50 — entry timing not optimal.",
        "no_bullish_candle":  "No bullish confirmation candle for LONG setup.",
        "no_bearish_candle":  "No bearish confirmation candle for SHORT setup.",
        "weak_candle":        "Candle body ratio too small — indecision candle, not momentum.",
        "low_volume":         "Volume below average — no institutional participation.",
        "grade_filter":       "Grade below minimum threshold — expected behavior.",
        "ml_filter":          "ML model scored below threshold — expected behavior.",
        "session_filter":     "Outside active trading session — expected behavior.",
        "max_open_trades":    "Maximum open trades reached — expected behavior.",
        "daily_loss_limit":   "Daily loss limit hit — expected behavior.",
        "loss_pause":         "Loss pause active — expected behavior.",
        "in_trade":           "Coin already in trade — expected behavior.",
        "cooldown":           "Coin in cooldown after recent trade — expected behavior.",
    }
    return actions.get(reason, f"Review {reason} filter — check engine logs for details.")


def _analyze_rejection_trends(daily_stats: list) -> dict:
    if not daily_stats:
        return {}

    try:
        trend_by_reason = {}

        for day_data in daily_stats:
            date_str = day_data.get("date", "")
            for reason, count in day_data.get("by_reason", {}).items():
                if reason not in trend_by_reason:
                    trend_by_reason[reason] = []
                trend_by_reason[reason].append({
                    "date":  date_str,
                    "count": count,
                })

        trends = {}
        for reason, data_points in trend_by_reason.items():
            if len(data_points) < 3:
                continue
            counts     = [d["count"] for d in data_points]
            recent     = counts[-3:]
            older      = counts[:-3] if len(counts) > 3 else counts
            recent_avg = sum(recent) / len(recent)
            older_avg  = sum(older)  / len(older) if older else recent_avg
            if older_avg > 0:
                change_pct = round((recent_avg - older_avg) / older_avg * 100, 1)
            else:
                change_pct = 0
            trend = "increasing" if change_pct > 10 else "decreasing" if change_pct < -10 else "stable"
            trends[reason] = {
                "trend":       trend,
                "change_pct":  change_pct,
                "recent_avg":  round(recent_avg, 1),
                "older_avg":   round(older_avg,  1),
                "data_points": data_points,
            }

        return trends

    except Exception as e:
        log.error("_analyze_rejection_trends: %s", e)
        return {}


def _generate_recommendations(
    bottlenecks:        list,
    filter_performance: dict,
    total_stats:        dict,
) -> list:
    recommendations = []
    signal_rate     = total_stats.get("signal_rate", 0)

    if signal_rate < 1.0:
        recommendations.append({
            "priority": "high",
            "type":     "signal_rate",
            "message":  f"Signal rate is {signal_rate}% — very low. Check ADX threshold and EMA alignment.",
        })
    elif signal_rate < 3.0:
        recommendations.append({
            "priority": "medium",
            "type":     "signal_rate",
            "message":  f"Signal rate is {signal_rate}% — below target. Monitor top rejections.",
        })

    for b in bottlenecks[:3]:
        if b["severity"] in ("critical", "high"):
            recommendations.append({
                "priority": b["severity"],
                "type":     "bottleneck",
                "filter":   b["filter"],
                "pct":      b["pct"],
                "message":  b["action"],
            })

    return recommendations


async def send_filter_report_telegram() -> None:
    try:
        from alerts.telegram import send
        report = run_filter_analysis()

        if report.get("error"):
            await send(f"📊 *Filter Analysis*\n\n{report['error']}")
            return

        total       = report.get("total_stats",         {})
        bottlenecks = report.get("bottleneck_analysis", [])[:5]
        recs        = report.get("recommendations",     [])[:3]

        lines = [
            f"🔍 *Filter Analysis Report*\n",
            f"Total Scans:   `{total.get('total_scans',   0)}`",
            f"Total Signals: `{total.get('total_signals', 0)}`",
            f"Signal Rate:   `{total.get('signal_rate',   0)}%`",
            f"",
            f"*Top Bottlenecks:*",
        ]

        for b in bottlenecks:
            severity_emoji = "🔴" if b["severity"] == "critical" else "🟡" if b["severity"] == "high" else "🟢"
            lines.append(f"{severity_emoji} `{b['filter']}` — `{b['pct']}%` of scans")

        if recs:
            lines.append(f"")
            lines.append(f"*Recommendations:*")
            for r in recs:
                lines.append(f"• {r['message']}")

        await send("\n".join(lines))

    except Exception as e:
        log.error("send_filter_report_telegram: %s", e)