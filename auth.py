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


# ── Password ────────────────────────────────────────────────────────────────

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


# ── TOTP ────────────────────────────────────────────────────────────────────

def get_totp() -> pyotp.TOTP:
    return pyotp.TOTP(cfg.TOTP_SECRET)


def verify_totp(code: str) -> bool:
    try:
        return get_totp().verify(code, valid_window=1)
    except Exception:
        return False


def get_totp_uri() -> str:
    return get_totp().provisioning_uri(
        name="SignalEngine",
        issuer_name="SignalEngineV5"
    )


def get_qr_svg() -> str:
    uri = get_totp_uri()
    qr  = qrcode.make(uri, image_factory=qrcode.image.svg.SvgImage)
    buf = BytesIO()
    qr.save(buf)
    return buf.getvalue().decode()


def get_qr_png_bytes() -> bytes:
    uri = get_totp_uri()
    qr  = qrcode.make(uri)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()


# ── JWT ─────────────────────────────────────────────────────────────────────

def create_jwt() -> str:
    payload = {
        "sub": "dashboard",
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


# ── Login validation ─────────────────────────────────────────────────────────

def validate_login(password: str, totp_code: str, ip: str = "") -> dict:
    success = False
    reason  = ""

    if not password_is_set():
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
        detail  = reason if not success else "Login successful",
        ip      = ip,
        success = success
    )

    if success:
        return {"success": True, "token": create_jwt()}
    return {"success": False, "reason": reason}


# ── API Key ──────────────────────────────────────────────────────────────────

def verify_api_key(key: str) -> bool:
    return bool(cfg.DASHBOARD_API_KEY) and key == cfg.DASHBOARD_API_KEY


# ── Auth check (JWT cookie OR API key header) ────────────────────────────────

def is_authenticated(request) -> bool:
    # API key header
    api_key = request.headers.get("X-API-Key", "")
    if api_key and verify_api_key(api_key):
        return True

    # JWT cookie
    token = request.cookies.get("se_token", "")
    if token and verify_jwt(token):
        return True

    return False


# ── Audit log ────────────────────────────────────────────────────────────────

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


# ── First run setup ──────────────────────────────────────────────────────────

def setup_status() -> dict:
    return {
        "totp_secret_set":    bool(cfg.TOTP_SECRET),
        "password_set":       password_is_set(),
        "api_key_set":        bool(cfg.DASHBOARD_API_KEY),
        "webhook_secret_set": bool(cfg.WEBHOOK_SECRET),
        "setup_complete":     password_is_set() and bool(cfg.TOTP_SECRET),
        "totp_uri":           get_totp_uri() if cfg.TOTP_SECRET else "",
        "api_key":            cfg.DASHBOARD_API_KEY
    }