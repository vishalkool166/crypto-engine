#!/usr/bin/env python3
"""Create a private .env without printing secrets. Never overwrites an existing one."""

from pathlib import Path
import secrets
import os

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env"
if target.exists():
    raise SystemExit(".env already exists; edit it instead of replacing it")
values = {
    "ENV": "production",
    "PUBLIC_APP_ORIGIN": "https://app.vishalkool.top",
    "ADMIN_APP_ORIGIN": "https://admin-app.vishalkool.top",
    "ADMIN_EMAILS": "vishalkool166@gmail.com",
    "ADMIN_SESSION_HOURS": "12",
    "TRADING_MODE": "paper",
    "ENGINE_ENABLED": "true",
    "SESSION_SECRET": secrets.token_hex(48),
    "ORIGIN_PROXY_SECRET": secrets.token_hex(48),
    "WEBHOOK_SECRET": secrets.token_hex(32),
    "GOOGLE_CLIENT_ID": "",
    "GOOGLE_CLIENT_SECRET": "",
    "BINANCE_DEMO_API_KEY": "",
    "BINANCE_DEMO_SECRET": "",
    "TELEGRAM_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
    "TELEGRAM_ALLOWED_USER_IDS": "",
    "TOTP_SECRET": "",
    "REDIS_URL": "redis://redis:6379/0",
    "SIGNAL_ENGINE_DB_PATH": "database/signals.db",
    "TUNNEL_TOKEN": "",
    "CLOUDFLARE_ZONE_NAME": "vishalkool.top",
    "PUBLIC_PAGES_PROJECT": "signal-engine-public",
    "ADMIN_PAGES_PROJECT": "signal-engine-admin",
    "GROQ_API_KEY": "",
    "SYSTEM_VERSION": "1.0.0",
}
fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(
        "# Private production configuration. Empty provider values must be supplied before deployment.\n"
    )
    for k, v in values.items():
        f.write(k + "=" + v + "\n")
print(
    "Created private .env with fresh random application secrets; provider credentials are empty, not simulated."
)
