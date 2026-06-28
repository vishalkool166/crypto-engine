import logging
from fastapi import HTTPException, Request
from functools import wraps
from config import cfg, tier_meets_minimum, TIER_FREE, TIER_PRO, TIER_ELITE, TIER_ADMIN
from auth import get_current_user_any, is_admin_user

log = logging.getLogger(__name__)


def get_current_user(request: Request) -> dict | None:
    user = get_current_user_any(request)
    if not user:
        return None

    session_id = user.get("session_id")
    if session_id:
        try:
            from saas.sessions import validate_session
            session_data = validate_session(session_id)
            if not session_data:
                return None
            user["tier"]     = session_data["tier"]
            user["is_admin"] = session_data["is_admin"]
        except Exception as e:
            log.warning(f"Session validation error: {e}")

    return user


def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_tier(minimum_tier: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = get_current_user(request)
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            user_tier = user.get("tier", TIER_FREE)
            if not tier_meets_minimum(user_tier, minimum_tier):
                raise HTTPException(
                    status_code = 403,
                    detail      = {
                        "code":          "upgrade_required",
                        "message":       f"This feature requires {minimum_tier} tier or higher",
                        "required_tier": minimum_tier,
                        "current_tier":  user_tier,
                    }
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_admin(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = get_current_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Authentication required")
        if not is_admin_user(user):
            raise HTTPException(status_code=404, detail="Not found")
        return await func(request, *args, **kwargs)
    return wrapper


def get_user_tier(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        return TIER_FREE
    return user.get("tier", TIER_FREE)


def is_admin(request: Request) -> bool:
    user = get_current_user(request)
    if not user:
        return False
    return is_admin_user(user)


def check_feature_access(request: Request, feature: str) -> bool:
    from config import tier_has_feature
    tier = get_user_tier(request)
    return tier_has_feature(tier, feature)


def get_user_id(request: Request) -> int | None:
    user = get_current_user(request)
    if not user:
        return None
    try:
        return int(user.get("sub", 0)) or None
    except Exception:
        return None