import json
import logging
from datetime import datetime, timezone
from config import cfg, ADAPTATION_CONFIG
from database import get_session, AdaptationRecommendation

log = logging.getLogger(__name__)


def run() -> dict:
    try:
        log.info("Analyzer started")

        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            total_trades = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()

        min_trades = ADAPTATION_CONFIG["change_rules"]["min_trades_before_change"]

        if total_trades < min_trades:
            log.info("Analyzer: insufficient trades %s/%s", total_trades, min_trades)
            return {
                "status":       "insufficient_data",
                "total_trades": total_trades,
                "min_required": min_trades,
                "recommendations": [],
            }

        from ml.performance_tracker import get_full_report, get_recent_trend
        from ml.threshold_optimizer import run_full_optimization
        from ml.regime_classifier   import get_regime_recommendations

        report          = get_full_report()
        trend           = get_recent_trend(window=20)
        optimization    = run_full_optimization()
        regime_recs     = get_regime_recommendations()

        recommendations = []

        for rec in optimization.get("recommendations", []):
            if rec.get("recommend_change") if isinstance(rec, dict) and "recommend_change" in rec else True:
                recommendations.append({
                    "type":            "threshold",
                    "parameter":       rec["parameter"],
                    "current_value":   rec["current_value"],
                    "recommended_value": rec["new_value"],
                    "direction":       "increase" if rec["new_value"] > rec["current_value"] else "decrease",
                    "expected_improvement": rec.get("improvement", 0),
                    "data_basis":      rec.get("data_basis", total_trades),
                    "confidence":      rec.get("confidence", "low"),
                    "reasoning":       rec.get("reason", ""),
                })

        for rec in regime_recs:
            recommendations.append({
                "type":            "regime",
                "parameter":       f"regime_{rec['type']}",
                "current_value":   0,
                "recommended_value": 1 if rec["action"] == "avoid" else 0.5,
                "direction":       rec["action"],
                "expected_improvement": 0,
                "data_basis":      rec.get("trades", 0),
                "confidence":      "medium" if rec.get("trades", 0) >= 20 else "low",
                "reasoning":       rec.get("reason", ""),
            })

        degrading = trend.get("trend") == "degrading"
        if degrading:
            recommendations.append({
                "type":            "alert",
                "parameter":       "performance_trend",
                "current_value":   trend.get("alltime_win_rate", 0),
                "recommended_value": 0,
                "direction":       "alert",
                "expected_improvement": 0,
                "data_basis":      trend.get("recent_trades", 0),
                "confidence":      "high",
                "reasoning":       (
                    f"Recent {trend.get('recent_window')} trades WR "
                    f"{trend.get('recent_win_rate', 0):.1f}% vs "
                    f"all-time {trend.get('alltime_win_rate', 0):.1f}% — "
                    f"performance degrading"
                ),
            })

        saved = _save_recommendations(recommendations)

        result = {
            "status":          "complete",
            "total_trades":    total_trades,
            "recommendations": recommendations,
            "saved":           saved,
            "report_summary":  _summarize_report(report),
            "trend":           trend,
            "analyzed_at":     datetime.now(timezone.utc).isoformat(),
        }

        log.info("Analyzer complete — %s recommendations", len(recommendations))
        _notify_analysis_complete(result)
        return result

    except Exception as e:
        log.error("analyzer.run: %s", e)
        return {"status": "error", "error": str(e), "recommendations": []}


def _save_recommendations(recommendations: list) -> int:
    saved = 0
    try:
        with get_session() as db:
            for rec in recommendations:
                if rec.get("type") == "alert":
                    continue

                row = AdaptationRecommendation(
                    parameter               = rec["parameter"],
                    current_value           = float(rec["current_value"]),
                    recommended_value       = float(rec["recommended_value"]),
                    direction               = rec["direction"],
                    expected_wr_improvement = rec.get("expected_improvement"),
                    data_basis              = rec.get("data_basis"),
                    confidence              = rec.get("confidence"),
                    reasoning               = rec.get("reasoning"),
                    status                  = "pending",
                )
                db.add(row)
                saved += 1

        log.info("Saved %s recommendations", saved)
        return saved

    except Exception as e:
        log.error("_save_recommendations: %s", e)
        return 0


def get_pending_recommendations() -> list:
    try:
        with get_session() as db:
            rows = db.query(AdaptationRecommendation).filter(
                AdaptationRecommendation.status == "pending"
            ).order_by(
                AdaptationRecommendation.created_at.desc()
            ).all()

            return [{
                "id":                   r.id,
                "parameter":            r.parameter,
                "current_value":        r.current_value,
                "recommended_value":    r.recommended_value,
                "direction":            r.direction,
                "expected_improvement": r.expected_wr_improvement,
                "data_basis":           r.data_basis,
                "confidence":           r.confidence,
                "reasoning":            r.reasoning,
                "status":               r.status,
                "created_at":           r.created_at.isoformat() if r.created_at else None,
            } for r in rows]

    except Exception as e:
        log.error("get_pending_recommendations: %s", e)
        return []


def approve_recommendation(rec_id: int, approved_by: str = "human") -> bool:
    try:
        with get_session() as db:
            rec = db.query(AdaptationRecommendation).filter(
                AdaptationRecommendation.id == rec_id
            ).first()
            if not rec:
                return False
            rec.status      = "approved"
            rec.approved_at = datetime.now(timezone.utc)
            rec.approved_by = approved_by
        log.info("Recommendation %s approved by %s", rec_id, approved_by)
        return True
    except Exception as e:
        log.error("approve_recommendation: %s", e)
        return False


def reject_recommendation(rec_id: int, reason: str = "") -> bool:
    try:
        with get_session() as db:
            rec = db.query(AdaptationRecommendation).filter(
                AdaptationRecommendation.id == rec_id
            ).first()
            if not rec:
                return False
            rec.status           = "rejected"
            rec.rejected_at      = datetime.now(timezone.utc)
            rec.rejection_reason = reason
        log.info("Recommendation %s rejected", rec_id)
        return True
    except Exception as e:
        log.error("reject_recommendation: %s", e)
        return False


def get_approved_recommendations() -> list:
    try:
        with get_session() as db:
            rows = db.query(AdaptationRecommendation).filter(
                AdaptationRecommendation.status == "approved"
            ).order_by(
                AdaptationRecommendation.approved_at.asc()
            ).all()

            return [{
                "id":                   r.id,
                "parameter":            r.parameter,
                "current_value":        r.current_value,
                "recommended_value":    r.recommended_value,
                "direction":            r.direction,
                "expected_improvement": r.expected_wr_improvement,
                "data_basis":           r.data_basis,
                "confidence":           r.confidence,
                "reasoning":            r.reasoning,
                "approved_at":          r.approved_at.isoformat() if r.approved_at else None,
            } for r in rows]

    except Exception as e:
        log.error("get_approved_recommendations: %s", e)
        return []


def _summarize_report(report: dict) -> dict:
    try:
        overall = report.get("overall", {})
        trend   = report.get("recent_trend", {})

        return {
            "total_trades":    overall.get("total",         0),
            "win_rate":        overall.get("win_rate",       0),
            "total_pnl":       overall.get("total_pnl",      0),
            "profit_factor":   overall.get("profit_factor",  0),
            "max_drawdown":    overall.get("max_drawdown",   0),
            "recent_trend":    trend.get("trend",            "unknown"),
            "recent_wr":       trend.get("recent_win_rate",  0),
            "alltime_wr":      trend.get("alltime_win_rate", 0),
        }
    except Exception:
        return {}


def _notify_analysis_complete(result: dict):
    try:
        import asyncio
        from alerts.telegram import send

        recs        = result.get("recommendations", [])
        threshold   = [r for r in recs if r.get("type") == "threshold"]
        alerts      = [r for r in recs if r.get("type") == "alert"]
        summary     = result.get("report_summary", {})
        trend       = result.get("trend", {})

        lines = [
            f"🔍 *Weekly Analysis Complete*\n",
            f"Trades analyzed: `{result.get('total_trades', 0)}`",
            f"Win rate: `{summary.get('win_rate', 0):.1f}%`",
            f"Total PnL: `${summary.get('total_pnl', 0):.2f}`",
            f"Recent trend: `{trend.get('trend', 'unknown')}`",
            f"",
        ]

        if threshold:
            lines.append(f"*{len(threshold)} Parameter Recommendations:*")
            for r in threshold[:3]:
                direction_emoji = "📈" if r["direction"] == "increase" else "📉"
                lines.append(
                    f"{direction_emoji} `{r['parameter']}`: "
                    f"`{r['current_value']}` → `{r['recommended_value']}` "
                    f"(+{r.get('expected_improvement', 0):.1f}% WR)"
                )
            lines.append("")

        if alerts:
            lines.append(f"*⚠️ {len(alerts)} Alert(s):*")
            for a in alerts:
                lines.append(f"  ⚠️ {a.get('reasoning', '')[:100]}")
            lines.append("")

        require_approval = ADAPTATION_CONFIG["change_rules"]["require_human_approval"]
        if threshold and require_approval:
            lines.append("_Recommendations pending your approval._")
            lines.append("_Use /adaptations to review and approve._")
        elif threshold and not require_approval:
            lines.append("_Recommendations queued for auto-application._")
            lines.append("_Use /adaptations to review._")
        else:
            lines.append("_No parameter changes recommended this week._")

        asyncio.create_task(send("\n".join(lines)))

    except Exception as e:
        log.error("_notify_analysis_complete: %s", e)