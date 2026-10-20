"""SaaS personal API key authentication and least-privilege policy."""
import hashlib
from datetime import datetime, timezone

from config import TIER_ELITE
from database import ApiKey, User
import database

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def authenticate_personal_api_key(request) -> dict | None:
    """Authenticate a user key without granting owner administrator rights."""
    key = request.headers.get("X-API-Key", "")
    if not key or not key.startswith("se_"):
        return None
    if getattr(request, "method", "GET").upper() not in SAFE_METHODS:
        return None

    try:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        with database.get_session() as db:
            api_key = db.query(ApiKey).filter(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            ).first()
            if not api_key:
                return None
            if api_key.expires_at:
                expiry = api_key.expires_at
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry <= datetime.now(timezone.utc):
                    return None
            user = db.query(User).filter(User.id == api_key.user_id).first()
            if not user or not user.is_active:
                return None
            api_key.last_used = datetime.now(timezone.utc)
            return {
                "sub": str(user.id),
                "email": user.email,
                "tier": TIER_ELITE if user.tier == "admin" else user.tier,
                "is_admin": False,
                "type": "api_key",
            }
    except Exception:
        return None
