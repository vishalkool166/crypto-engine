import os
import logging
import time
import pyotp
import bcrypt
import qrcode
import qrcode.image.svg
from io import BytesIO
from jose import jwt, JWTError
from datetime import datetime, timezone, timedelta
from config import cfg, _ensure
from database import get_session, AuditLog

log = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_H  = 24


# ── Password ─────────────────────────────────────────────────────────────────

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


# ── Username ──────────────────────────────────────────────────────────────────

def verify_username(username: str) -> bool:
    return username.strip().lower() == cfg.DASHBOARD_USERNAME.strip().lower()


def set_username(username: str):
    _ensure("DASHBOARD_USERNAME", username.strip())
    cfg.DASHBOARD_USERNAME = username.strip()
    log.info(f"Dashboard username set: {username}")


# ── TOTP ──────────────────────────────────────────────────────────────────────

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
    log.info(f"TOTP secret regenerated: {secret}")
    return secret


def get_qr_svg() -> str:
    try:
        uri = get_totp_uri()
        qr  = qrcode.QRCode(
            version           = 1,
            error_correction  = qrcode.constants.ERROR_CORRECT_L,
            box_size          = 10,
            border            = 4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
        buf = BytesIO()
        img.save(buf)
        return buf.getvalue().decode()
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


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_jwt() -> str:
    payload = {
        "sub": "dashboard",
        "usr": cfg.DASHBOARD_USERNAME,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_H)
    }
    return jwt.encode(payload, cfg.JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> bool:
    try:
        jwt.decode(token, cfg.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return True
    except JWTError:
        return False


# ── Login ─────────────────────────────────────────────────────────────────────

def validate_login(username: str, password: str, totp_code: str, ip: str = "") -> dict:
    success = False
    reason  = ""

    if not username:
        reason = "Username required"
    elif not verify_username(username):
        reason = "Invalid username"
    elif not password_is_set():
        reason = "Password not configured — visit /auth/setup"
    elif not verify_password(password, cfg.DASHBOARD_PASSWORD_HASH):
        reason = "Invalid password"
    elif not verify_totp(totp_code):
        reason = "Invalid TOTP code"
    else:
        success = True

    _audit(
        action  = "dashboard_login",
        source  = "web",
        detail  = reason if not success else f"Login successful — user:{username}",
        ip      = ip,
        success = success
    )

    if success:
        return {"success": True, "token": create_jwt(), "username": cfg.DASHBOARD_USERNAME}
    return {"success": False, "reason": reason}


# ── Reset password via TOTP ───────────────────────────────────────────────────

def reset_password_with_totp(totp_code: str, new_password: str, ip: str = "") -> dict:
    if not verify_totp(totp_code):
        _audit("password_reset_failed", "web", "Invalid TOTP", ip=ip, success=False)
        return {"success": False, "reason": "Invalid TOTP code"}

    if len(new_password) < 8:
        return {"success": False, "reason": "Password must be at least 8 characters"}

    set_password(new_password)
    _audit("password_reset", "web", "Password reset via TOTP", ip=ip, success=True)
    return {"success": True}


# ── API Key ───────────────────────────────────────────────────────────────────

def verify_api_key(key: str) -> bool:
    return bool(cfg.DASHBOARD_API_KEY) and key == cfg.DASHBOARD_API_KEY


# ── Auth check ────────────────────────────────────────────────────────────────

def is_authenticated(request) -> bool:
    api_key = request.headers.get("X-API-Key", "")
    if api_key and verify_api_key(api_key):
        return True
    token = request.cookies.get("se_token", "")
    if token and verify_jwt(token):
        return True
    return False


# ── Audit ─────────────────────────────────────────────────────────────────────

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


# ── Setup status ──────────────────────────────────────────────────────────────

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