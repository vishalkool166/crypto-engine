"""Server-owned navigation to the separately hosted Cloudflare dashboard.

Never accept a caller-supplied redirect origin; only predefined internal paths.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

from config import cfg


_ALLOWED_PATHS = frozenset({"/", "/login", "/login?error=oauth_failed", "/verify-email", "/reset-password"})


def frontend_location(path: str = "/") -> str:
    if path not in _ALLOWED_PATHS:
        raise ValueError("Unapproved frontend redirect path")

    origin = (os.environ.get("FRONTEND_URL") or cfg.FRONTEND_URL or "").strip()
    if any(ord(c) < 33 or ord(c) == 127 for c in origin):
        raise ValueError("Invalid frontend origin")
    url = urlsplit(origin)
    if (url.scheme not in {"http", "https"} or not url.hostname
            or url.username is not None or url.password is not None
            or url.path not in {"", "/"} or url.query or url.fragment):
        raise ValueError("FRONTEND_URL must be an HTTP(S) origin without path or credentials")
    # In production, never direct authenticated clients to cleartext HTTP.
    if cfg.ENV == "production" and url.scheme != "https":
        raise ValueError("Production frontend origin must use HTTPS")
    try:
        _ = url.port
    except ValueError as exc:
        raise ValueError("Invalid frontend origin port") from exc
    # Explicitly reject relative/hostless redirects and backslashes in hostnames.
    if "\\" in url.netloc:
        raise ValueError("Invalid frontend origin hostname")
    return f"{url.scheme}://{url.netloc.rstrip('/')}{path}"
