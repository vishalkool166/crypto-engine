#!/usr/bin/env python3
"""Generate non-secret deployment config from the private root .env."""

import json, os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main():
    from portal_settings import settings

    settings.validate()
    zone = os.getenv("CLOUDFLARE_ZONE_NAME", "vishalkool.top")
    for host in (settings.public_host, settings.admin_host):
        if not (host == zone or host.endswith("." + zone)):
            raise SystemExit("Both hosts must belong to CLOUDFLARE_ZONE_NAME")
    public = os.getenv("PUBLIC_PAGES_PROJECT", "signal-engine-public")
    admin = os.getenv("ADMIN_PAGES_PROJECT", "signal-engine-admin")
    for name in (public, admin):
        if not name.replace("-", "").isalnum():
            raise SystemExit("Invalid Pages project name")
    result = {
        "name": "signal-engine-gateway",
        "main": "gateway.js",
        "compatibility_date": "2026-04-07",
        "workers_dev": False,
        "routes": [
            {"pattern": host + "/*", "zone_name": zone}
            for host in (settings.public_host, settings.admin_host)
        ],
        "vars": {
            "PUBLIC_APP_ORIGIN": settings.public_origin,
            "ADMIN_APP_ORIGIN": settings.admin_origin,
            "PUBLIC_PAGES_ORIGIN": "https://" + public + ".pages.dev",
            "ADMIN_PAGES_ORIGIN": "https://" + admin + ".pages.dev",
        },
    }
    (ROOT / "deploy/cloudflare/wrangler.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print("Generated deploy/cloudflare/wrangler.json (no secrets).")
    print("Google redirect URI:", settings.admin_origin + "/auth/callback/google")
    print("Tunnel hostnames:", settings.public_host, settings.admin_host)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT))
    main()
