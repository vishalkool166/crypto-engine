import logging
from datetime import datetime, timezone
from database import get_session, AdaptationLog, AdaptationRecommendation
from config import cfg, ADAPTATION_CONFIG

log = logging.getLogger(__name__)


def run() -> dict:
    try:
        log.info("Adapter started")

        if cfg.ADAPTATION_FROZEN:
            log.info("Adapter: adaptations frozen — skipping")
            return {"status": "frozen", "applied": 0}

        require_approval = ADAPTATION_CONFIG["change_rules"]["require_human_approval"]

        if require_approval:
            recommendations = _get_approved_recommendations()
        else:
            recommendations = _get_auto_recommendations()

        if not recommendations:
            log.info("Adapter: no recommendations to apply")
            return {"status": "no_recommendations", "applied": 0}

        applied = []
        skipped = []

        for rec in recommendations:
            if rec.get("parameter", "").startswith("pillar_weight_"):
                result = _apply_pillar_weight_recommendation(rec)
            else:
                result = _apply_recommendation(rec)

            if result["applied"]:
                applied.append(result)
            else:
                skipped.append(result)

        log.info("Adapter complete — applied:%s skipped:%s", len(applied), len(skipped))

        if applied:
            _notify_adapter_complete(applied, skipped)

        return {
            "status":  "complete",
            "applied": len(applied),
            "skipped": len(skipped),
            "details": applied,
        }

    except Exception as e:
        log.error("adapter.run: %s", e)
        return {"status": "error", "error": str(e), "applied": 0}


def _apply_pillar_weight_recommendation(rec: dict) -> dict:
    parameter = rec["parameter"]
    pillar    = parameter.replace("pillar_weight_", "")
    new_weight= float(rec["recommended_value"])
    rec_id    = rec.get("id")

    try:
        from ml.pillar_analyzer import apply_weight_change
        from ml.safety_checks import check_pillar_weight_change

        safety = check_pillar_weight_change(
            pillar        = pillar,
            current_weight= float(rec["current_value"]),
            new_weight    = new_weight,
        )

        if not safety["pass"]:
            log.info("Pillar weight skipped %s: %s", pillar, safety["failures"])
            return {
                "applied":   False,
                "parameter": parameter,
                "reason":    safety["failures"],
            }

        result = apply_weight_change(
            pillar      = pillar,
            new_weight  = new_weight,
            rec_id      = rec_id,
            approved_by = "adapter",
        )

        if result.get("success"):
            log.info(
                "Pillar weight applied: %s %.3f → %.3f",
                pillar, rec["current_value"], new_weight
            )
            return {
                "applied":     True,
                "parameter":   parameter,
                "old_value":   rec["current_value"],
                "new_value":   new_weight,
                "new_version": result.get("new_version"),
            }
        else:
            return {
                "applied":   False,
                "parameter": parameter,
                "reason":    result.get("reason", "Unknown error"),
            }

    except Exception as e:
        log.error("_apply_pillar_weight_recommendation %s: %s", pillar, e)
        return {"applied": False, "parameter": parameter, "reason": str(e)}


def _apply_recommendation(rec: dict) -> dict:
    parameter       = rec["parameter"]
    current_value   = float(rec["current_value"])
    proposed_value  = float(rec["recommended_value"])
    rec_id          = rec.get("id")

    from ml.safety_checks import check_all, check_win_rate_improvement

    safety = check_all(parameter, current_value, proposed_value)
    if not safety["pass"]:
        log.info("Adapter skipped %s: %s", parameter, safety["failures"])
        return {
            "applied":   False,
            "parameter": parameter,
            "reason":    safety["failures"],
        }

    current_wr  = _get_current_win_rate()
    proposed_wr = current_wr + (rec.get("expected_improvement", 0) / 100)

    wr_check = check_win_rate_improvement(
        parameter      = parameter,
        current_value  = current_value,
        proposed_value = proposed_value,
        current_wr     = current_wr,
        proposed_wr    = proposed_wr,
    )

    if not wr_check["pass"]:
        log.info("Adapter skipped %s: %s", parameter, wr_check["reason"])
        return {
            "applied":   False,
            "parameter": parameter,
            "reason":    wr_check["reason"],
        }

    version_before = cfg.SYSTEM_VERSION

    success = _update_parameter(parameter, proposed_value)
    if not success:
        return {
            "applied":   False,
            "parameter": parameter,
            "reason":    f"Failed to update parameter {parameter}",
        }

    from ml.version_registry import create_new_version
    new_version = create_new_version(
        reason     = f"Adaptation: {parameter} {current_value} → {proposed_value}",
        changed_by = "adapter",
    )

    total_trades      = _get_total_trades()
    adaptation_log_id = _log_change(
        parameter      = parameter,
        old_value      = current_value,
        new_value      = proposed_value,
        reasoning      = rec.get("reasoning", ""),
        data_basis     = rec.get("data_basis", total_trades),
        expected_imp   = rec.get("expected_improvement", 0),
        version_before = version_before,
        version_after  = new_version,
        rec_id         = rec_id,
    )

    if adaptation_log_id:
        from ml.rollback_manager import create_checkpoint
        create_checkpoint(
            adaptation_log_id = adaptation_log_id,
            parameter         = parameter,
            old_value         = current_value,
            new_value         = proposed_value,
            baseline_win_rate = current_wr,
            baseline_trades   = total_trades,
        )

    if rec_id:
        _mark_recommendation_applied(rec_id)

    _notify_change_applied(
        parameter    = parameter,
        old_value    = current_value,
        new_value    = proposed_value,
        reasoning    = rec.get("reasoning", ""),
        data_basis   = rec.get("data_basis", total_trades),
        expected_imp = rec.get("expected_improvement", 0),
        confidence   = rec.get("confidence", "low"),
        new_version  = new_version,
        total_trades = total_trades,
    )

    log.info(
        "Adaptation applied: %s %s → %s version:%s",
        parameter, current_value, proposed_value, new_version
    )

    return {
        "applied":     True,
        "parameter":   parameter,
        "old_value":   current_value,
        "new_value":   proposed_value,
        "new_version": new_version,
        "log_id":      adaptation_log_id,
    }


def _update_parameter(parameter: str, value: float) -> bool:
    try:
        SE = cfg.SCALP_ENGINE
        if parameter in SE:
            SE[parameter] = value
            log.info("Parameter updated: %s = %s", parameter, value)
            return True
        log.error("Parameter not found in SCALP_ENGINE: %s", parameter)
        return False
    except Exception as e:
        log.error("_update_parameter %s: %s", parameter, e)
        return False


def _log_change(
    parameter:      str,
    old_value:      float,
    new_value:      float,
    reasoning:      str,
    data_basis:     int,
    expected_imp:   float,
    version_before: str,
    version_after:  str,
    rec_id:         int | None,
) -> int | None:
    try:
        with get_session() as db:
            entry = AdaptationLog(
                parameter             = parameter,
                old_value             = old_value,
                new_value             = new_value,
                direction             = "increase" if new_value > old_value else "decrease",
                reasoning             = reasoning,
                data_basis            = data_basis,
                expected_improvement  = expected_imp,
                system_version_before = version_before,
                system_version_after  = version_after,
                recommendation_id     = rec_id,
                rolled_back           = False,
            )
            db.add(entry)
            db.flush()
            db.refresh(entry)
            return entry.id
    except Exception as e:
        log.error("_log_change: %s", e)
        return None


def _mark_recommendation_applied(rec_id: int) -> None:
    try:
        with get_session() as db:
            rec = db.query(AdaptationRecommendation).filter(
                AdaptationRecommendation.id == rec_id
            ).first()
            if rec:
                rec.status     = "applied"
                rec.applied_at = datetime.now(timezone.utc)
    except Exception as e:
        log.error("_mark_recommendation_applied: %s", e)


def _get_approved_recommendations() -> list:
    try:
        from ml.analyzer import get_approved_recommendations
        return get_approved_recommendations()
    except Exception as e:
        log.error("_get_approved_recommendations: %s", e)
        return []


def _get_auto_recommendations() -> list:
    try:
        from ml.analyzer import get_pending_recommendations
        pending = get_pending_recommendations()
        return [r for r in pending if r.get("confidence") in ("high", "medium")]
    except Exception as e:
        log.error("_get_auto_recommendations: %s", e)
        return []


def _get_current_win_rate() -> float:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.desc()).limit(50).all()

        if not closed:
            return 0.5

        wins = sum(1 for t in closed if t.outcome == "win")
        return wins / len(closed)

    except Exception as e:
        log.error("_get_current_win_rate: %s", e)
        return 0.5


def _get_total_trades() -> int:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()
    except Exception:
        return 0


def get_adaptation_history(limit: int = 20) -> list:
    try:
        with get_session() as db:
            rows = db.query(AdaptationLog).order_by(
                AdaptationLog.applied_at.desc()
            ).limit(limit).all()

            return [{
                "id":                   r.id,
                "parameter":            r.parameter,
                "old_value":            r.old_value,
                "new_value":            r.new_value,
                "direction":            r.direction,
                "reasoning":            r.reasoning,
                "data_basis":           r.data_basis,
                "expected_improvement": r.expected_improvement,
                "version_before":       r.system_version_before,
                "version_after":        r.system_version_after,
                "applied_at":           r.applied_at.isoformat() if r.applied_at else None,
                "rolled_back":          r.rolled_back,
                "rolled_back_at":       r.rolled_back_at.isoformat() if r.rolled_back_at else None,
            } for r in rows]

    except Exception as e:
        log.error("get_adaptation_history: %s", e)
        return []


def _notify_change_applied(
    parameter:    str,
    old_value:    float,
    new_value:    float,
    reasoning:    str,
    data_basis:   int,
    expected_imp: float,
    confidence:   str,
    new_version:  str,
    total_trades: int,
):
    try:
        import asyncio
        from alerts.telegram import send

        direction = "📈 Increased" if new_value > old_value else "📉 Decreased"
        rules     = ADAPTATION_CONFIG["change_rules"]

        asyncio.create_task(send(
            f"🧠 *Auto-Adaptation Applied*\n\n"
            f"Parameter: `{parameter}`\n"
            f"Change: `{old_value}` → `{new_value}` {direction}\n\n"
            f"Reason:\n_{reasoning[:200]}_\n\n"
            f"Data basis: `{data_basis}` trades\n"
            f"Confidence: `{confidence}`\n"
            f"Expected WR improvement: `+{expected_imp:.1f}%`\n\n"
            f"System version: `{new_version}`\n"
            f"Review checkpoint: `{rules['rollback_review_trades']}` trades from now\n\n"
            f"_Type /rollback {parameter} to revert manually._"
        ))
    except Exception as e:
        log.error("_notify_change_applied: %s", e)


def _notify_adapter_complete(applied: list, skipped: list):
    try:
        import asyncio
        from alerts.telegram import send

        if not applied:
            return

        lines = [f"✅ *Adaptation Cycle Complete*\n"]
        lines.append(f"Applied: `{len(applied)}` · Skipped: `{len(skipped)}`\n")

        for a in applied:
            lines.append(
                f"• `{a['parameter']}`: `{a['old_value']}` → `{a['new_value']}`"
            )

        asyncio.create_task(send("\n".join(lines)))

    except Exception as e:
        log.error("_notify_adapter_complete: %s", e)