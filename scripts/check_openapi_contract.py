#!/usr/bin/env python3
"""Build and sanity-check the FastAPI OpenAPI contract in an isolated process."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]

CHILD = r'''
import main

app = main.app
schema = app.openapi()
assert schema["info"]["version"] == "5.0.0"
operations = [
    (path, method, operation)
    for path, path_item in schema["paths"].items()
    for method, operation in path_item.items()
    if method != "parameters"
]
assert operations, "OpenAPI contains no operations"
operation_ids = [operation.get("operationId") for _, _, operation in operations]
assert all(operation_ids), "Every operation must have an operationId"
assert len(operation_ids) == len(set(operation_ids)), "OpenAPI operationId values must be unique"
assert "post" in schema["paths"]["/auth/logout"]
assert "get" not in schema["paths"]["/auth/logout"]
registered = {
    (route.path, method.lower())
    for route in app.routes
    if getattr(route, "include_in_schema", False)
    for method in getattr(route, "methods", set())
}
documented = {(path, method) for path, method, _ in operations}
assert registered == documented, f"Registered/schema mismatch: {registered ^ documented}"
assert any(getattr(route, "path", None) == "/ws/dashboard" for route in app.routes)
print(f"OpenAPI contract passed: {len(operations)} HTTP operations; WebSocket route registered; version {schema['info']['version']}.")
'''

# Importing main.py bootstraps first-run credentials and the SQLAlchemy module
# initializes its database. Keep the schema check away from local/project data.
with TemporaryDirectory(prefix="signal-engine-openapi-") as temporary_dir:
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": str(ROOT),
        "SIGNAL_ENGINE_DATABASE_PATH": str(Path(temporary_dir) / "contract.db"),
        "TOTP_SECRET": "JBSWY3DPEHPK3PXP",
        "JWT_SECRET": "openapi-contract-local-only-jwt-secret",
        "OAUTH_JWT_SECRET": "openapi-contract-local-only-oauth-secret",
        "DASHBOARD_API_KEY": "openapi-contract-local-only-api-key",
        "WEBHOOK_SECRET": "openapi-contract-local-only-webhook-secret",
        "DASHBOARD_USERNAME": "schema-check",
        "TRADING_MODE": "paper",
        "SYSTEM_VERSION": "schema-check",
        "BINANCE_API_KEY": "",
        "BINANCE_SECRET": "",
        "BINANCE_DEMO_API_KEY": "",
        "BINANCE_DEMO_SECRET": "",
        "TELEGRAM_BOT_TOKEN": "",
        "GOOGLE_CLIENT_ID": "",
        "GOOGLE_CLIENT_SECRET": "",
    })
    subprocess.run([sys.executable, "-c", CHILD], cwd=ROOT, env=env, check=True)
