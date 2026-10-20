"""Opt-in email identity lifecycle. Google and legacy admin authentication stay independent.

All tokens and passwords are stored as one-way digests. No email identity is
created before its inbox has been verified. The public API uses generic
responses for account enumeration resistance.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from database import Base, User, Subscription, UserSession, get_session
from config import TIER_FREE
from saas.security_email import SecurityEmailType, send_security_email, DeliveryUnavailable


class EmailCredential(Base):
    __tablename__ = 'email_credentials'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    password_digest = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class EmailChallenge(Base):
    __tablename__ = 'email_challenges'
    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False, index=True)
    purpose = Column(String, nullable=False)  # register or reset; no arbitrary notification types
    digest = Column(String, unique=True, nullable=False)
    pending_password_digest = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)


class EmailThrottle(Base):
    __tablename__ = 'email_throttles'
    key = Column(String, primary_key=True)
    window_start = Column(DateTime, nullable=False)
    count = Column(Integer, nullable=False)


ACCOUNT_MESSAGE = 'If the address is eligible, an email will be sent with the next step.'
TOKEN_MINUTES = 20
_TOKEN_PATTERN = re.compile(r'^[0-9a-f]{64}$')
_EMAIL_PATTERN = re.compile(r'^[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+$')


class InvalidChallenge(ValueError):
    pass


class Throttled(RuntimeError):
    pass


def enabled() -> bool:
    return (os.environ.get('EMAIL_ACCOUNTS_ENABLED', '').lower() == 'true'
            and os.environ.get('SECURITY_EMAIL_ENABLED', '').lower() == 'true')


def normalize_email(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError('Invalid email')
    email = value.strip().lower()
    if (len(email) > 254 or any(c in email for c in '<>,;:\"()[]')
            or not _EMAIL_PATTERN.fullmatch(email)):
        raise ValueError('Invalid email')
    return email


def _utcnow():
    return datetime.now(timezone.utc)


def _as_utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def hash_password(password: str, salt: bytes | None = None) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 128 or len(password.encode('utf-8')) > 256:
        raise ValueError('Password length must be 12–128 characters')
    salt = salt or secrets.token_bytes(16)
    result = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f'scrypt$16384$8$1${salt.hex()}${result.hex()}'


def matches_password(password: str, encoded: str) -> bool:
    try:
        name, n, r, p, salt, digest = encoded.split('$')
        if name != 'scrypt' or (int(n), int(r), int(p)) != (16384, 8, 1):
            return False
        if len(password.encode('utf-8')) > 256:
            return False
        expected = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(expected, bytes.fromhex(digest))
    except (ValueError, TypeError, AttributeError, UnicodeEncodeError):
        return False


def _rate_limit(db, email: str, kind: str, ip: str, *, limit: int = 5, minutes: int = 20) -> None:
    # SQLite-persisted throttling does not silently become unlimited when Redis fails.
    now = _utcnow()
    for label in (email, f'ip:{ip}'):
        key = hashlib.sha256(f'email-auth:{kind}:{label}'.encode()).hexdigest()
        row = db.get(EmailThrottle, key)
        if row is None:
            db.add(EmailThrottle(key=key, window_start=now, count=1))
        elif now - _as_utc(row.window_start) >= timedelta(minutes=minutes):
            row.window_start = now
            row.count = 1
        elif row.count >= limit:
            raise Throttled('Too many requests; please try again later')
        else:
            row.count += 1


def _create_challenge(db, email: str, purpose: str, password_digest: str | None = None):
    now = _utcnow()
    db.query(EmailChallenge).filter(EmailChallenge.email == email, EmailChallenge.purpose == purpose, EmailChallenge.consumed_at.is_(None)).delete(synchronize_session=False)
    token = secrets.token_hex(32)
    db.add(EmailChallenge(email=email, purpose=purpose, digest=digest_token(token),
                          pending_password_digest=password_digest, created_at=now,
                          expires_at=now + timedelta(minutes=TOKEN_MINUTES)))
    return token


def _link(token: str, path: str) -> str:
    # Fragment is not sent to Cloudflare in HTTP request or referrer.
    from saas.frontend_url import frontend_location
    return frontend_location(path) + '#token=' + quote(token)


def request_registration(email: str, password: str, ip: str = '', *, dispatch=None) -> str:
    if not enabled():
        raise DeliveryUnavailable('Email accounts are disabled')
    address = normalize_email(email)
    password_digest = hash_password(password)
    with get_session() as db:
        _rate_limit(db, address, 'register', ip)
        if db.query(User.id).filter(func.lower(User.email) == address).first():
            return ACCOUNT_MESSAGE
        token = _create_challenge(db, address, 'register', password_digest)
    try:
        (dispatch or send_security_email)(to=address, kind=SecurityEmailType.VERIFY_EMAIL,
                            message=f'Open this link to verify your Signal Engine account (expires in {TOKEN_MINUTES} minutes):\n{_link(token, "/verify-email")}')
    except DeliveryUnavailable:
        # The token stays expiring in the DB, but cannot be used without receiving the email.
        raise
    return ACCOUNT_MESSAGE


def verify_registration(token: str) -> bool:
    if not _TOKEN_PATTERN.fullmatch(token or ''):
        raise InvalidChallenge('Invalid or expired verification link')
    now = _utcnow()
    with get_session() as db:
        challenge = db.query(EmailChallenge).filter_by(digest=digest_token(token), purpose='register', consumed_at=None).first()
        if not challenge or _as_utc(challenge.expires_at) <= now:
            raise InvalidChallenge('Invalid or expired verification link')
        if db.query(User.id).filter(func.lower(User.email) == challenge.email).first():
            raise InvalidChallenge('Account already exists; use its original sign-in method')
        if db.query(EmailChallenge).filter(EmailChallenge.id == challenge.id, EmailChallenge.consumed_at.is_(None),
                                          EmailChallenge.expires_at > now).update({'consumed_at': now}, synchronize_session=False) != 1:
            raise InvalidChallenge('Verification link already used')
        user = User(email=challenge.email, name=None, provider='email', provider_id=secrets.token_hex(16),
                    tier=TIER_FREE, is_admin=False, is_active=True, onboarded=False,
                    created_at=now, last_seen=now)
        db.add(user)
        db.flush()
        db.add(EmailCredential(user_id=user.id, password_digest=challenge.pending_password_digest,
                               created_at=now, updated_at=now))
        db.add(Subscription(user_id=user.id, tier=TIER_FREE, status='active', created_at=now, updated_at=now))
        challenge.pending_password_digest = None
    return True


def authenticate(email: str, password: str, ip: str = '') -> dict | None:
    address = normalize_email(email)
    with get_session() as db:
        _rate_limit(db, address, 'login', ip, limit=10, minutes=15)
        user = db.query(User).filter(func.lower(User.email) == address).first()
        credential = db.get(EmailCredential, user.id) if user and user.provider == 'email' else None
        # A costly dummy hash also prevents user-existence timing shortcuts.
        stored = credential.password_digest if credential else _DUMMY_HASH
        valid = matches_password(password, stored)
        if not (user and credential and user.is_active and valid):
            return None
        user.last_login = _utcnow()
        user.last_seen = _utcnow()
        return {'id': user.id, 'email': user.email, 'tier': user.tier, 'is_admin': user.is_admin}


# Static dummy generated with the same parameters; never a real account credential.
_DUMMY_HASH = 'scrypt$16384$8$1$0123456789abcdef0123456789abcdef$' + hashlib.scrypt(
    b'no-account-password', salt=bytes.fromhex('0123456789abcdef0123456789abcdef'),
    n=2**14, r=8, p=1, dklen=32).hex()


def request_password_reset(email: str, ip: str = '', *, dispatch=None) -> str:
    if not enabled():
        raise DeliveryUnavailable('Email accounts are disabled')
    address = normalize_email(email)
    with get_session() as db:
        _rate_limit(db, address, 'reset', ip)
        user = db.query(User).filter(func.lower(User.email) == address).first()
        if not user or user.provider != 'email' or not user.is_active or not db.get(EmailCredential, user.id):
            return ACCOUNT_MESSAGE
        token = _create_challenge(db, address, 'reset')
    (dispatch or send_security_email)(to=address, kind=SecurityEmailType.RESET_PASSWORD,
                        message=f'Open this link to reset your Signal Engine account password (expires in {TOKEN_MINUTES} minutes):\n{_link(token, "/reset-password")}')
    return ACCOUNT_MESSAGE


def reset_password(token: str, new_password: str) -> bool:
    if not _TOKEN_PATTERN.fullmatch(token or ''):
        raise InvalidChallenge('Invalid or expired reset link')
    hashed = hash_password(new_password)
    now = _utcnow()
    with get_session() as db:
        challenge = db.query(EmailChallenge).filter_by(digest=digest_token(token), purpose='reset', consumed_at=None).first()
        if not challenge or _as_utc(challenge.expires_at) <= now:
            raise InvalidChallenge('Invalid or expired reset link')
        user = db.query(User).filter(func.lower(User.email) == challenge.email, User.provider == 'email', User.is_active.is_(True)).first()
        if not user:
            raise InvalidChallenge('Invalid or expired reset link')
        credential = db.get(EmailCredential, user.id)
        if not credential:
            raise InvalidChallenge('Invalid or expired reset link')
        if db.query(EmailChallenge).filter(EmailChallenge.id == challenge.id, EmailChallenge.consumed_at.is_(None),
                                          EmailChallenge.expires_at > now).update({'consumed_at': now}, synchronize_session=False) != 1:
            raise InvalidChallenge('Reset link already used')
        credential.password_digest = hashed
        credential.updated_at = now
        db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.is_active.is_(True)).update({UserSession.is_active: False, UserSession.revoked_at: now}, synchronize_session=False)
        address = user.email
    try:
        send_security_email(to=address, kind=SecurityEmailType.PASSWORD_CHANGED,
                            message='Your Signal Engine password was changed. If this was not you, contact the account administrator.')
    except DeliveryUnavailable:
        pass  # Security event committed; notification failure must not roll it back.
    return True
