import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from saas.middleware import require_admin
from saas.users import (
    list_all_users,
    get_user_stats,
    update_user_tier,
    deactivate_user,
    reactivate_user,
    get_user_by_id,
)
from saas.sessions import (
    get_all_sessions_admin,
    admin_revoke_session,
    admin_revoke_all_user_sessions,
    get_user_sessions,
    cleanup_expired_sessions,
)
from database import get_session, User, Subscription, AuditLog, Signal as SignalModel
from config import TIER_FREE, TIER_PRO, TIER_ELITE, TIER_ADMIN

log    = logging.getLogger(__name__)
router = APIRouter()


def _auth(request: Request):
    from saas.middleware import get_current_user, is_admin
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not is_admin(request):
        raise HTTPException(status_code=404, detail="Not found")
    return user


@router.get("/admin/overview")
async def admin_overview(request: Request):
    _auth(request)
    try:
        user_stats = get_user_stats()

        with get_session() as db:
            total_signals = db.query(SignalModel).count()
            pending       = db.query(SignalModel).filter(
                SignalModel.outcome == "pending"
            ).count()
            wins          = db.query(SignalModel).filter(
                SignalModel.outcome == "win"
            ).count()
            losses        = db.query(SignalModel).filter(
                SignalModel.outcome == "loss"
            ).count()
            closed        = wins + losses
            win_rate      = round(wins / closed * 100, 1) if closed > 0 else 0

            from sqlalchemy import func
            total_pnl = db.query(
                func.sum(SignalModel.pnl)
            ).filter(
                SignalModel.outcome.in_(["win", "loss"])
            ).scalar() or 0.0

            recent_users = db.query(User).order_by(
                User.created_at.desc()
            ).limit(5).all()

            recent_users_list = [{
                "id":         u.id,
                "email":      u.email,
                "name":       u.name,
                "tier":       u.tier,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            } for u in recent_users]

            recent_audit = db.query(AuditLog).order_by(
                AuditLog.timestamp.desc()
            ).limit(10).all()

            recent_audit_list = [{
                "id":        a.id,
                "action":    a.action,
                "source":    a.source,
                "detail":    a.detail,
                "ip":        a.ip,
                "success":   a.success,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            } for a in recent_audit]

        return JSONResponse(content={
            "users":        user_stats,
            "signals": {
                "total":     total_signals,
                "pending":   pending,
                "wins":      wins,
                "losses":    losses,
                "win_rate":  win_rate,
                "total_pnl": round(float(total_pnl), 2),
            },
            "recent_users": recent_users_list,
            "recent_audit": recent_audit_list,
            "timestamp":    datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        log.error(f"admin_overview error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/users")
async def admin_users(
    request: Request,
    limit:   int = 50,
    offset:  int = 0,
    tier:    str = None,
):
    _auth(request)
    try:
        result = list_all_users(limit=limit, offset=offset, tier=tier)
        return JSONResponse(content=result)
    except Exception as e:
        log.error(f"admin_users error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/users/{user_id}")
async def admin_get_user(request: Request, user_id: int):
    _auth(request)
    try:
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found")

        with get_session() as db:
            sub = db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()

            sub_data = None
            if sub:
                sub_data = {
                    "tier":                 sub.tier,
                    "status":               sub.status,
                    "current_period_end":   sub.current_period_end.isoformat() if sub.current_period_end else None,
                    "cancel_at_period_end": sub.cancel_at_period_end,
                }

        sessions = get_user_sessions(user_id)

        return JSONResponse(content={
            "user":         user,
            "subscription": sub_data,
            "sessions":     sessions,
        })

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"admin_get_user error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/users/{user_id}/tier")
async def admin_update_tier(request: Request, user_id: int):
    admin = _auth(request)
    try:
        body     = await request.json()
        new_tier = body.get("tier", "").lower()

        valid_tiers = [TIER_FREE, TIER_PRO, TIER_ELITE, TIER_ADMIN]
        if new_tier not in valid_tiers:
            raise HTTPException(400, f"Invalid tier. Must be one of: {valid_tiers}")

        result = update_user_tier(user_id, new_tier)

        if not result.get("success"):
            raise HTTPException(400, result.get("reason", "Update failed"))

        from auth import audit
        audit(
            action  = "admin_tier_update",
            source  = "admin",
            detail  = f"user:{user_id} tier:{result['old_tier']}→{new_tier}",
            ip      = request.client.host if request.client else "",
            success = True,
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"admin_update_tier error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/users/{user_id}/deactivate")
async def admin_deactivate_user(request: Request, user_id: int):
    _auth(request)
    try:
        admin_revoke_all_user_sessions(user_id)

        result = deactivate_user(user_id)
        if not result.get("success"):
            raise HTTPException(400, result.get("reason", "Failed"))

        from auth import audit
        audit(
            action  = "admin_deactivate_user",
            source  = "admin",
            detail  = f"user:{user_id}",
            ip      = request.client.host if request.client else "",
            success = True,
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"admin_deactivate_user error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/users/{user_id}/reactivate")
async def admin_reactivate_user(request: Request, user_id: int):
    _auth(request)
    try:
        result = reactivate_user(user_id)
        if not result.get("success"):
            raise HTTPException(400, result.get("reason", "Failed"))

        from auth import audit
        audit(
            action  = "admin_reactivate_user",
            source  = "admin",
            detail  = f"user:{user_id}",
            ip      = request.client.host if request.client else "",
            success = True,
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"admin_reactivate_user error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/sessions")
async def admin_get_sessions(
    request: Request,
    user_id: int = None,
    limit:   int = 100,
):
    _auth(request)
    try:
        sessions = get_all_sessions_admin(user_id=user_id, limit=limit)
        return JSONResponse(content={"sessions": sessions})
    except Exception as e:
        log.error(f"admin_get_sessions error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/sessions/{session_id}/revoke")
async def admin_revoke_session_endpoint(request: Request, session_id: str):
    _auth(request)
    try:
        result = admin_revoke_session(session_id)
        if not result.get("success"):
            raise HTTPException(400, result.get("reason", "Failed"))

        from auth import audit
        audit(
            action  = "admin_revoke_session",
            source  = "admin",
            detail  = f"session:{session_id[:16]}...",
            ip      = request.client.host if request.client else "",
            success = True,
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"admin_revoke_session error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/users/{user_id}/sessions/revoke-all")
async def admin_revoke_all_sessions(request: Request, user_id: int):
    _auth(request)
    try:
        result = admin_revoke_all_user_sessions(user_id)

        from auth import audit
        audit(
            action  = "admin_revoke_all_sessions",
            source  = "admin",
            detail  = f"user:{user_id} revoked:{result.get('revoked', 0)}",
            ip      = request.client.host if request.client else "",
            success = True,
        )

        return JSONResponse(content=result)

    except Exception as e:
        log.error(f"admin_revoke_all_sessions error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/sessions/cleanup")
async def admin_cleanup_sessions(request: Request):
    _auth(request)
    try:
        count = cleanup_expired_sessions()
        return JSONResponse(content={"success": True, "cleaned": count})
    except Exception as e:
        log.error(f"admin_cleanup_sessions error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/stats")
async def admin_stats(request: Request):
    _auth(request)
    try:
        user_stats = get_user_stats()

        with get_session() as db:
            now   = datetime.now(timezone.utc)
            week  = now - timedelta(days=7)
            month = now - timedelta(days=30)

            signups_week = db.query(User).filter(
                User.created_at >= week
            ).count()

            signups_month = db.query(User).filter(
                User.created_at >= month
            ).count()

            active_subs = db.query(Subscription).filter(
                Subscription.status == "active",
                Subscription.tier.in_([TIER_PRO, TIER_ELITE])
            ).count()

            pro_count   = db.query(User).filter(User.tier == TIER_PRO).count()
            elite_count = db.query(User).filter(User.tier == TIER_ELITE).count()

            from config import TIER_PRICING
            mrr = (
                pro_count   * TIER_PRICING[TIER_PRO]["price_monthly"] +
                elite_count * TIER_PRICING[TIER_ELITE]["price_monthly"]
            )

            from database import UserSession
            active_sessions = db.query(UserSession).filter(
                UserSession.is_active == True
            ).count()

        return JSONResponse(content={
            "users":           user_stats,
            "signups_week":    signups_week,
            "signups_month":   signups_month,
            "active_subs":     active_subs,
            "mrr_estimate":    mrr,
            "pro_count":       pro_count,
            "elite_count":     elite_count,
            "active_sessions": active_sessions,
            "timestamp":       now.isoformat(),
        })

    except Exception as e:
        log.error(f"admin_stats error: {e}")
        raise HTTPException(500, str(e))

@router.get("/admin/demo/stats")
async def admin_demo_stats(request: Request):
    _auth(request)
    try:
        from database import DemoVisit
        from sqlalchemy import func
        from datetime import datetime, timezone, timedelta

        now   = datetime.now(timezone.utc)
        day   = now - timedelta(days=1)
        week  = now - timedelta(days=7)
        month = now - timedelta(days=30)

        with get_session() as db:
            total        = db.query(DemoVisit).count()
            last_24h     = db.query(DemoVisit).filter(DemoVisit.visited_at >= day).count()
            last_7d      = db.query(DemoVisit).filter(DemoVisit.visited_at >= week).count()
            last_30d     = db.query(DemoVisit).filter(DemoVisit.visited_at >= month).count()
            cta_clicks   = db.query(DemoVisit).filter(DemoVisit.cta_clicked == True).count()
            mobile_count = db.query(DemoVisit).filter(DemoVisit.device == "mobile").count()

            tier_rows = db.query(
                DemoVisit.tier_explored,
                func.count(DemoVisit.id).label("count")
            ).group_by(DemoVisit.tier_explored).all()

            tier_breakdown = {row.tier_explored: row.count for row in tier_rows}

            avg_duration = db.query(
                func.avg(DemoVisit.duration_secs)
            ).filter(
                DemoVisit.duration_secs != None,
                DemoVisit.duration_secs > 0
            ).scalar() or 0

            recent = db.query(DemoVisit).order_by(
                DemoVisit.visited_at.desc()
            ).limit(20).all()

            recent_list = [{
                "id":            v.id,
                "visited_at":    v.visited_at.isoformat() if v.visited_at else None,
                "device":        v.device,
                "browser":       v.browser,
                "tier_explored": v.tier_explored,
                "cta_clicked":   v.cta_clicked,
                "duration_secs": v.duration_secs,
                "referrer":      v.referrer,
            } for v in recent]

        conversion_rate = round(cta_clicks / total * 100, 1) if total > 0 else 0

        return JSONResponse(content={
            "total":            total,
            "last_24h":         last_24h,
            "last_7d":          last_7d,
            "last_30d":         last_30d,
            "cta_clicks":       cta_clicks,
            "conversion_rate":  conversion_rate,
            "mobile_count":     mobile_count,
            "desktop_count":    total - mobile_count,
            "avg_duration_secs": round(float(avg_duration)),
            "tier_breakdown":   tier_breakdown,
            "recent":           recent_list,
            "timestamp":        now.isoformat(),
        })

    except Exception as e:
        log.error(f"admin_demo_stats error: {e}")
        raise HTTPException(500, str(e))

@router.get("/admin/audit")
async def admin_audit(
    request: Request,
    limit:   int = 100,
    offset:  int = 0,
):
    _auth(request)
    try:
        with get_session() as db:
            total = db.query(AuditLog).count()
            logs  = db.query(AuditLog).order_by(
                AuditLog.timestamp.desc()
            ).offset(offset).limit(limit).all()

            result = [{
                "id":        a.id,
                "action":    a.action,
                "source":    a.source,
                "detail":    a.detail,
                "ip":        a.ip,
                "success":   a.success,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            } for a in logs]

        return JSONResponse(content={"total": total, "logs": result})

    except Exception as e:
        log.error(f"admin_audit error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/pricing")
async def admin_get_pricing(request: Request):
    _auth(request)
    try:
        from saas.tiers import get_pricing_data
        return JSONResponse(content=get_pricing_data())
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/admin/system")
async def admin_system(request: Request):
    _auth(request)
    try:
        from api.routes import _system_stats
        import asyncio
        loop   = asyncio.get_running_loop()
        system = await loop.run_in_executor(None, _system_stats)
        return JSONResponse(content=system)
    except Exception as e:
        log.error(f"admin_system error: {e}")
        raise HTTPException(500, str(e))


# ─── ML / Adaptation Routes ──────────────────────────────────────────────────

@router.get("/admin/adaptations/history")
async def adaptation_history(request: Request, limit: int = 20):
    _auth(request)
    try:
        from ml.adapter import get_adaptation_history
        return JSONResponse(content=get_adaptation_history(limit=limit))
    except Exception as e:
        log.error(f"adaptation_history error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/adaptations/pending")
async def adaptation_pending(request: Request):
    _auth(request)
    try:
        from ml.analyzer import get_pending_recommendations
        return JSONResponse(content=get_pending_recommendations())
    except Exception as e:
        log.error(f"adaptation_pending error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/adaptations/{rec_id}/approve")
async def adaptation_approve(request: Request, rec_id: int):
    _auth(request)
    try:
        from ml.analyzer import approve_recommendation
        success = approve_recommendation(rec_id, approved_by="dashboard")
        if not success:
            raise HTTPException(404, f"Recommendation {rec_id} not found")

        from auth import audit
        audit(
            action  = "adaptation_approve",
            source  = "dashboard",
            detail  = f"rec_id:{rec_id}",
            ip      = request.client.host if request.client else "",
            success = True,
        )

        return JSONResponse(content={"success": True, "rec_id": rec_id})

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"adaptation_approve error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/adaptations/{rec_id}/reject")
async def adaptation_reject(request: Request, rec_id: int):
    _auth(request)
    try:
        body   = await request.json()
        reason = body.get("reason", "rejected_via_dashboard")

        from ml.analyzer import reject_recommendation
        success = reject_recommendation(rec_id, reason=reason)
        if not success:
            raise HTTPException(404, f"Recommendation {rec_id} not found")

        from auth import audit
        audit(
            action  = "adaptation_reject",
            source  = "dashboard",
            detail  = f"rec_id:{rec_id} reason:{reason}",
            ip      = request.client.host if request.client else "",
            success = True,
        )

        return JSONResponse(content={"success": True, "rec_id": rec_id})

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"adaptation_reject error: {e}")
        raise HTTPException(500, str(e))


@router.post("/admin/adaptations/rollback")
async def adaptation_rollback(request: Request):
    _auth(request)
    try:
        body      = await request.json()
        parameter = body.get("parameter", "")

        if not parameter:
            raise HTTPException(400, "parameter required")

        from ml.rollback_manager import manual_rollback
        result = manual_rollback(parameter, reason="manual_dashboard")

        if not result.get("success"):
            raise HTTPException(400, result.get("reason", "Rollback failed"))

        from auth import audit
        audit(
            action  = "adaptation_rollback",
            source  = "dashboard",
            detail  = f"parameter:{parameter}",
            ip      = request.client.host if request.client else "",
            success = True,
        )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"adaptation_rollback error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/adaptations/checkpoints")
async def adaptation_checkpoints(request: Request):
    _auth(request)
    try:
        from ml.rollback_manager import get_pending_checkpoints
        return JSONResponse(content=get_pending_checkpoints())
    except Exception as e:
        log.error(f"adaptation_checkpoints error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/adaptations/versions")
async def adaptation_versions(request: Request, limit: int = 10):
    _auth(request)
    try:
        from ml.version_registry import get_version_history
        return JSONResponse(content=get_version_history(limit=limit))
    except Exception as e:
        log.error(f"adaptation_versions error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/adaptations/performance/version")
async def adaptation_perf_version(request: Request):
    _auth(request)
    try:
        from ml.version_registry import get_performance_by_version
        return JSONResponse(content=get_performance_by_version())
    except Exception as e:
        log.error(f"adaptation_perf_version error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/adaptations/performance/regime")
async def adaptation_perf_regime(request: Request):
    _auth(request)
    try:
        from ml.regime_classifier import get_regime_performance
        data = get_regime_performance(min_trades=1)
        result = []
        for regime, stats in data.items():
            result.append({
                "regime":   regime,
                "total":    stats.get("total",    0),
                "wins":     stats.get("wins",     0),
                "losses":   stats.get("losses",   0),
                "win_rate": stats.get("win_rate", 0),
                "pnl":      stats.get("pnl",      0),
                "action":   stats.get("action",   "normal"),
            })
        result.sort(key=lambda x: x["win_rate"], reverse=True)
        return JSONResponse(content=result)
    except Exception as e:
        log.error(f"adaptation_perf_regime error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/adaptations/parameters")
async def adaptation_parameters(request: Request):
    _auth(request)
    try:
        from config import cfg
        SE = cfg.SCALP_ENGINE
        return JSONResponse(content={
            "sweep_min_score":       SE.get("sweep_min_score",       0.30),
            "zone_min_score":        SE.get("zone_min_score",        0.40),
            "grade_a_threshold":     SE.get("grade_a_threshold",     0.65),
            "grade_aplus_threshold": SE.get("grade_aplus_threshold", 0.80),
            "grade_b_threshold":     SE.get("grade_b_threshold",     0.50),
            "sweep_max_age_hours":   SE.get("sweep_max_age_hours",   12),
            "sweep_min_wick_atr":    SE.get("sweep_min_wick_atr",    0.2),
            "zone_min_width_atr":    SE.get("zone_min_width_atr",    0.15),
            "zone_max_dist_pct":     SE.get("zone_max_dist_pct",     4.0),
            "zone_max_touches":      SE.get("zone_max_touches",      2),
            "trigger_min_score":     SE.get("trigger_min_score",     0.6),
            "base_risk_pct":         SE.get("base_risk_pct",         0.01),
            "max_risk_pct":          SE.get("max_risk_pct",          0.02),
            "min_risk_pct":          SE.get("min_risk_pct",          0.005),
            "daily_loss_limit_pct":  SE.get("daily_loss_limit_pct",  0.02),
            "max_open_trades":       SE.get("max_open_trades",       3),
            "max_leverage":          SE.get("max_leverage",          15),
            "tp1_min_rr":            SE.get("tp1_min_rr",            1.5),
            "tp2_min_rr":            SE.get("tp2_min_rr",            2.5),
            "system_version":        cfg.SYSTEM_VERSION,
            "adaptation_frozen":     cfg.ADAPTATION_FROZEN,
            "ml_enabled":            cfg.ML_ENABLED,
            "trading_mode":          cfg.TRADING_MODE,
        })
    except Exception as e:
        log.error(f"adaptation_parameters error: {e}")
        raise HTTPException(500, str(e))