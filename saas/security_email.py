"""Restricted Resend transport for account establishment and security events.

This is a provider adapter, NOT an activated public password reset flow.
No method accepts arbitrary templates, HTML, subjects or market/event notifications.
Keep tokens single-use/expiring in authenticated account workflows before calling it.
"""
from __future__ import annotations

import html
import logging
import os
from email.utils import parseaddr
from enum import Enum

import httpx

log = logging.getLogger(__name__)
RESEND_API_URL = 'https://api.resend.com/emails'


class SecurityEmailType(str, Enum):
    VERIFY_EMAIL = 'verify_email'
    ACTIVATE_ACCOUNT = 'activate_account'
    RESET_PASSWORD = 'reset_password'
    PASSWORD_CHANGED = 'password_changed'
    EMAIL_CHANGED = 'email_changed'
    SECURITY_ALERT = 'security_alert'


# Locked mapping: deliberately excludes trade events, reports and marketing.
_SUBJECTS: dict[SecurityEmailType, str] = {
    SecurityEmailType.VERIFY_EMAIL: 'Verify your Signal Engine email',
    SecurityEmailType.ACTIVATE_ACCOUNT: 'Your Signal Engine account is ready',
    SecurityEmailType.RESET_PASSWORD: 'Reset your Signal Engine password',
    SecurityEmailType.PASSWORD_CHANGED: 'Your Signal Engine password changed',
    SecurityEmailType.EMAIL_CHANGED: 'Your Signal Engine email changed',
    SecurityEmailType.SECURITY_ALERT: 'Signal Engine security notice',
}


class DeliveryUnavailable(RuntimeError):
    pass


def _address(value: str) -> str:
    name, addr = parseaddr(value)
    if (not value or name or addr != value or '@' not in addr
            or len(addr) > 254 or any(c.isspace() for c in addr)
            or any(c in value for c in '\r\n<>')):
        raise ValueError('Invalid email address')
    return addr


def send_security_email(*, to: str, kind: SecurityEmailType, message: str,
                        correlation_id: str = '') -> str:
    """Delivers an approved transactional account email; returns provider message ID.

    Caller must authorize recipient, enforce cooldown, and never include raw credentials.
    Do not log message or recipient. Safe when disabled: fails closed.
    """
    if not isinstance(kind, SecurityEmailType):
        raise ValueError('Only approved account-security email types are permitted')
    destination = _address(to)
    if not isinstance(message, str) or not 1 <= len(message) <= 1500:
        raise ValueError('Invalid security email content')
    if os.environ.get('SECURITY_EMAIL_ENABLED', '').lower() != 'true':
        raise DeliveryUnavailable('Security email delivery not enabled')
    key = os.environ.get('RESEND_API_KEY', '')
    sender = os.environ.get('SECURITY_EMAIL_FROM', '')
    if not key or not sender:
        raise DeliveryUnavailable('Security email delivery configuration missing')
    _address(sender)
    # No caller-controlled HTML; escape body text, so links remain plain text.
    html_body = '<div style="font:14px/1.6 system-ui;white-space:pre-wrap">' + html.escape(message) + '</div>'
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(RESEND_API_URL, headers=headers, json={
                'from': sender, 'to': [destination], 'subject': _SUBJECTS[kind],
                'text': message, 'html': html_body,
            })
            response.raise_for_status()
            ident = response.json().get('id')
            if not isinstance(ident, str) or not ident:
                raise DeliveryUnavailable('Provider returned no message ID')
            log.info('Security email accepted: type=%s id=%s corr=%s', kind.value, ident, correlation_id[:48])
            return ident
    except (httpx.HTTPError, ValueError) as exc:
        # No response body, authorization headers, recipient, or sensitive message logged.
        log.error('Security email delivery failed: type=%s corr=%s', kind.value, correlation_id[:48])
        raise DeliveryUnavailable('Provider request failed') from exc
