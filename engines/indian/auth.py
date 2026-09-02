import logging
import time
from config import cfg

log = logging.getLogger(__name__)

_api        = None
_session_at = 0.0
_SESSION_TTL = 20 * 3600


def _login():
    global _api, _session_at
    try:
        import pyotp
        from SmartApi import SmartConnect

        totp_code = pyotp.TOTP(cfg.ANGELONE_TOTP_SECRET).now()
        api       = SmartConnect(api_key=cfg.ANGELONE_API_KEY)
        data      = api.generateSession(
            cfg.ANGELONE_CLIENT_ID,
            cfg.ANGELONE_PASSWORD,
            totp_code,
        )

        if not data.get("status"):
            log.error("AngelOne login failed: %s", data.get("message"))
            return None

        _api        = api
        _session_at = time.time()
        log.info("AngelOne login successful")
        return _api

    except Exception as e:
        log.error("AngelOne login error: %s", e)
        return None


def get_api():
    global _api, _session_at
    if _api is None or (time.time() - _session_at) > _SESSION_TTL:
        log.info("AngelOne session expired or missing — re-logging in")
        _login()
    return _api


def refresh_session():
    global _api, _session_at
    log.info("Forcing AngelOne session refresh")
    _api        = None
    _session_at = 0.0
    return _login()


async def init_indian_session() -> bool:
    api = _login()
    if api:
        log.info("AngelOne session initialized")
        return True
    log.warning("AngelOne session failed — Indian market disabled")
    return False


def is_session_valid() -> bool:
    return _api is not None and (time.time() - _session_at) < _SESSION_TTL