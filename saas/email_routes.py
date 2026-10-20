"""Isolated public routes for opt-in email authentication.

Disabled until EMAIL_ACCOUNTS_ENABLED and SECURITY_EMAIL_ENABLED are both true.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import cfg
from saas import email_accounts as accounts
from saas.security_email import DeliveryUnavailable

router = APIRouter(prefix='/auth/email', tags=['email accounts'])


class EmailPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)


class AddressRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class TokenRequest(BaseModel):
    token: str = Field(min_length=64, max_length=64)


class ResetRequest(TokenRequest):
    password: str = Field(min_length=12, max_length=128)


def _enabled():
    if not accounts.enabled():
        raise HTTPException(404, 'Email accounts not enabled')


def _ip(request: Request) -> str:
    # Don't trust spoofable X-Forwarded-For unless proxy trust is configured.
    return request.client.host if request.client else 'unknown'


@router.get('/status')
async def status():
    return {'enabled': accounts.enabled()}


@router.post('/register')
async def register(body: EmailPasswordRequest, request: Request, background_tasks: BackgroundTasks):
    _enabled()
    try:
        message = accounts.request_registration(body.email, body.password, _ip(request),
             dispatch=lambda **kwargs: background_tasks.add_task(accounts.send_security_email, **kwargs))
        return JSONResponse({'message': message}, headers={'Cache-Control': 'no-store'})
    except accounts.Throttled as e:
        raise HTTPException(429, str(e))
    except DeliveryUnavailable:
        raise HTTPException(503, 'Email delivery temporarily unavailable')
    except ValueError:
        raise HTTPException(400, 'Invalid account details')


@router.post('/verify')
async def verify(body: TokenRequest):
    _enabled()
    try:
        accounts.verify_registration(body.token)
        return {'success': True, 'message': 'Email verified. You may now sign in.'}
    except accounts.InvalidChallenge:
        raise HTTPException(400, 'Invalid or expired verification link')


@router.post('/login')
async def login(body: EmailPasswordRequest, request: Request):
    _enabled()
    try:
        user = accounts.authenticate(body.email, body.password, _ip(request))
    except accounts.Throttled:
        raise HTTPException(429, 'Too many attempts; try again later')
    except ValueError:
        user = None
    if not user:
        raise HTTPException(401, 'Invalid credentials')
    from saas.sessions import create_session
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    sid = create_session(user_id=user['id'], tier=user['tier'], ip=_ip(request),
                         user_agent=request.headers.get('user-agent', ''))
    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub': str(user['id']), 'email': user['email'], 'tier': user['tier'],
                        'is_admin': user['is_admin'], 'session_id': sid, 'type': 'oauth',
                        'iat': now, 'exp': now + timedelta(hours=cfg.OAUTH_JWT_EXPIRY)},
                       cfg.OAUTH_JWT_SECRET, algorithm='HS256')
    response = JSONResponse({'success': True}, headers={'Cache-Control': 'no-store'})
    response.set_cookie(key=cfg.SESSION_COOKIE_NAME, value=token,
                        httponly=cfg.SESSION_COOKIE_HTTPONLY,
                        secure=cfg.SESSION_COOKIE_SECURE,
                        samesite=cfg.SESSION_COOKIE_SAMESITE,
                        max_age=cfg.SESSION_COOKIE_MAX_AGE)
    return response


@router.post('/request-reset')
async def request_reset(body: AddressRequest, request: Request, background_tasks: BackgroundTasks):
    _enabled()
    try:
        return {'message': accounts.request_password_reset(body.email, _ip(request),
             dispatch=lambda **kwargs: background_tasks.add_task(accounts.send_security_email, **kwargs))}
    except accounts.Throttled as e:
        raise HTTPException(429, str(e))
    except DeliveryUnavailable:
        raise HTTPException(503, 'Email delivery temporarily unavailable')
    except ValueError:
        raise HTTPException(400, 'Invalid email')


@router.post('/reset')
async def reset(body: ResetRequest):
    _enabled()
    try:
        accounts.reset_password(body.token, body.password)
        return {'success': True, 'message': 'Password updated. Please sign in again.'}
    except accounts.InvalidChallenge:
        raise HTTPException(400, 'Invalid or expired reset link')
    except ValueError:
        raise HTTPException(400, 'Invalid password')
