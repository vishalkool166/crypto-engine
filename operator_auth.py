"""Google-only operator identity and revocable opaque sessions.

Historical customer tables are not modified. Tokens are stored as hashes.
Authlib validates OIDC signatures, issuer, audience, state, and nonce.
"""

import hashlib
import hmac
import logging
import secrets
import time
from sqlalchemy import text
from fastapi import HTTPException
from portal_settings import settings

log = logging.getLogger(__name__)


def init_operator_schema():
    from database import engine

    with engine.begin() as db:
        db.execute(
            text("""CREATE TABLE IF NOT EXISTS operator_identities (
            email TEXT PRIMARY KEY, google_subject TEXT NOT NULL UNIQUE, created_at REAL NOT NULL)""")
        )
        db.execute(
            text("""CREATE TABLE IF NOT EXISTS operator_sessions (
            token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, csrf TEXT NOT NULL,
            expires_at REAL NOT NULL, created_at REAL NOT NULL)""")
        )


def validate_identity(info):
    email = str(info.get("email", "")).strip().lower()
    subject = info.get("sub")
    if (
        info.get("email_verified") is not True
        or not subject
        or email not in settings.admin_emails
    ):
        raise HTTPException(403, "This Google account is not an authorized operator")
    return email, str(subject)


def create_operator_session(info):
    from database import engine

    email, subject = validate_identity(info)
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    now = time.time()
    with engine.begin() as db:
        old = db.execute(
            text("SELECT google_subject FROM operator_identities WHERE email=:email"),
            {"email": email},
        ).scalar()
        if old and not hmac.compare_digest(old, subject):
            raise HTTPException(403, "Operator identity mismatch")
        if not old:
            db.execute(
                text("INSERT INTO operator_identities VALUES (:email,:subject,:now)"),
                {"email": email, "subject": subject, "now": now},
            )
        db.execute(
            text("DELETE FROM operator_sessions WHERE expires_at < :now"), {"now": now}
        )
        db.execute(
            text(
                "INSERT INTO operator_sessions VALUES (:token,:email,:csrf,:expires,:now)"
            ),
            {
                "token": hashlib.sha256(token.encode()).hexdigest(),
                "email": email,
                "csrf": csrf,
                "expires": now + settings.session_hours * 3600,
                "now": now,
            },
        )
    return token


def current_operator(request):
    token = request.cookies.get(settings.cookie_name, "")
    if not token or len(token) > 256:
        return None
    try:
        from database import engine

        with engine.connect() as db:
            row = (
                db.execute(
                    text(
                        "SELECT email, csrf, expires_at FROM operator_sessions WHERE token_hash=:token"
                    ),
                    {"token": hashlib.sha256(token.encode()).hexdigest()},
                )
                .mappings()
                .first()
            )
        if (
            not row
            or row["expires_at"] <= time.time()
            or row["email"] not in settings.admin_emails
        ):
            return None
        return {
            "sub": row["email"],
            "email": row["email"],
            "is_admin": True,
            "tier": "admin",
            "type": "operator",
            "csrf": row["csrf"],
            "expires_at": row["expires_at"],
        }
    except Exception:
        log.error("Operator session store unavailable")
        return None


def require_operator(request):
    user = current_operator(request)
    if not user:
        raise HTTPException(401, "Operator authentication required")
    return user


def revoke_operator_session(request):
    from database import engine

    token = request.cookies.get(settings.cookie_name, "")
    with engine.begin() as db:
        db.execute(
            text("DELETE FROM operator_sessions WHERE token_hash=:token"),
            {"token": hashlib.sha256(token.encode()).hexdigest()},
        )


def cleanup_expired_sessions():
    from database import engine

    with engine.begin() as db:
        return db.execute(
            text("DELETE FROM operator_sessions WHERE expires_at < :now"),
            {"now": time.time()},
        ).rowcount


def oauth_client():
    from authlib.integrations.starlette_client import OAuth
    import os

    if not os.getenv("GOOGLE_CLIENT_ID") or not os.getenv("GOOGLE_CLIENT_SECRET"):
        raise HTTPException(503, "Google operator sign-in is not configured")
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
            "code_challenge_method": "S256",
        },
    )
    return oauth.google
