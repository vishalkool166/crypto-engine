"""One validated domain configuration. Browser URLs remain same-origin."""

import os
from dotenv import load_dotenv

load_dotenv()
from urllib.parse import urlsplit
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    public_origin: str = os.getenv(
        "PUBLIC_APP_ORIGIN", "http://localhost:5173"
    ).rstrip("/")
    admin_origin: str = os.getenv(
        "ADMIN_APP_ORIGIN", "http://localhost:5174"
    ).rstrip("/")
    production: bool = os.getenv("ENV", "development") == "production"
    session_secret: str = os.getenv("SESSION_SECRET", "")
    origin_secret: str = os.getenv("ORIGIN_PROXY_SECRET", "")
    session_hours: int = int(os.getenv("ADMIN_SESSION_HOURS", "12"))
    admin_emails: tuple = tuple(
        e.strip().lower()
        for e in os.getenv("ADMIN_EMAILS", "operator@example.com").split(",")
        if e.strip()
    )

    @property
    def admin_host(self):
        return urlsplit(self.admin_origin).netloc

    @property
    def public_host(self):
        return urlsplit(self.public_origin).netloc

    @property
    def cookie_name(self):
        return "__Host-se_operator" if self.production else "se_operator"

    def validate(self):
        for value in (self.public_origin, self.admin_origin):
            u = urlsplit(value)
            if (
                u.scheme not in ("http", "https")
                or not u.netloc
                or u.path
                or u.query
                or u.fragment
            ):
                raise RuntimeError("App origins must contain only scheme and hostname")
            if self.production and u.scheme != "https":
                raise RuntimeError("Production origins must use HTTPS")
        if self.public_origin == self.admin_origin:
            raise RuntimeError("Public and admin origins must differ")
        if not self.admin_emails or not 1 <= self.session_hours <= 24:
            raise RuntimeError(
                "Configure ADMIN_EMAILS and an ADMIN_SESSION_HOURS value from 1 to 24"
            )
        if self.production:
            for key in ("SESSION_SECRET", "ORIGIN_PROXY_SECRET"):
                if len(os.getenv(key, "")) < 32:
                    raise RuntimeError(
                        key + " must be configured with at least 32 random characters"
                    )
            for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
                if not os.getenv(key):
                    raise RuntimeError(key + " must be configured")
        if os.getenv("TRADING_MODE", "paper") != "paper":
            raise RuntimeError("This release supports paper trading only")


settings = Settings()
