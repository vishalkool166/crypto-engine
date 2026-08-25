import logging
from datetime import datetime, timezone
from database import get_session, AdaptationLog, RollbackCheckpoint
from config import cfg, ADAPTATION_CONFIG

log = logging.getLogger(__name__)


def create_checkpoint(
    adaptation_log_id: int,
    parameter:         str,
    old_value:         float,
    new_value:         float,
    baseline_win_rate: float,
    baseline_trades:   int,
) -> int | None:
    try:
        rules         = ADAPTATION_CONFIG["change_rules"]
        review_trades = baseline_trades + rules["rollback_review_trades"]
        trigger_drop  = rules["rollback_trigger_drop"]
        trigger_wr    = baseline_win_rate - trigger_drop

        with get_session() as db:
            checkpoint = RollbackCheckpoint(
                adaptation_log_id     = adaptation_log_id,
                parameter             = parameter,
                old_value             = old_value,
                new_value             = new_value,
                baseline_win_rate     = baseline_win_rate,
                baseline_trade_count  = baseline_trades,
                review_at_trade_count = review_trades,
                rollback_trigger_wr   = max(0.0, trigger_wr),
                status                = "pending",
            )
            db.add(checkpoint)
            db.flush()
            db.refresh(checkpoint)
            checkpoint_id = checkpoint.id

        log.info(
            "Checkpoint created: id=%s param=%s review_at=%s trades trigger_wr=%.3f",
            checkpoint_id, parameter, review_trades, trigger_wr,
        )
        return checkpoint_id

    except Exception as e:
        log.error("create_checkpoint: %s", e)
        return None


def check_all_pending() -> list:
    results = []
    try:
        with get_session() as db:
            pending = db.query(RollbackCheckpoint).filter(
                RollbackCheckpoint.status == "pending"
            ).all()

        current_total = _get_total_trades()

        for checkpoint in pending:
            if current_total < checkpoint.review_at_trade_count:
                continue
            result = _evaluate_checkpoint(checkpoint, current_total)
            results.append(result)

        return results

    except Exception as e:
        log.error("check_all_pending: %s", e)
        return []


def _evaluate_checkpoint(checkpoint: RollbackCheckpoint, current_total: int) -> dict:
    try:
        post_change_trades = _get_trades_since(checkpoint.baseline_trade_count)
        post_change_wr     = _calculate_win_rate(post_change_trades)

        with get_session() as db:
            cp = db.query(RollbackCheckpoint).filter(
                RollbackCheckpoint.id == checkpoint.id
            ).first()
            if not cp:
                return {}

            cp.post_change_win_rate = post_change_wr
            cp.post_change_trades   = len(post_change_trades)
            cp.reviewed_at          = datetime.now(timezone.utc)

            should_rollback = (
                post_change_wr is not None and
                len(post_change_trades) >= 10 and
                post_change_wr < checkpoint.rollback_trigger_wr
            )

            if should_rollback:
                cp.status      = "rolled_back"
                cp.rolled_back = True
                success        = _apply_rollback(
                    parameter = checkpoint.parameter,
                    old_value = checkpoint.old_value,
                    new_value = checkpoint.new_value,
                    reason    = (
                        f"Auto-rollback: post-change WR {post_change_wr*100:.1f}% "
                        f"below trigger {checkpoint.rollback_trigger_wr*100:.1f}%"
                    ),
                )
                result = {
                    "checkpoint_id":    checkpoint.id,
                    "parameter":        checkpoint.parameter,
                    "action":           "rolled_back",
                    "post_change_wr":   round(post_change_wr * 100, 1) if post_change_wr else None,
                    "trigger_wr":       round(checkpoint.rollback_trigger_wr * 100, 1),
                    "baseline_wr":      round(checkpoint.baseline_win_rate * 100, 1),
                    "trades_evaluated": len(post_change_trades),
                    "rollback_success": success,
                }
                _notify_rollback(result)
            else:
                cp.status = "confirmed"
                result    = {
                    "checkpoint_id":    checkpoint.id,
                    "parameter":        checkpoint.parameter,
                    "action":           "confirmed",
                    "post_change_wr":   round(post_change_wr * 100, 1) if post_change_wr else None,
                    "trigger_wr":       round(checkpoint.rollback_trigger_wr * 100, 1),
                    "baseline_wr":      round(checkpoint.baseline_win_rate * 100, 1),
                    "trades_evaluated": len(post_change_trades),
                }
                _notify_confirmed(result)

        return result

    except Exception as e:
        log.error("_evaluate_checkpoint id=%s: %s", checkpoint.id, e)
        return {}


def manual_rollback(parameter: str, reason: str = "manual") -> dict:
    try:
        with get_session() as db:
            last_change = db.query(AdaptationLog).filter(
                AdaptationLog.parameter   == parameter,
                AdaptationLog.rolled_back == False,
            ).order_by(AdaptationLog.applied_at.desc()).first()

            if not last_change:
                return {
                    "success": False,
                    "reason":  f"No change history found for {parameter}",
                }

            old_value = last_change.old_value
            new_value = last_change.new_value
            log_id    = last_change.id

        success = _apply_rollback(
            parameter = parameter,
            old_value = old_value,
            new_value = new_value,
            reason    = reason,
        )

        if success:
            with get_session() as db:
                log_entry = db.query(AdaptationLog).filter(
                    AdaptationLog.id == log_id
                ).first()
                if log_entry:
                    log_entry.rolled_back     = True
                    log_entry.rolled_back_at  = datetime.now(timezone.utc)
                    log_entry.rollback_reason = reason

        return {
            "success":   success,
            "parameter": parameter,
            "restored":  old_value,
            "from":      new_value,
            "reason":    reason,
        }

    except Exception as e:
        log.error("manual_rollback %s: %s", parameter, e)
        return {"success": False, "reason": str(e)}


def _apply_rollback(
    parameter: str,
    old_value: float,
    new_value: float,
    reason:    str,
) -> bool:
    try:
        HE = cfg.HYBRID_ENGINE

        if parameter in HE:
            HE[parameter] = old_value
            log.info("Rollback applied: %s %s → %s", parameter, new_value, old_value)
        else:
            log.error("Rollback failed: %s not in HYBRID_ENGINE", parameter)
            return False

        from ml.version_registry import create_new_version
        create_new_version(
            reason     = f"Rollback: {parameter} {new_value} → {old_value} — {reason}",
            changed_by = "rollback_manager",
        )

        with get_session() as db:
            log_entry = AdaptationLog(
                parameter             = parameter,
                old_value             = new_value,
                new_value             = old_value,
                direction             = "rollback",
                reasoning             = reason,
                data_basis            = _get_total_trades(),
                expected_improvement  = 0.0,
                system_version_before = cfg.SYSTEM_VERSION,
                system_version_after  = cfg.SYSTEM_VERSION,
                rolled_back           = False,
            )
            db.add(log_entry)

        return True

    except Exception as e:
        log.error("_apply_rollback %s: %s", parameter, e)
        return False


def get_rollback_history(limit: int = 20) -> list:
    try:
        with get_session() as db:
            rows = db.query(AdaptationLog).filter(
                AdaptationLog.rolled_back == True
            ).order_by(AdaptationLog.rolled_back_at.desc()).limit(limit).all()

            return [{
                "id":             r.id,
                "parameter":      r.parameter,
                "old_value":      r.old_value,
                "new_value":      r.new_value,
                "applied_at":     r.applied_at.isoformat()     if r.applied_at     else None,
                "rolled_back_at": r.rolled_back_at.isoformat() if r.rolled_back_at else None,
                "reason":         r.rollback_reason,
            } for r in rows]

    except Exception as e:
        log.error("get_rollback_history: %s", e)
        return []


def get_pending_checkpoints() -> list:
    try:
        with get_session() as db:
            rows = db.query(RollbackCheckpoint).filter(
                RollbackCheckpoint.status == "pending"
            ).order_by(RollbackCheckpoint.created_at.asc()).all()

            current_total = _get_total_trades()

            return [{
                "id":                    r.id,
                "parameter":             r.parameter,
                "old_value":             r.old_value,
                "new_value":             r.new_value,
                "baseline_win_rate":     round(r.baseline_win_rate * 100, 1),
                "rollback_trigger_wr":   round(r.rollback_trigger_wr * 100, 1),
                "review_at_trade_count": r.review_at_trade_count,
                "current_trade_count":   current_total,
                "trades_remaining":      max(0, r.review_at_trade_count - current_total),
                "created_at":            r.created_at.isoformat() if r.created_at else None,
            } for r in rows]

    except Exception as e:
        log.error("get_pending_checkpoints: %s", e)
        return []


def _get_total_trades() -> int:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            return db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).count()
    except Exception:
        return 0


def _get_trades_since(baseline_count: int) -> list:
    try:
        from database import SessionLocal, Trade as TradeModel
        with SessionLocal() as db:
            all_closed = db.query(TradeModel).filter(
                TradeModel.outcome.in_(["win", "loss"])
            ).order_by(TradeModel.opened_at.asc()).all()
        return all_closed[baseline_count:]
    except Exception as e:
        log.error("_get_trades_since: %s", e)
        return []


def _calculate_win_rate(trades: list) -> float | None:
    if not trades:
        return None
    wins = sum(1 for t in trades if t.outcome == "win")
    return wins / len(trades)


def _notify_rollback(result: dict):
    try:
        import asyncio
        from alerts.telegram import send

        asyncio.create_task(send(
            f"🔄 *Auto-Rollback Applied*\n\n"
            f"Parameter: `{result['parameter']}`\n"
            f"Restored to: `{result.get('old_value', '--')}`\n\n"
            f"Post-change WR: `{result.get('post_change_wr', '--')}%`\n"
            f"Trigger threshold: `{result['trigger_wr']}%`\n"
            f"Baseline WR: `{result['baseline_wr']}%`\n"
            f"Trades evaluated: `{result['trades_evaluated']}`\n\n"
            f"_Change did not improve performance — reverted automatically._"
        ))
    except Exception as e:
        log.error("_notify_rollback: %s", e)


def _notify_confirmed(result: dict):
    try:
        import asyncio
        from alerts.telegram import send

        asyncio.create_task(send(
            f"✅ *Adaptation Confirmed*\n\n"
            f"Parameter: `{result['parameter']}`\n"
            f"Post-change WR: `{result.get('post_change_wr', '--')}%`\n"
            f"Baseline WR: `{result['baseline_wr']}%`\n"
            f"Trades evaluated: `{result['trades_evaluated']}`\n\n"
            f"_Change confirmed — performing as expected._"
        ))
    except Exception as e:
        log.error("_notify_confirmed: %s", e)