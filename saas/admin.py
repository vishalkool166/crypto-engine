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
        result = list_all_users(
            limit  = limit,
            offset = offset,
            tier   = tier,
        )
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
            raise HTTPException(
                400,
                f"Invalid tier. Must be one of: {valid_tiers}"
            )

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
        sessions = get_all_sessions_admin(
            user_id = user_id,
            limit   = limit,
        )
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
        return JSONResponse(content={
            "success": True,
            "cleaned": count,
        })
    except Exception as e:
        log.error(f"admin_cleanup_sessions error: {e}")
        raise HTTPException(500, str(e))


@router.get("/admin/stats")
async def admin_stats(request: Request):
    _auth(request)
    try:
        user_stats = get_user_stats()

        with get_session() as db:
            from sqlalchemy import func

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

        return JSONResponse(content={
            "total": total,
            "logs":  result,
        })

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
        from api.routes import _get_system_stats
        import asyncio
        loop   = asyncio.get_running_loop()
        system = await loop.run_in_executor(None, _get_system_stats)
        return JSONResponse(content=system)
    except Exception as e:
        log.error(f"admin_system error: {e}")
        raise HTTPException(500, str(e))