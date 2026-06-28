import os
import logging
import time
import json
import secrets
import hashlib
import pyotp
import bcrypt
import qrcode
import qrcode.image.svg
from io import BytesIO
from jose import jwt, JWTError
from datetime import datetime, timezone, timedelta
from config import cfg, _ensure, TIER_FREE, TIER_ADMIN, tier_meets_minimum
from database import get_session, AuditLog, User, ApiKey

log = logging.getLogger(__name__)

JWT_ALGORITHM  = "HS256"
JWT_EXPIRY_H   = 24

OAUTH_ALGORITHM = "HS256"

_failed_attempts: dict = {}
_lockout_until:   dict = {}

MAX_ATTEMPTS     = 5
LOCKOUT_MINUTES  = 15
ATTEMPT_WINDOW   = 300


def _get_attempt_key(ip: str) -> str:
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _is_locked_out(ip: str) -> tuple[bool, int]:
    key   = _get_attempt_key(ip)
    until = _lockout_until.get(key, 0)
    now   = time.time()
    if until > now:
        remaining = int((until - now) / 60) + 1
        return True, remaining
    return False, 0


def _record_failure(ip: str):
    key      = _get_attempt_key(ip)
    now      = time.time()
    attempts = _failed_attempts.get(key, [])
    attempts = [t for t in attempts if now - t < ATTEMPT_WINDOW]
    attempts.append(now)
    _failed_attempts[key] = attempts
    if len(attempts) >= MAX_ATTEMPTS:
        _lockout_until[key] = now + LOCKOUT_MINUTES * 60
        log.warning(f"IP locked out after {MAX_ATTEMPTS} failed attempts: {ip[:8]}***")
    return len(attempts)


def _clear_attempts(ip: str):
    key = _get_attempt_key(ip)
    _failed_attempts.pop(key, None)
    _lockout_until.pop(key, None)


def _attempts_remaining(ip: str) -> int:
    key      = _get_attempt_key(ip)
    now      = time.time()
    attempts = _failed_attempts.get(key, [])
    attempts = [t for t in attempts if now - t < ATTEMPT_WINDOW]
    return max(0, MAX_ATTEMPTS - len(attempts))


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def set_password(plain: str):
    h = hash_password(plain)
    _ensure("DASHBOARD_PASSWORD_HASH", h)
    cfg.DASHBOARD_PASSWORD_HASH = h
    log.info("Dashboard password set")


def password_is_set() -> bool:
    return bool(cfg.DASHBOARD_PASSWORD_HASH)


def verify_username(username: str) -> bool:
    return username.strip().lower() == cfg.DASHBOARD_USERNAME.strip().lower()


def set_username(username: str):
    _ensure("DASHBOARD_USERNAME", username.strip())
    cfg.DASHBOARD_USERNAME = username.strip()
    log.info(f"Dashboard username set: {username}")


def get_totp() -> pyotp.TOTP:
    return pyotp.TOTP(cfg.TOTP_SECRET)


def verify_totp(code: str) -> bool:
    try:
        return get_totp().verify(str(code).strip(), valid_window=1)
    except Exception:
        return False


def get_totp_uri() -> str:
    return get_totp().provisioning_uri(
        name        = cfg.DASHBOARD_USERNAME or "SignalEngine",
        issuer_name = "SignalEngineV5"
    )


def regenerate_totp() -> str:
    secret = pyotp.random_base32()
    _ensure("TOTP_SECRET", secret)
    cfg.TOTP_SECRET = secret
    log.info("TOTP secret regenerated")
    return secret


def get_qr_svg() -> str:
    try:
        uri = get_totp_uri()
        qr  = qrcode.QRCode(
            version          = 1,
            error_correction = qrcode.constants.ERROR_CORRECT_L,
            box_size         = 10,
            border           = 4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
        buf = BytesIO()
        img.save(buf)
        svg = buf.getvalue().decode()
        svg = svg.replace("'", '"')
        svg = svg.replace("svg:rect", "rect")
        svg = svg.replace("svg:svg", "svg")
        svg = svg.replace('xmlns:svg="http://www.w3.org/2000/svg"', '')
        return svg
    except Exception as e:
        log.error(f"QR SVG generation error: {e}")
        return ""


def get_qr_png_bytes() -> bytes:
    try:
        uri = get_totp_uri()
        qr  = qrcode.QRCode(
            version          = 1,
            error_correction = qrcode.constants.ERROR_CORRECT_L,
            box_size         = 10,
            border           = 4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        log.error(f"QR PNG generation error: {e}")
        return b""


def generate_recovery_codes(count: int = 8) -> list[str]:
    codes = []
    for _ in range(count):
        code = secrets.token_hex(4).upper() + '-' + secrets.token_hex(4).upper()
        codes.append(code)
    return codes


def hash_recovery_codes(codes: list[str]) -> list[str]:
    return [hashlib.sha256(c.encode()).hexdigest() for c in codes]


def store_recovery_codes(codes: list[str]):
    hashed = hash_recovery_codes(codes)
    _ensure("RECOVERY_CODES", json.dumps(hashed))
    cfg.RECOVERY_CODES = json.dumps(hashed)
    log.info(f"Recovery codes stored: {len(codes)} codes")


def verify_recovery_code(code: str) -> bool:
    try:
        stored_raw = getattr(cfg, 'RECOVERY_CODES', '') or os.getenv("RECOVERY_CODES", "")
        if not stored_raw:
            return False
        stored    = json.loads(stored_raw)
        code_hash = hashlib.sha256(code.strip().upper().encode()).hexdigest()
        if code_hash in stored:
            stored.remove(code_hash)
            _ensure("RECOVERY_CODES", json.dumps(stored))
            cfg.RECOVERY_CODES = json.dumps(stored)
            log.info("Recovery code used and invalidated")
            return True
        return False
    except Exception as e:
        log.error(f"Recovery code verify error: {e}")
        return False


def create_jwt(tier: str = "pro") -> str:
    payload = {
        "sub":  "dashboard",
        "usr":  cfg.DASHBOARD_USERNAME,
        "tier": tier,
        "iat":  datetime.now(timezone.utc),
        "exp":  datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_H)
    }
    return jwt.encode(payload, cfg.JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> bool:
    try:
        jwt.decode(token, cfg.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return True
    except JWTError:
        return False


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, cfg.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return {}


def validate_login(username: str, password: str, totp_code: str, ip: str = "") -> dict:
    locked, minutes = _is_locked_out(ip)
    if locked:
        _audit(
            action  = "dashboard_login",
            source  = "web",
            detail  = f"Blocked — IP locked out for {minutes}m",
            ip      = ip,
            success = False
        )
        return {
            "success":         False,
            "reason":          f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes > 1 else ''}.",
            "locked":          True,
            "lockout_minutes": minutes
        }

    success = False
    reason  = ""

    if not username:
        reason = "Username required"
    elif not verify_username(username):
        reason = "Invalid credentials"
    elif not password_is_set():
        reason = "Account not configured — visit /auth/setup"
    elif not verify_password(password, cfg.DASHBOARD_PASSWORD_HASH):
        reason = "Invalid credentials"
    elif not verify_totp(totp_code):
        reason = "Invalid authenticator code"
    else:
        success = True

    if not success:
        count     = _record_failure(ip)
        remaining = _attempts_remaining(ip)
        locked_now, lock_mins = _is_locked_out(ip)

        _audit(
            action  = "dashboard_login",
            source  = "web",
            detail  = reason,
            ip      = ip,
            success = False
        )

        result = {
            "success": False,
            "reason":  reason,
            "locked":  locked_now,
        }

        if locked_now:
            result["reason"]          = f"Too many failed attempts. Locked for {lock_mins} minute{'s' if lock_mins > 1 else ''}."
            result["lockout_minutes"] = lock_mins
        else:
            result["attempts_remaining"] = remaining

        return result

    _clear_attempts(ip)

    _audit(
        action  = "dashboard_login",
        source  = "web",
        detail  = f"Login successful — user:{username}",
        ip      = ip,
        success = True
    )

    return {
        "success":  True,
        "token":    create_jwt(tier="pro"),
        "username": cfg.DASHBOARD_USERNAME,
        "tier":     "pro"
    }


def reset_password_with_totp(totp_code: str, new_password: str, ip: str = "") -> dict:
    if not verify_totp(totp_code):
        _audit("password_reset_failed", "web", "Invalid TOTP", ip=ip, success=False)
        return {"success": False, "reason": "Invalid authenticator code"}
    if len(new_password) < 8:
        return {"success": False, "reason": "Password must be at least 8 characters"}
    set_password(new_password)
    _audit("password_reset", "web", "Password reset via TOTP", ip=ip, success=True)
    return {"success": True}


def reset_password_with_recovery(recovery_code: str, new_password: str, ip: str = "") -> dict:
    if not verify_recovery_code(recovery_code):
        _audit("password_reset_failed", "web", "Invalid recovery code", ip=ip, success=False)
        return {"success": False, "reason": "Invalid recovery code"}
    if len(new_password) < 8:
        return {"success": False, "reason": "Password must be at least 8 characters"}
    set_password(new_password)
    _audit("password_reset", "web", "Password reset via recovery code", ip=ip, success=True)
    return {"success": True}


def verify_api_key(key: str) -> bool:
    return bool(cfg.DASHBOARD_API_KEY) and key == cfg.DASHBOARD_API_KEY


def is_authenticated(request) -> bool:
    api_key = request.headers.get("X-API-Key", "")
    if api_key and verify_api_key(api_key):
        return True
    token = request.cookies.get("se_token", "")
    if token and verify_jwt(token):
        return True
    user = get_oauth_user_from_request(request)
    if user:
        return True
    return False


def get_user_tier(request) -> str:
    user = get_oauth_user_from_request(request)
    if user:
        return user.get("tier", TIER_FREE)
    token = request.cookies.get("se_token", "")
    if token:
        payload = decode_jwt(token)
        return payload.get("tier", "pro")
    return "pro"


def _audit(action: str, source: str, detail: str = "", ip: str = "", success: bool = True):
    try:
        with get_session() as db:
            db.add(AuditLog(
                action  = action,
                source  = source,
                detail  = detail,
                ip      = ip,
                success = success
            ))
    except Exception as e:
        log.error(f"Audit log error: {e}")


def audit(action: str, source: str, detail: str = "", ip: str = "", success: bool = True):
    _audit(action, source, detail, ip, success)


def setup_status() -> dict:
    return {
        "totp_secret_set":    bool(cfg.TOTP_SECRET),
        "password_set":       password_is_set(),
        "username_set":       bool(cfg.DASHBOARD_USERNAME),
        "api_key_set":        bool(cfg.DASHBOARD_API_KEY),
        "webhook_secret_set": bool(cfg.WEBHOOK_SECRET),
        "setup_complete":     password_is_set() and bool(cfg.TOTP_SECRET),
        "totp_uri":           get_totp_uri() if cfg.TOTP_SECRET else "",
        "api_key":            cfg.DASHBOARD_API_KEY,
        "username":           cfg.DASHBOARD_USERNAME
    }


def create_oauth_jwt(user_id: int, email: str, tier: str, is_admin: bool) -> str:
    payload = {
        "sub":      str(user_id),
        "email":    email,
        "tier":     tier,
        "is_admin": is_admin,
        "type":     "oauth",
        "iat":      datetime.now(timezone.utc),
        "exp":      datetime.now(timezone.utc) + timedelta(hours=cfg.OAUTH_JWT_EXPIRY),
    }
    return jwt.encode(payload, cfg.OAUTH_JWT_SECRET, algorithm=OAUTH_ALGORITHM)


def decode_oauth_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, cfg.OAUTH_JWT_SECRET, algorithms=[OAUTH_ALGORITHM])
    except JWTError:
        return {}


def get_oauth_user_from_request(request) -> dict | None:
    token = request.cookies.get(cfg.SESSION_COOKIE_NAME, "")
    if not token:
        token = request.headers.get("X-User-Token", "")
    if not token:
        return None
    payload = decode_oauth_jwt(token)
    if not payload:
        return None
    return payload


def verify_oauth_api_key(key: str) -> dict | None:
    if not key or not key.startswith("se_"):
        return None
    try:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        with get_session() as db:
            api_key = db.query(ApiKey).filter(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True
            ).first()
            if not api_key:
                return None
            if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
                return None
            api_key.last_used = datetime.now(timezone.utc)
            user = db.query(User).filter(User.id == api_key.user_id).first()
            if not user or not user.is_active:
                return None
            return {
                "sub":      str(user.id),
                "email":    user.email,
                "tier":     user.tier,
                "is_admin": user.is_admin,
                "type":     "api_key",
            }
    except Exception as e:
        log.error(f"API key verify error: {e}")
        return None


def get_current_user_any(request) -> dict | None:
    api_key_header = request.headers.get("X-API-Key", "")
    if api_key_header:
        if verify_api_key(api_key_header):
            return {
                "sub":      "0",
                "email":    cfg.DASHBOARD_USERNAME,
                "tier":     TIER_ADMIN,
                "is_admin": True,
                "type":     "master_key",
            }
        oauth_user = verify_oauth_api_key(api_key_header)
        if oauth_user:
            return oauth_user

    oauth_user = get_oauth_user_from_request(request)
    if oauth_user:
        return oauth_user

    token = request.cookies.get("se_token", "")
    if token and verify_jwt(token):
        payload = decode_jwt(token)
        return {
            "sub":      "0",
            "email":    cfg.DASHBOARD_USERNAME,
            "tier":     TIER_ADMIN,
            "is_admin": True,
            "type":     "legacy",
        }

    return None


def is_admin_user(user: dict) -> bool:
    if not user:
        return False
    if user.get("is_admin"):
        return True
    email = user.get("email", "")
    return cfg.is_admin_email(email)


def generate_api_key() -> tuple[str, str, str]:
    raw    = "se_" + secrets.token_hex(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    prefix = raw[:12]
    return raw, hashed, prefix