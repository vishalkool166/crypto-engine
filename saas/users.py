import hashlib
import secrets
import logging
from datetime import datetime, timezone
from database import get_session, User, Subscription, ApiKey
from config import cfg, TIER_FREE, TIER_ADMIN

log = logging.getLogger(__name__)


def create_or_get_user(
    email:       str,
    name:        str  = None,
    avatar:      str  = None,
    provider:    str  = "google",
    provider_id: str  = None,
) -> dict:
    try:
        with get_session() as db:
            user = db.query(User).filter(User.email == email).first()

            if user:
                user.last_seen  = datetime.now(timezone.utc)
                user.last_login = datetime.now(timezone.utc)
                if name   and not user.name:   user.name   = name
                if avatar and not user.avatar: user.avatar = avatar
                if provider_id and not user.provider_id:
                    user.provider_id = provider_id

                is_first_time = False

            else:
                is_admin = cfg.is_admin_email(email)
                tier     = TIER_ADMIN if is_admin else TIER_FREE

                user = User(
                    email       = email,
                    name        = name,
                    avatar      = avatar,
                    provider    = provider,
                    provider_id = provider_id,
                    tier        = tier,
                    is_admin    = is_admin,
                    is_active   = True,
                    onboarded   = False,
                    created_at  = datetime.now(timezone.utc),
                    last_seen   = datetime.now(timezone.utc),
                    last_login  = datetime.now(timezone.utc),
                )
                db.add(user)
                db.flush()
                db.refresh(user)

                sub = Subscription(
                    user_id    = user.id,
                    tier       = tier,
                    status     = "active",
                    created_at = datetime.now(timezone.utc),
                    updated_at = datetime.now(timezone.utc),
                )
                db.add(sub)

                is_first_time = True
                log.info(f"New user created: {email} tier:{tier}")

            return {
                "id":          user.id,
                "email":       user.email,
                "name":        user.name,
                "avatar":      user.avatar,
                "tier":        user.tier,
                "is_admin":    user.is_admin,
                "is_active":   user.is_active,
                "onboarded":   user.onboarded,
                "is_new":      is_first_time,
                "created_at":  user.created_at.isoformat() if user.created_at else None,
            }

    except Exception as e:
        log.error(f"create_or_get_user error: {e}")
        raise


def get_user_by_id(user_id: int) -> dict | None:
    try:
        with get_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            return _user_to_dict(user)
    except Exception as e:
        log.error(f"get_user_by_id error: {e}")
        return None


def get_user_by_email(email: str) -> dict | None:
    try:
        with get_session() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return None
            return _user_to_dict(user)
    except Exception as e:
        log.error(f"get_user_by_email error: {e}")
        return None


def update_user_tier(user_id: int, new_tier: str) -> dict:
    try:
        with get_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "reason": "User not found"}

            old_tier   = user.tier
            user.tier  = new_tier

            if new_tier == TIER_ADMIN:
                user.is_admin = True
            elif old_tier == TIER_ADMIN and new_tier != TIER_ADMIN:
                if not cfg.is_admin_email(user.email):
                    user.is_admin = False

            sub = db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()

            if sub:
                sub.tier       = new_tier
                sub.updated_at = datetime.now(timezone.utc)
            else:
                db.add(Subscription(
                    user_id    = user_id,
                    tier       = new_tier,
                    status     = "active",
                    created_at = datetime.now(timezone.utc),
                    updated_at = datetime.now(timezone.utc),
                ))

            log.info(f"User {user_id} tier updated: {old_tier} → {new_tier}")

            return {
                "success":   True,
                "user_id":   user_id,
                "old_tier":  old_tier,
                "new_tier":  new_tier,
            }

    except Exception as e:
        log.error(f"update_user_tier error: {e}")
        return {"success": False, "reason": str(e)}


def mark_user_onboarded(user_id: int):
    try:
        with get_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.onboarded = True
    except Exception as e:
        log.error(f"mark_user_onboarded error: {e}")


def deactivate_user(user_id: int) -> dict:
    try:
        with get_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "reason": "User not found"}
            user.is_active = False
            log.info(f"User deactivated: {user_id}")
            return {"success": True}
    except Exception as e:
        log.error(f"deactivate_user error: {e}")
        return {"success": False, "reason": str(e)}


def reactivate_user(user_id: int) -> dict:
    try:
        with get_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "reason": "User not found"}
            user.is_active = True
            log.info(f"User reactivated: {user_id}")
            return {"success": True}
    except Exception as e:
        log.error(f"reactivate_user error: {e}")
        return {"success": False, "reason": str(e)}


def list_all_users(
    limit:  int = 100,
    offset: int = 0,
    tier:   str = None,
) -> dict:
    try:
        with get_session() as db:
            query = db.query(User)
            if tier:
                query = query.filter(User.tier == tier)
            total = query.count()
            users = query.order_by(
                User.created_at.desc()
            ).offset(offset).limit(limit).all()

            return {
                "total": total,
                "users": [_user_to_dict(u) for u in users],
            }
    except Exception as e:
        log.error(f"list_all_users error: {e}")
        return {"total": 0, "users": []}


def get_user_stats() -> dict:
    try:
        with get_session() as db:
            total    = db.query(User).count()
            active   = db.query(User).filter(User.is_active == True).count()
            by_tier  = {}

            from config import TIER_FREE, TIER_PRO, TIER_ELITE, TIER_ADMIN
            for tier in [TIER_FREE, TIER_PRO, TIER_ELITE, TIER_ADMIN]:
                by_tier[tier] = db.query(User).filter(
                    User.tier == tier
                ).count()

            today = datetime.now(timezone.utc).date()
            new_today = db.query(User).filter(
                User.created_at >= datetime(
                    today.year, today.month, today.day,
                    tzinfo=timezone.utc
                )
            ).count()

            return {
                "total":     total,
                "active":    active,
                "new_today": new_today,
                "by_tier":   by_tier,
            }
    except Exception as e:
        log.error(f"get_user_stats error: {e}")
        return {}


def create_api_key_for_user(user_id: int, name: str = "Default") -> dict:
    try:
        from auth import generate_api_key
        raw, hashed, prefix = generate_api_key()

        with get_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "reason": "User not found"}

            existing = db.query(ApiKey).filter(
                ApiKey.user_id   == user_id,
                ApiKey.is_active == True
            ).count()

            if existing >= 3:
                return {
                    "success": False,
                    "reason":  "Maximum 3 active API keys allowed"
                }

            api_key = ApiKey(
                user_id    = user_id,
                key_hash   = hashed,
                key_prefix = prefix,
                name       = name,
                tier       = user.tier,
                is_active  = True,
                created_at = datetime.now(timezone.utc),
            )
            db.add(api_key)
            db.flush()
            db.refresh(api_key)

            log.info(f"API key created for user {user_id}: {prefix}...")

            return {
                "success":    True,
                "key":        raw,
                "prefix":     prefix,
                "name":       name,
                "created_at": api_key.created_at.isoformat(),
            }

    except Exception as e:
        log.error(f"create_api_key error: {e}")
        return {"success": False, "reason": str(e)}


def list_api_keys(user_id: int) -> list:
    try:
        with get_session() as db:
            keys = db.query(ApiKey).filter(
                ApiKey.user_id   == user_id,
                ApiKey.is_active == True
            ).all()
            return [{
                "id":         k.id,
                "prefix":     k.key_prefix,
                "name":       k.name,
                "last_used":  k.last_used.isoformat() if k.last_used else None,
                "created_at": k.created_at.isoformat() if k.created_at else None,
            } for k in keys]
    except Exception as e:
        log.error(f"list_api_keys error: {e}")
        return []


def revoke_api_key(key_id: int, user_id: int) -> dict:
    try:
        with get_session() as db:
            key = db.query(ApiKey).filter(
                ApiKey.id      == key_id,
                ApiKey.user_id == user_id
            ).first()
            if not key:
                return {"success": False, "reason": "Key not found"}
            key.is_active = False
            return {"success": True}
    except Exception as e:
        log.error(f"revoke_api_key error: {e}")
        return {"success": False, "reason": str(e)}


def _user_to_dict(user: User) -> dict:
    return {
        "id":          user.id,
        "email":       user.email,
        "name":        user.name,
        "avatar":      user.avatar,
        "provider":    user.provider,
        "tier":        user.tier,
        "is_admin":    user.is_admin,
        "is_active":   user.is_active,
        "onboarded":   user.onboarded,
        "created_at":  user.created_at.isoformat() if user.created_at else None,
        "last_seen":   user.last_seen.isoformat()  if user.last_seen  else None,
        "last_login":  user.last_login.isoformat() if user.last_login else None,
    }