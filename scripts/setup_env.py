#!/usr/bin/env python3
"""Create a private production .env from the documented example without overwriting."""
from pathlib import Path
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env"
if target.exists():
    raise SystemExit(".env already exists; edit it instead of replacing it")
lines = (ROOT / ".env.example").read_text().splitlines()
values = [line for line in lines if line and not line.startswith("#")]
secrets_to_generate = {
    "SESSION_SECRET": secrets.token_hex(48),
    "ORIGIN_PROXY_SECRET": secrets.token_hex(48),
    "WEBHOOK_SECRET": secrets.token_urlsafe(32),
}
content = "\n".join(
    key + "=" + secrets_to_generate.get(key, value)
    for line in values
    for key, value in [line.split("=", 1)]
) + "\n"
fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(content)
print("Created private .env with fresh application secrets. Add provider credentials before starting production.")
