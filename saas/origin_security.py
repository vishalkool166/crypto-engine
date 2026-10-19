"""Cookie-authenticated unsafe-request origin guard for split AWS/Pages hosting.

Existing EC2 deployments are opt-in until browser and automation clients are tested.
Header based API token callers without cookies are unaffected.
"""
from urllib.parse import urlsplit


def canonical_origin(value: str | None) -> str | None:
    if not value or value.strip() != value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname:
            return None
        if parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
            return None
        host = parsed.hostname.lower()
        # Do not consider untrusted suffixes, user-info or invalid ports valid.
        port = parsed.port
        default_port = 443 if parsed.scheme == 'https' else 80
        suffix = f':{port}' if port and port != default_port else ''
        return f'{parsed.scheme}://{host}{suffix}'
    except ValueError:
        return None


def allowed_request_origin(origin: str | None, trusted_origins: list[str]) -> bool:
    candidate = canonical_origin(origin)
    return candidate is not None and candidate in {
        parsed for item in trusted_origins
        if (parsed := canonical_origin(item)) is not None
    }
