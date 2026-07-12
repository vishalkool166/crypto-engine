import logging
from alerts.telegram.client     import send
from alerts.telegram.formatters import now_ist
from config import cfg

log = logging.getLogger(__name__)


async def cmd_ml() -> None:
    from ml.eligibility import get_ml_status
    s            = get_ml_status()
    closed       = s.get("closed_trades", 0)
    required     = s.get("required", 100)
    pct          = min(100, int(closed / required * 100))
    bar          = "█" * (pct // 10) + "░" * (10 - pct // 10)
    top_features = s.get("top_features", [])
    top_str      = (
        "\n*Top Features:*\n" + "\n".join(
            f"  `{f['feature']}` — `{f['importance']}`"
            for f in top_features[:3]
        )
        if top_features else ""
    )
    await send(
        f"🤖 *ML Status*\n\n"
        f"Status: `{'✅ ACTIVE' if s.get('ml_enabled') else '⏳ Collecting data'}`\n\n"
        f"Progress: `{closed}/{required}` trades\n"
        f"`{bar}` {pct}%\n\n"
        f"{s.get('message', '')}\n"
        f"{top_str}\n\n"
        f"Grades: `{', '.join(cfg.MIN_GRADE_TO_TRADE)}`\n"
        f"Auto-trains at: `{required}` · Retrains every: `50 new trades`"
    )


async def cmd_adaptations() -> None:
    try:
        from ml.adapter          import get_adaptation_history
        from ml.analyzer         import get_pending_recommendations
        from ml.rollback_manager import get_pending_checkpoints
        from ml.safety_checks    import get_safety_summary

        history     = get_adaptation_history(limit=5)
        pending     = get_pending_recommendations()
        checkpoints = get_pending_checkpoints()
        safety      = get_safety_summary()

        lines = [f"🧠 *Adaptation Status*\n_{now_ist()}_\n"]

        frozen_str = "🔴 FROZEN" if cfg.ADAPTATION_FROZEN else "🟢 Active"
        lines.append(f"Status: `{frozen_str}`")
        lines.append(
            f"Changes this month: "
            f"`{safety.get('changes_this_month', 0)}/{safety.get('max_changes_month', 3)}`"
        )
        lines.append(
            f"Total trades: "
            f"`{safety.get('total_trades', 0)}/{safety.get('min_trades_required', 50)}`"
        )
        lines.append(
            f"Approval required: "
            f"`{'Yes' if safety.get('require_approval') else 'No'}`\n"
        )

        if pending:
            lines.append(f"*{len(pending)} Pending Recommendations:*")
            for r in pending[:3]:
                direction = "📈" if r["direction"] == "increase" else "📉"
                lines.append(
                    f"{direction} `{r['parameter']}`: "
                    f"`{r['current_value']}` → `{r['recommended_value']}` "
                    f"(+{r.get('expected_improvement', 0):.1f}% WR) "
                    f"[{r.get('confidence', 'low')}]"
                )
            lines.append(f"\n_Use `/approve ID` or `/reject ID` to action._\n")

        if checkpoints:
            lines.append(f"*{len(checkpoints)} Active Checkpoints:*")
            for c in checkpoints[:3]:
                lines.append(
                    f"• `{c['parameter']}`: "
                    f"{c['trades_remaining']} trades until review"
                )
            lines.append("")

        if history:
            lines.append(f"*Recent Changes:*")
            for h in history[:3]:
                rolled = " ↩️ rolled back" if h.get("rolled_back") else ""
                lines.append(
                    f"• `{h['parameter']}`: "
                    f"`{h['old_value']}` → `{h['new_value']}`{rolled}"
                )

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_adaptations: %s", e)
        await send("❌ Could not fetch adaptation status.")


async def cmd_freeze() -> None:
    try:
        cfg.freeze_adaptations()
        await send(
            f"🔴 *Adaptations Frozen*\n\n"
            f"All automatic parameter changes are paused.\n"
            f"Use /unfreeze to resume."
        )
    except Exception as e:
        log.error("cmd_freeze: %s", e)
        await send("❌ Could not freeze adaptations.")


async def cmd_unfreeze() -> None:
    try:
        cfg.unfreeze_adaptations()
        await send(
            f"🟢 *Adaptations Resumed*\n\n"
            f"Automatic parameter changes are now active.\n"
            f"Next analysis: Sunday 00:00 UTC"
        )
    except Exception as e:
        log.error("cmd_unfreeze: %s", e)
        await send("❌ Could not unfreeze adaptations.")


async def cmd_rollback(parameter: str) -> None:
    try:
        from ml.rollback_manager import manual_rollback
        result = manual_rollback(parameter, reason="manual_telegram")
        if result.get("success"):
            await send(
                f"↩️ *Rollback Applied*\n\n"
                f"Parameter: `{parameter}`\n"
                f"Restored to: `{result.get('restored')}`\n"
                f"From: `{result.get('from')}`\n\n"
                f"System version updated."
            )
        else:
            await send(
                f"❌ *Rollback Failed*\n\n"
                f"Parameter: `{parameter}`\n"
                f"Reason: `{result.get('reason', 'Unknown error')}`"
            )
    except Exception as e:
        log.error("cmd_rollback %s: %s", parameter, e)
        await send(f"❌ Rollback failed: `{e}`")


async def cmd_approve(rec_id_str: str) -> None:
    try:
        rec_id = int(rec_id_str)
        from ml.analyzer import approve_recommendation
        success = approve_recommendation(rec_id, approved_by="telegram")
        if success:
            await send(
                f"✅ *Recommendation #{rec_id} Approved*\n\n"
                f"Will be applied in next adapter run (Sunday 01:00 UTC)\n"
                f"or use /analysis to trigger now."
            )
        else:
            await send(f"❌ Recommendation #{rec_id} not found.")
    except ValueError:
        await send("⚠️ Usage: `/approve 5`")
    except Exception as e:
        log.error("cmd_approve: %s", e)
        await send(f"❌ Approve failed: `{e}`")


async def cmd_reject(rec_id_str: str) -> None:
    try:
        rec_id = int(rec_id_str)
        from ml.analyzer import reject_recommendation
        success = reject_recommendation(rec_id, reason="rejected_via_telegram")
        if success:
            await send(f"🚫 *Recommendation #{rec_id} Rejected*")
        else:
            await send(f"❌ Recommendation #{rec_id} not found.")
    except ValueError:
        await send("⚠️ Usage: `/reject 5`")
    except Exception as e:
        log.error("cmd_reject: %s", e)
        await send(f"❌ Reject failed: `{e}`")


async def cmd_version() -> None:
    try:
        from ml.version_registry import get_current_version_record, get_version_history
        current = get_current_version_record()
        history = get_version_history(limit=5)

        SE    = cfg.SCALP_ENGINE
        lines = [
            f"⚙️ *System Version*\n",
            f"Current: `{cfg.SYSTEM_VERSION}`\n",
            f"*Active Parameters:*",
            f"sweep_min_score:       `{SE.get('sweep_min_score', 0.30)}`",
            f"zone_min_score:        `{SE.get('zone_min_score', 0.40)}`",
            f"grade_a_threshold:     `{SE.get('grade_a_threshold', 0.65)}`",
            f"grade_aplus_threshold: `{SE.get('grade_aplus_threshold', 0.80)}`",
            f"sweep_max_age_hours:   `{SE.get('sweep_max_age_hours', 12)}`",
            f"base_risk_pct:         `{SE.get('base_risk_pct', 0.01)}`",
            f"",
        ]

        if history and len(history) > 1:
            lines.append(f"*Version History (last {min(5, len(history))}):*")
            for v in history[:5]:
                current_marker = " ← current" if v.get("is_current") else ""
                lines.append(
                    f"• `{v['version']}`{current_marker} — "
                    f"_{v.get('change_reason', '')[:50]}_"
                )

        await send("\n".join(lines))

    except Exception as e:
        log.error("cmd_version: %s", e)
        await send("❌ Could not fetch version info.")


async def cmd_analysis() -> None:
    await send("⏳ *Running analysis...*\n\nThis may take a moment.")
    try:
        from ml.analyzer import run
        result = run()
        status = result.get("status", "unknown")
        if status == "insufficient_data":
            await send(
                f"📊 *Analysis Complete*\n\n"
                f"Status: `Insufficient data`\n"
                f"Trades: `{result.get('total_trades', 0)}/{result.get('min_required', 50)}`\n\n"
                f"_Keep trading — analysis activates at "
                f"{result.get('min_required', 50)} closed trades._"
            )
            return
        recs = result.get("recommendations", [])
        await send(
            f"✅ *Analysis Complete*\n\n"
            f"Trades analyzed: `{result.get('total_trades', 0)}`\n"
            f"Recommendations: `{len(recs)}`\n\n"
            f"_Use /adaptations to review recommendations._"
        )
    except Exception as e:
        log.error("cmd_analysis: %s", e)
        await send(f"❌ Analysis failed: `{e}`")