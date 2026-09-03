import logging
import time
import json
import pyotp
from config import cfg

log = logging.getLogger(__name__)

_api        = None
_session_at = 0.0
_SESSION_TTL = 20 * 3600

_REDIS_SESSION_KEY = "indian:session:token"
_REDIS_SESSION_AT  = "indian:session:at"


def _get_redis():
    try:
        from redis_client import get_redis
        return get_redis()
    except Exception:
        return None


def _save_session_to_redis():
    try:
        r = _get_redis()
        if not r:
            return
        r.setex(_REDIS_SESSION_AT, int(_SESSION_TTL), str(_session_at))
        log.info("AngelOne session timestamp saved to Redis")
    except Exception as e:
        log.warning("Could not save session to Redis: %s", e)


def _load_session_from_redis() -> bool:
    global _session_at
    try:
        r = _get_redis()
        if not r:
            return False
        at = r.get(_REDIS_SESSION_AT)
        if not at:
            return False
        saved_at = float(at)
        age      = time.time() - saved_at
        if age > _SESSION_TTL:
            log.info("Redis session too old (%.1f hours) — will re-login", age / 3600)
            return False
        _session_at = saved_at
        log.info("Session timestamp loaded from Redis (age: %.1f hours)", age / 3600)
        return True
    except Exception as e:
        log.warning("Could not load session from Redis: %s", e)
        return False


def _login() -> bool:
    global _api, _session_at
    try:
        from SmartApi import SmartConnect

        if not cfg.ANGELONE_CLIENT_ID:
            log.error("ANGELONE_CLIENT_ID not set in .env")
            return False
        if not cfg.ANGELONE_API_KEY:
            log.error("ANGELONE_API_KEY not set in .env")
            return False
        if not cfg.ANGELONE_PASSWORD:
            log.error("ANGELONE_PASSWORD not set in .env")
            return False
        if not cfg.ANGELONE_TOTP_SECRET:
            log.error("ANGELONE_TOTP_SECRET not set in .env")
            return False

        totp_code = pyotp.TOTP(cfg.ANGELONE_TOTP_SECRET).now()
        api       = SmartConnect(api_key=cfg.ANGELONE_API_KEY)
        data      = api.generateSession(
            cfg.ANGELONE_CLIENT_ID,
            cfg.ANGELONE_PASSWORD,
            totp_code,
        )

        if not data.get("status"):
            log.error("AngelOne login failed: %s", data.get("message", "unknown"))
            return False

        _api        = api
        _session_at = time.time()

        _save_session_to_redis()

        log.info("AngelOne login successful")
        return True

    except Exception as e:
        log.error("AngelOne login error: %s", e)
        return False


def get_api():
    global _api, _session_at

    if _api is not None:
        age = time.time() - _session_at
        if age < _SESSION_TTL:
            return _api
        log.info("AngelOne session expired in memory — re-logging in")

    if _api is None and _session_at == 0.0:
        if _load_session_from_redis():
            log.info("Attempting to restore AngelOne session from Redis")
            success = _login()
            if success:
                return _api

    success = _login()
    if success:
        return _api

    log.error("AngelOne get_api failed — all login attempts exhausted")
    return None


def refresh_session():
    global _api, _session_at
    log.info("Forcing AngelOne session refresh")
    _api        = None
    _session_at = 0.0

    try:
        r = _get_redis()
        if r:
            r.delete(_REDIS_SESSION_KEY)
            r.delete(_REDIS_SESSION_AT)
    except Exception:
        pass

    success = _login()
    if success:
        return _api
    return None


async def init_indian_session() -> bool:
    if _load_session_from_redis():
        log.info("Found existing session in Redis — attempting reuse")

    success = _login()
    if success:
        log.info("AngelOne session initialized")
        return True

    log.warning("AngelOne session failed — Indian market disabled")
    return False


def is_session_valid() -> bool:
    if _api is None:
        return False
    age = time.time() - _session_at
    return age < _SESSION_TTL


def get_session_age_hours() -> float:
    if _session_at == 0.0:
        return -1.0
    return round((time.time() - _session_at) / 3600, 2)