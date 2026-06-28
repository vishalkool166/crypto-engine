import secrets
import logging
from datetime import datetime, timezone, timedelta
from database import get_session, UserSession, User
from config import cfg, TIER_FREE, TIER_PRO, TIER_ELITE, TIER_ADMIN

log = logging.getLogger(__name__)

SESSION_LIMITS = {
    TIER_FREE:  1,
    TIER_PRO:   3,
    TIER_ELITE: 5,
    TIER_ADMIN: 999,
}

SESSION_EXPIRY_DAYS = 7


def _parse_user_agent(user_agent: str) -> dict:
    if not user_agent:
        return {"device": "Unknown", "browser": "Unknown"}

    ua = user_agent.lower()

    if "mobile" in ua or "android" in ua or "iphone" in ua:
        device = "Mobile"
    elif "tablet" in ua or "ipad" in ua:
        device = "Tablet"
    else:
        device = "Desktop"

    if "chrome" in ua and "edg" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "edg" in ua:
        browser = "Edge"
    elif "opera" in ua or "opr" in ua:
        browser = "Opera"
    else:
        browser = "Unknown"

    return {"device": device, "browser": browser}


def create_session(
    user_id:    int,
    tier:       str,
    ip:         str  = None,
    user_agent: str  = None,
) -> str:
    try:
        session_id = secrets.token_hex(32)
        ua_info    = _parse_user_agent(user_agent or "")
        expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)
        limit      = SESSION_LIMITS.get(tier, 1)

        with get_session() as db:
            active_sessions = db.query(UserSession).filter(
                UserSession.user_id  == user_id,
                UserSession.is_active == True,
            ).order_by(UserSession.created_at.asc()).all()

            if len(active_sessions) >= limit:
                to_revoke = active_sessions[:len(active_sessions) - limit + 1]
                for s in to_revoke:
                    s.is_active  = False
                    s.revoked_at = datetime.now(timezone.utc)
                log.info(
                    f"Auto revoked {len(to_revoke)} old session(s) "
                    f"for user {user_id} — limit {limit}"
                )

            new_session = UserSession(
                user_id    = user_id,
                session_id = session_id,
                device     = ua_info["device"],
                browser    = ua_info["browser"],
                ip         = ip,
                created_at = datetime.now(timezone.utc),
                last_active= datetime.now(timezone.utc),
                expires_at = expires_at,
                is_active  = True,
            )
            db.add(new_session)

        log.info(f"Session created for user {user_id} device:{ua_info['device']}")
        return session_id

    except Exception as e:
        log.error(f"create_session error: {e}")
        return secrets.token_hex(32)


def validate_session(session_id: str) -> dict | None:
    if not session_id:
        return None
    try:
        with get_session() as db:
            session = db.query(UserSession).filter(
                UserSession.session_id == session_id,
                UserSession.is_active  == True,
            ).first()

            if not session:
                return None

            now = datetime.now(timezone.utc)

            if session.expires_at:
                expires = session.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if now > expires:
                    session.is_active  = False
                    session.revoked_at = now
                    return None

            session.last_active = now

            user = db.query(User).filter(
                User.id       == session.user_id,
                User.is_active == True,
            ).first()

            if not user:
                return None

            return {
                "user_id":    user.id,
                "email":      user.email,
                "tier":       user.tier,
                "is_admin":   user.is_admin,
                "session_id": session_id,
            }

    except Exception as e:
        log.error(f"validate_session error: {e}")
        return None


def revoke_session(session_id: str, user_id: int = None) -> dict:
    try:
        with get_session() as db:
            query = db.query(UserSession).filter(
                UserSession.session_id == session_id
            )
            if user_id:
                query = query.filter(UserSession.user_id == user_id)

            session = query.first()
            if not session:
                return {"success": False, "reason": "Session not found"}

            session.is_active  = False
            session.revoked_at = datetime.now(timezone.utc)

        log.info(f"Session revoked: {session_id[:16]}...")
        return {"success": True}

    except Exception as e:
        log.error(f"revoke_session error: {e}")
        return {"success": False, "reason": str(e)}


def revoke_all_sessions(user_id: int, except_session: str = None) -> dict:
    try:
        with get_session() as db:
            query = db.query(UserSession).filter(
                UserSession.user_id  == user_id,
                UserSession.is_active == True,
            )
            if except_session:
                query = query.filter(
                    UserSession.session_id != except_session
                )

            sessions = query.all()
            count    = len(sessions)
            now      = datetime.now(timezone.utc)

            for s in sessions:
                s.is_active  = False
                s.revoked_at = now

        log.info(f"Revoked {count} sessions for user {user_id}")
        return {"success": True, "revoked": count}

    except Exception as e:
        log.error(f"revoke_all_sessions error: {e}")
        return {"success": False, "reason": str(e)}


def get_user_sessions(user_id: int) -> list:
    try:
        with get_session() as db:
            sessions = db.query(UserSession).filter(
                UserSession.user_id  == user_id,
                UserSession.is_active == True,
            ).order_by(UserSession.last_active.desc()).all()

            return [{
                "id":          s.id,
                "session_id":  s.session_id[:16] + "...",
                "device":      s.device,
                "browser":     s.browser,
                "ip":          s.ip,
                "created_at":  s.created_at.isoformat()  if s.created_at  else None,
                "last_active": s.last_active.isoformat() if s.last_active else None,
                "expires_at":  s.expires_at.isoformat()  if s.expires_at  else None,
            } for s in sessions]

    except Exception as e:
        log.error(f"get_user_sessions error: {e}")
        return []


def get_all_sessions_admin(
    user_id: int = None,
    limit:   int = 100,
) -> list:
    try:
        with get_session() as db:
            query = db.query(UserSession)
            if user_id:
                query = query.filter(UserSession.user_id == user_id)
            sessions = query.order_by(
                UserSession.last_active.desc()
            ).limit(limit).all()

            return [{
                "id":          s.id,
                "user_id":     s.user_id,
                "session_id":  s.session_id[:16] + "...",
                "device":      s.device,
                "browser":     s.browser,
                "ip":          s.ip,
                "is_active":   s.is_active,
                "created_at":  s.created_at.isoformat()  if s.created_at  else None,
                "last_active": s.last_active.isoformat() if s.last_active else None,
                "revoked_at":  s.revoked_at.isoformat()  if s.revoked_at  else None,
            } for s in sessions]

    except Exception as e:
        log.error(f"get_all_sessions_admin error: {e}")
        return []


def admin_revoke_session(session_id: str) -> dict:
    try:
        with get_session() as db:
            session = db.query(UserSession).filter(
                UserSession.session_id == session_id
            ).first()
            if not session:
                return {"success": False, "reason": "Session not found"}
            session.is_active  = False
            session.revoked_at = datetime.now(timezone.utc)
        log.info(f"Admin revoked session: {session_id[:16]}...")
        return {"success": True}
    except Exception as e:
        log.error(f"admin_revoke_session error: {e}")
        return {"success": False, "reason": str(e)}


def admin_revoke_all_user_sessions(user_id: int) -> dict:
    return revoke_all_sessions(user_id)


def cleanup_expired_sessions():
    try:
        now = datetime.now(timezone.utc)
        with get_session() as db:
            expired = db.query(UserSession).filter(
                UserSession.is_active  == True,
                UserSession.expires_at <= now,
            ).all()
            count = len(expired)
            for s in expired:
                s.is_active  = False
                s.revoked_at = now
        if count:
            log.info(f"Cleaned up {count} expired sessions")
        return count
    except Exception as e:
        log.error(f"cleanup_expired_sessions error: {e}")
        return 0


def get_session_limit(tier: str) -> int:
    return SESSION_LIMITS.get(tier, 1)