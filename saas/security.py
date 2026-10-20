"""Centralized privileged-access checks for account-level operations."""
import hmac
import os
from fastapi import HTTPException
from auth import is_admin_user as _auth_is_admin_user
from saas.middleware import get_current_user


def is_admin_user(user: dict | None) -> bool:
    if user and user.get("type") == "api_key":
        return False
    return _auth_is_admin_user(user)


def require_admin_access(request) -> dict:
    user = get_current_user(request)
    if user is None:
        raise HTTPException(401, "Authentication required")
    if not is_admin_user(user):
        raise HTTPException(403, "Administrator privileges required")
    return user


def require_setup_access(request) -> None:
    """No public initial provisioning. Local operator supplies a dedicated secret.

    Once a dashboard password exists, only an authenticated administrator may
    access credential material. The bootstrap token is never an ongoing backdoor.
    """
    from auth import password_is_set
    if password_is_set():
        require_admin_access(request)
        return
    token = os.environ.get("SIGNAL_ENGINE_SETUP_TOKEN", "")
    provided = request.headers.get("X-Setup-Token", "")
    if not token or not provided or not hmac.compare_digest(token, provided):
        raise HTTPException(403, "Initial setup requires SIGNAL_ENGINE_SETUP_TOKEN")
