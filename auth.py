"""Operator authentication helpers and audited step-up verification."""

import hashlib
import logging
import re
import pyotp
from config import cfg

log = logging.getLogger(__name__)


def is_authenticated(request):
    from operator_auth import current_operator

    return current_operator(request) is not None


def get_current_user_any(request):
    from operator_auth import current_operator

    return current_operator(request)


def is_admin_user(user):
    return bool(
        user
        and user.get("type") == "operator"
        and cfg.is_admin_email(user.get("email", ""))
    )


def verify_totp(code):
    if (
        not cfg.TOTP_SECRET
        or not isinstance(code, str)
        or not re.fullmatch(r"\d{6}", code)
    ):
        return False
    try:
        if not pyotp.TOTP(cfg.TOTP_SECRET).verify(code, valid_window=1):
            return False
        from redis_client import get_redis

        redis = get_redis()
        if redis is None:
            return False
        key = hashlib.sha256((cfg.TOTP_SECRET + code).encode()).hexdigest()
        return bool(redis.set("operator:stepup:" + key, "used", ex=90, nx=True))
    except Exception:
        log.warning("Step-up verification unavailable")
        return False


def audit(action, source, detail="", ip="", success=True):
    from database import get_session, AuditLog

    try:
        with get_session() as db:
            db.add(
                AuditLog(
                    action=str(action)[:120],
                    source=str(source)[:120],
                    detail=str(detail)[:2048],
                    ip=str(ip)[:128],
                    success=bool(success),
                )
            )
    except Exception:
        log.error("Audit record could not be persisted")
