import json
import logging
from datetime import datetime, timezone
from database import get_session, ThesisSnapshot, AdaptationRecommendation
from config import cfg, ADAPTATION_CONFIG

log = logging.getLogger(__name__)

MIN_TRADES_FOR_ANALYSIS  = 50
MIN_FAILURES_PER_PILLAR  = 10
MAX_WEIGHT_CHANGE        = 0.05
MIN_WEIGHT               = 0.05
MAX_WEIGHT               = 0.50
MIN_WIN_RATE_DIFFERENCE  = 0.05

PILLAR_NAMES = ["sweep", "zone", "structure", "btc_alignment", "regime"]

DEFAULT_WEIGHTS = {
    "sweep":         0.25,
    "zone":          0.25,
    "structure":     0.20,
    "btc_alignment": 0.15,
    "regime":        0.15,
}

REDIS_WEIGHTS_KEY = "thesis:pillar_weights"


def get_current_weights() -> dict:
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            raw = r.get(REDIS_WEIGHTS_KEY)
            if raw:
                weights = json.loads(raw)
                if all(p in weights for p in PILLAR_NAMES):
                    return weights
    except Exception as e:
        log.warning("get_current_weights redis: %s", e)

    try:
        from database import SessionLocal, PillarWeightHistory
        with SessionLocal() as db:
            latest = db.query(PillarWeightHistory).order_by(
                PillarWeightHistory.applied_at.desc()
            ).first()
            if latest:
                weights = _build_weights_from_history()
                if weights:
                    _store_weights_redis(weights)
                    return weights
    except Exception as e:
        log.warning("get_current_weights db: %s", e)

    return dict(DEFAULT_WEIGHTS)


def _build_weights_from_history() -> dict:
    try:
        from database import SessionLocal, PillarWeightHistory
        weights = dict(DEFAULT_WEIGHTS)
        with SessionLocal() as db:
            for pillar in PILLAR_NAMES:
                latest = db.query(PillarWeightHistory).filter(
                    PillarWeightHistory.pillar      == pillar,
                    PillarWeightHistory.rolled_back == False,
                ).order_by(PillarWeightHistory.applied_at.desc()).first()
                if latest:
                    weights[pillar] = latest.new_weight
        return weights
    except Exception as e:
        log.error("_build_weights_from_history: %s", e)
        return dict(DEFAULT_WEIGHTS)


def _store_weights_redis(weights: dict) -> None:
    try:
        from redis_client import get_redis
        r = get_redis()
        if r:
            r.set(REDIS_WEIGHTS_KEY, json.dumps(weights))
    except Exception as e:
        log.warning("_store_weights_redis: %s", e)


def run() -> dict:
    try:
        log.info("Pillar analyzer started")

        snapshots = _load_snapshots_with_outcomes()

        if len(snapshots) < MIN_TRADES_FOR_ANALYSIS:
            log.info(
                "Pillar analyzer: insufficient data %s/%s",
                len(snapshots), MIN_TRADES_FOR_ANALYSIS
            )
            return {
                "status":          "insufficient_data",
                "total":           len(snapshots),
                "min_required":    MIN_TRADES_FOR_ANALYSIS,
                "recommendations": [],
            }

        current_weights = get_current_weights()
        pillar_stats    = _analyze_pillars(snapshots)
        recommendations = _generate_recommendations(pillar_stats, current_weights)

        saved = _save_recommendations(recommendations)

        result = {
            "status":          "complete",
            "total_snapshots": len(snapshots),
            "pillar_stats":    pillar_stats,
            "current_weights": current_weights,
            "recommendations": recommendations,
            "saved":           saved,
            "analyzed_at":     datetime.now(timezone.utc).isoformat(),
        }

        log.info(
            "Pillar analyzer complete — snapshots:%s recommendations:%s",
            len(snapshots), len(recommendations)
        )

        _notify_complete(result)
        return result

    except Exception as e:
        log.error("pillar_analyzer.run: %s", e)
        return {"status": "error", "error": str(e), "recommendations": []}


def _load_snapshots_with_outcomes() -> list:
    try:
        from database import SessionLocal
        with SessionLocal() as db:
            snapshots = db.query(ThesisSnapshot).filter(
                ThesisSnapshot.outcome.isnot(None),
                ThesisSnapshot.final_pnl.isnot(None),
            ).all()

        result = []
        for s in snapshots:
            result.append({
                "trade_id":           s.trade_id,
                "grade":              s.grade,
                "outcome":            s.outcome,
                "final_pnl":          float(s.final_pnl or 0),
                "thesis_strength":    float(s.thesis_strength or 0),
                "thesis_action":      s.thesis_action,
                "hours_open":         float(s.hours_open or 0),
                "move_pct":           float(s.move_pct or 0),
                "captured_move_pct":  float(s.captured_move_pct or 0),
                "velocity":           float(s.velocity or 0),
                "sweep_valid":        bool(s.sweep_valid),
                "sweep_score":        float(s.sweep_score or 0),
                "zone_valid":         bool(s.zone_valid),
                "zone_score":         float(s.zone_score or 0),
                "structure_valid":    bool(s.structure_valid),
                "structure_score":    float(s.structure_score or 0),
                "btc_alignment_valid":bool(s.btc_alignment_valid),
                "btc_alignment_score":float(s.btc_alignment_score or 0),
                "regime_valid":       bool(s.regime_valid),
                "regime_score":       float(s.regime_score or 0),
                "entry_regime":       s.entry_regime,
                "current_regime":     s.current_regime,
            })

        return result

    except Exception as e:
        log.error("_load_snapshots_with_outcomes: %s", e)
        return []


def _analyze_pillars(snapshots: list) -> dict:
    stats = {}

    for pillar in PILLAR_NAMES:
        valid_key   = f"{pillar}_valid"
        score_key   = f"{pillar}_score"

        valid_wins   = [s for s in snapshots if s.get(valid_key) and s["outcome"] == "win"]
        valid_losses = [s for s in snapshots if s.get(valid_key) and s["outcome"] == "loss"]
        fail_wins    = [s for s in snapshots if not s.get(valid_key) and s["outcome"] == "win"]
        fail_losses  = [s for s in snapshots if not s.get(valid_key) and s["outcome"] == "loss"]

        valid_total = len(valid_wins) + len(valid_losses)
        fail_total  = len(fail_wins)  + len(fail_losses)

        wr_when_valid = (
            len(valid_wins) / valid_total
            if valid_total > 0 else None
        )
        wr_when_failed = (
            len(fail_wins) / fail_total
            if fail_total > 0 else None
        )

        predictive_power = None
        if wr_when_valid is not None and wr_when_failed is not None:
            predictive_power = round(wr_when_valid - wr_when_failed, 4)

        avg_score_wins   = (
            sum(s[score_key] for s in valid_wins) / len(valid_wins)
            if valid_wins else 0.0
        )
        avg_score_losses = (
            sum(s[score_key] for s in valid_losses) / len(valid_losses)
            if valid_losses else 0.0
        )

        captured_when_valid = (
            sum(s["captured_move_pct"] for s in valid_wins) / len(valid_wins)
            if valid_wins else 0.0
        )
        captured_when_failed = (
            sum(s["captured_move_pct"] for s in fail_wins) / len(fail_wins)
            if fail_wins else 0.0
        )

        stats[pillar] = {
            "valid_total":          valid_total,
            "fail_total":           fail_total,
            "valid_wins":           len(valid_wins),
            "valid_losses":         len(valid_losses),
            "fail_wins":            len(fail_wins),
            "fail_losses":          len(fail_losses),
            "wr_when_valid":        round(wr_when_valid  * 100, 1) if wr_when_valid  is not None else None,
            "wr_when_failed":       round(wr_when_failed * 100, 1) if wr_when_failed is not None else None,
            "predictive_power":     predictive_power,
            "avg_score_wins":       round(avg_score_wins,   3),
            "avg_score_losses":     round(avg_score_losses, 3),
            "captured_when_valid":  round(captured_when_valid,  1),
            "captured_when_failed": round(captured_when_failed, 1),
            "sufficient_data":      fail_total >= MIN_FAILURES_PER_PILLAR,
        }

    return stats


def _generate_recommendations(pillar_stats: dict, current_weights: dict) -> list:
    recommendations = []

    for pillar, stats in pillar_stats.items():
        if not stats["sufficient_data"]:
            continue

        predictive_power = stats.get("predictive_power")
        if predictive_power is None:
            continue

        current_weight = current_weights.get(pillar, DEFAULT_WEIGHTS.get(pillar, 0.20))

        if predictive_power > MIN_WIN_RATE_DIFFERENCE:
            direction  = "increase"
            new_weight = min(MAX_WEIGHT, current_weight + MAX_WEIGHT_CHANGE)
        elif predictive_power < -MIN_WIN_RATE_DIFFERENCE:
            direction  = "decrease"
            new_weight = max(MIN_WEIGHT, current_weight - MAX_WEIGHT_CHANGE)
        else:
            continue

        if abs(new_weight - current_weight) < 0.001:
            continue

        expected_improvement = abs(predictive_power) * 100

        confidence = (
            "high"   if stats["fail_total"] >= 50 else
            "medium" if stats["fail_total"] >= 25 else
            "low"
        )

        reasoning = (
            f"Pillar '{pillar}': WR when valid={stats['wr_when_valid']}% "
            f"vs failed={stats['wr_when_failed']}% "
            f"(diff={predictive_power*100:.1f}%). "
            f"Captured move when valid={stats['captured_when_valid']:.1f}% "
            f"vs failed={stats['captured_when_failed']:.1f}%. "
            f"Based on {stats['fail_total']} failure events."
        )

        recommendations.append({
            "type":                 "pillar_weight",
            "pillar":               pillar,
            "parameter":            f"pillar_weight_{pillar}",
            "current_value":        current_weight,
            "recommended_value":    round(new_weight, 3),
            "direction":            direction,
            "expected_improvement": round(expected_improvement, 2),
            "data_basis":           stats["fail_total"],
            "confidence":           confidence,
            "reasoning":            reasoning,
            "stats":                stats,
        })

    return recommendations


def _save_recommendations(recommendations: list) -> int:
    saved = 0
    try:
        with get_session() as db:
            for rec in recommendations:
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

        log.info("Saved %s pillar weight recommendations", saved)
        return saved

    except Exception as e:
        log.error("_save_recommendations: %s", e)
        return 0


def apply_weight_change(
    pillar:      str,
    new_weight:  float,
    rec_id:      int | None = None,
    approved_by: str        = "human",
) -> dict:
    try:
        if pillar not in PILLAR_NAMES:
            return {"success": False, "reason": f"Unknown pillar: {pillar}"}

        if new_weight < MIN_WEIGHT or new_weight > MAX_WEIGHT:
            return {
                "success": False,
                "reason":  f"Weight {new_weight} outside bounds [{MIN_WEIGHT}, {MAX_WEIGHT}]"
            }

        current_weights = get_current_weights()
        old_weight      = current_weights.get(pillar, DEFAULT_WEIGHTS[pillar])

        if abs(new_weight - old_weight) > MAX_WEIGHT_CHANGE:
            return {
                "success": False,
                "reason":  f"Change {abs(new_weight - old_weight):.3f} exceeds max {MAX_WEIGHT_CHANGE}"
            }

        current_weights[pillar] = new_weight

        total = sum(current_weights.values())
        if abs(total - 1.0) > 0.001:
            factor = 1.0 / total
            for p in PILLAR_NAMES:
                if p != pillar:
                    current_weights[p] = round(current_weights[p] * factor, 4)
            current_weights[pillar] = round(new_weight, 4)

        _store_weights_redis(current_weights)

        from ml.version_registry import get_current_version, create_new_version
        version_before = get_current_version()
        new_version    = create_new_version(
            reason     = f"Pillar weight: {pillar} {old_weight} → {new_weight}",
            changed_by = approved_by,
        )

        from database import SessionLocal, PillarWeightHistory
        with SessionLocal() as db:
            db.add(PillarWeightHistory(
                pillar                = pillar,
                old_weight            = old_weight,
                new_weight            = new_weight,
                approved_by           = approved_by,
                system_version_before = version_before,
                system_version_after  = new_version,
            ))

        if rec_id:
            with get_session() as db:
                rec = db.query(AdaptationRecommendation).filter(
                    AdaptationRecommendation.id == rec_id
                ).first()
                if rec:
                    rec.status     = "applied"
                    rec.applied_at = datetime.now(timezone.utc)

        log.info(
            "Pillar weight applied: %s %.3f → %.3f version:%s",
            pillar, old_weight, new_weight, new_version
        )

        _notify_weight_change(pillar, old_weight, new_weight, new_version)

        return {
            "success":     True,
            "pillar":      pillar,
            "old_weight":  old_weight,
            "new_weight":  new_weight,
            "new_weights": current_weights,
            "new_version": new_version,
        }

    except Exception as e:
        log.error("apply_weight_change %s: %s", pillar, e)
        return {"success": False, "reason": str(e)}


def rollback_weight(pillar: str, reason: str = "manual") -> dict:
    try:
        from database import SessionLocal, PillarWeightHistory
        with SessionLocal() as db:
            latest = db.query(PillarWeightHistory).filter(
                PillarWeightHistory.pillar      == pillar,
                PillarWeightHistory.rolled_back == False,
            ).order_by(PillarWeightHistory.applied_at.desc()).first()

            if not latest:
                return {"success": False, "reason": f"No weight history for {pillar}"}

            old_weight = latest.new_weight
            restore_to = latest.old_weight

            latest.rolled_back    = True
            latest.rolled_back_at = datetime.now(timezone.utc)

        result = apply_weight_change(
            pillar      = pillar,
            new_weight  = restore_to,
            approved_by = "rollback",
        )

        if result.get("success"):
            log.info("Pillar weight rolled back: %s %.3f → %.3f", pillar, old_weight, restore_to)

        return result

    except Exception as e:
        log.error("rollback_weight %s: %s", pillar, e)
        return {"success": False, "reason": str(e)}


def get_weight_history(pillar: str = None, limit: int = 20) -> list:
    try:
        from database import SessionLocal, PillarWeightHistory
        with SessionLocal() as db:
            query = db.query(PillarWeightHistory)
            if pillar:
                query = query.filter(PillarWeightHistory.pillar == pillar)
            rows = query.order_by(
                PillarWeightHistory.applied_at.desc()
            ).limit(limit).all()

            return [{
                "id":                   r.id,
                "pillar":               r.pillar,
                "old_weight":           r.old_weight,
                "new_weight":           r.new_weight,
                "data_basis":           r.data_basis,
                "failure_count":        r.failure_count,
                "win_rate_when_failed": r.win_rate_when_failed,
                "win_rate_when_valid":  r.win_rate_when_valid,
                "expected_improvement": r.expected_improvement,
                "reasoning":            r.reasoning,
                "approved_by":          r.approved_by,
                "system_version_before":r.system_version_before,
                "system_version_after": r.system_version_after,
                "rolled_back":          r.rolled_back,
                "rolled_back_at":       r.rolled_back_at.isoformat() if r.rolled_back_at else None,
                "applied_at":           r.applied_at.isoformat() if r.applied_at else None,
            } for r in rows]

    except Exception as e:
        log.error("get_weight_history: %s", e)
        return []


def cleanup_old_snapshots(keep_per_trade: int = 200) -> int:
    try:
        from database import SessionLocal

        deleted = 0
        with SessionLocal() as db:
            trade_ids = [
                row[0] for row in
                db.query(ThesisSnapshot.trade_id).distinct().all()
            ]

            for trade_id in trade_ids:
                count = db.query(ThesisSnapshot).filter(
                    ThesisSnapshot.trade_id == trade_id
                ).count()

                if count <= keep_per_trade:
                    continue

                to_delete = count - keep_per_trade
                oldest = db.query(ThesisSnapshot).filter(
                    ThesisSnapshot.trade_id == trade_id
                ).order_by(
                    ThesisSnapshot.captured_at.asc()
                ).limit(to_delete).all()

                for snap in oldest:
                    db.delete(snap)
                deleted += to_delete

        if deleted:
            log.info("ThesisSnapshot cleanup: deleted %s old snapshots", deleted)
        return deleted

    except Exception as e:
        log.error("cleanup_old_snapshots: %s", e)
        return 0


def _notify_complete(result: dict) -> None:
    try:
        import asyncio
        from alerts.telegram import send

        recs = result.get("recommendations", [])
        if not recs:
            return

        lines = [f"🧠 *Pillar Weight Analysis Complete*\n"]
        lines.append(f"Snapshots analyzed: `{result.get('total_snapshots', 0)}`\n")
        lines.append(f"*Recommendations:*")

        for r in recs[:5]:
            direction = "📈" if r["direction"] == "increase" else "📉"
            lines.append(
                f"{direction} `{r['pillar']}`: "
                f"`{r['current_value']:.3f}` → `{r['recommended_value']:.3f}` "
                f"[{r['confidence']}]"
            )

        lines.append(f"\n_Use /adaptations to review and approve._")
        asyncio.create_task(send("\n".join(lines)))

    except Exception as e:
        log.error("_notify_complete: %s", e)


def _notify_weight_change(
    pillar:      str,
    old_weight:  float,
    new_weight:  float,
    new_version: str,
) -> None:
    try:
        import asyncio
        from alerts.telegram import send

        direction = "📈 Increased" if new_weight > old_weight else "📉 Decreased"
        asyncio.create_task(send(
            f"⚖️ *Pillar Weight Updated*\n\n"
            f"Pillar:  `{pillar}`\n"
            f"Change:  `{old_weight:.3f}` → `{new_weight:.3f}` {direction}\n"
            f"Version: `{new_version}`\n\n"
            f"_ThesisTracker will use new weights immediately._"
        ))
    except Exception as e:
        log.error("_notify_weight_change: %s", e)