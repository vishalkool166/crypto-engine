#!/usr/bin/env python3
"""Check the checked-in HTTP/WebSocket route inventory against source decorators."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/engineering/API_SECURITY_INVENTORY.md"
SOURCES = {
    "main.py": ("", "main"),
    "api/routes.py": ("/api", "authenticated-user helper"),
    "api/trading.py": ("/api", "administrator helper"),
    "api/engine_health.py": ("/api", "administrator helper"),
    "api/indian.py": ("/api", "authenticated-user helper"),
    "saas/admin.py": ("/api", "administrator helper"),
    "saas/email_routes.py": ("/auth/email", "feature-gated public auth"),
}
PUBLIC_POLICIES = {
    ("main.py", "api_health"): "public liveness",
    ("main.py", "api_readiness"): "public sanitized database/Redis readiness",
    ("main.py", "auth_google"): "public OAuth initiation",
    ("main.py", "auth_callback_google"): "public OAuth callback; Authlib validates state",
    ("main.py", "auth_login"): "public password login with rate limit",
    ("main.py", "request_totp_via_telegram"): "public endpoint; requires dashboard password",
    ("main.py", "auth_reset_password"): "public endpoint; requires TOTP or recovery proof",
    ("main.py", "get_pricing"): "public pricing catalogue",
    ("main.py", "login_page"): "public legacy redirect",
    ("main.py", "legacy_dashboard_home"): "public legacy redirect",
    ("main.py", "telegram_webhook"): "public endpoint; delegates shared-secret validation",
    ("api/routes.py", "coins_active"): "public, non-sensitive symbol list",
    ("saas/email_routes.py", "status"): "public email-feature availability only",
    ("saas/email_routes.py", "register"): "public; dual-flag gated and throttled",
    ("saas/email_routes.py", "verify"): "public; single-use verification token",
    ("saas/email_routes.py", "login"): "public; dual-flag gated and throttled",
    ("saas/email_routes.py", "request_reset"): "public; generic response and throttle",
    ("saas/email_routes.py", "reset"): "public; single-use reset token",
}


def render() -> str:
    rows = []
    for relative, (prefix, helper_policy) in SOURCES.items():
        tree = ast.parse((ROOT / relative).read_text())
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = set()
            for item in ast.walk(node):
                if isinstance(item, ast.Call):
                    if isinstance(item.func, ast.Name):
                        calls.add(item.func.id)
                    elif isinstance(item.func, ast.Attribute):
                        calls.add(item.func.attr)
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id not in {"app", "router"}:
                    continue
                method = decorator.func.attr.upper()
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "WEBSOCKET"}:
                    continue
                path = ast.literal_eval(decorator.args[0]) if decorator.args else "?"
                if prefix and not path.startswith(prefix):
                    path = prefix + path
                if "require_admin_access" in calls:
                    guard = "`require_admin_access` — administrator"
                elif "require_setup_access" in calls:
                    guard = "`require_setup_access` — setup token before provisioning; administrator after"
                elif "get_current_user" in calls:
                    guard = "`get_current_user` — active session/user"
                elif "is_authenticated" in calls:
                    guard = "`is_authenticated` — authenticated user"
                elif "_auth" in calls:
                    guard = f"`_auth` — {helper_policy} (see helper in source)"
                elif "_get_ws_user" in calls:
                    guard = "`_get_ws_user` — active session; origin checked when supplied"
                elif "handle_webhook" in calls:
                    guard = "`handle_webhook` — Telegram webhook secret"
                elif (relative, node.name) in PUBLIC_POLICIES:
                    guard = f"Public by design — {PUBLIC_POLICIES[(relative, node.name)]}"
                else:
                    guard = "UNCLASSIFIED — route authorization test must fail"
                if method == "GET":
                    behavior = "Read/redirect/provider callback; verify handler remains side-effect safe"
                elif method == "WEBSOCKET":
                    behavior = "Long-lived authenticated stream"
                else:
                    behavior = "State change or command; verify step-up, validation and audit as applicable"
                rows.append((method, path, relative, node.name, node.lineno, guard, behavior))

    rows.sort(key=lambda item: (item[2], item[1], item[0], item[3]))
    body = [
        "# API and WebSocket security inventory",
        "",
        "Source-generated from route decorators on 2026-10-20. This is a source review aid, not a live authorization test or release certification.",
        "",
        f"The inventory contains {sum(row[0] != 'WEBSOCKET' for row in rows)} HTTP operations and {sum(row[0] == 'WEBSOCKET' for row in rows)} WebSocket route.",
        "",
        "## Guard semantics",
        "",
        "| Source | Helper meaning |",
        "| --- | --- |",
        "| `api/routes.py` | `_auth` calls `auth.is_authenticated`; selected admin handlers additionally call `require_admin_access`. |",
        "| `api/indian.py` | `_auth` calls `auth.is_authenticated`; setup, scan, refresh and quota diagnostics require administrator access. |",
        "| `api/trading.py` | `_auth` calls `require_admin_access`; trade account and execution controls are administrator-only. |",
        "| `api/engine_health.py` | `_auth` calls `require_admin_access`; rejection reset also requires TOTP. |",
        "| `saas/admin.py` | `_auth` checks an active user and `is_admin`; unauthorized users receive 404. |",
        "| `saas/email_routes.py` | Anonymous identity endpoints are unavailable unless both email-account flags are enabled; token flows and persistent throttling are enforced in the account service. |",
        "| `main.py` | Session routes resolve current users; OAuth callbacks use Authlib; setup routes use setup/admin checks; TOTP and recovery controls have endpoint-specific proof. |",
        "",
        "## Endpoint map",
        "",
        "| Method | Path | Handler | Guard observed in handler | Behavior to verify | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for method, path, relative, name, lineno, guard, behavior in rows:
        body.append(f"| `{method}` | `{path}` | `{name}` | {guard} | {behavior} | `{relative}:{lineno}` |")
    body.extend([
        "",
        "## Public and protocol exceptions",
        "",
        "Anonymous routes are intentional only for liveness, public pricing, login/recovery, OAuth initiation/callback, feature-gated email authentication, legacy redirects, a non-sensitive symbol list, and the Telegram webhook (which delegates secret validation). `GET /auth/logout` was converted to `POST`; market scan and backtest launch routes are also POST. OAuth redirects/callbacks remain GET because the provider protocol returns there; Authlib state validation and verified Google identity are source checks that still need browser integration tests.",
        "",
        "Personal SaaS API keys are read-only (GET/HEAD/OPTIONS), never receive the administrator role, and new keys expire after 90 days. The legacy dashboard master key remains a separate privileged credential. Existing account API keys with no expiry must be manually revoked and recreated.",
        "",
        "The strict cookie-origin check remains opt-in (`STRICT_SESSION_ORIGIN_CHECK=true`) pending cross-origin browser validation. The current source-level route matrix checks classification and helper semantics; it does not prove tenant isolation, CSRF behavior in a real browser, provider callbacks, or every endpoint response permission.",
        "",
    ])
    return "\n".join(body)


expected = render()
if "--write" in sys.argv:
    OUTPUT.write_text(expected)
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
elif not OUTPUT.exists() or OUTPUT.read_text() != expected:
    raise SystemExit("API security inventory is missing or stale; run scripts/check_api_inventory.py --write")
else:
    count = expected.count("| `GET` |") + expected.count("| `POST` |") + expected.count("| `PUT` |") + expected.count("| `PATCH` |") + expected.count("| `DELETE` |") + expected.count("| `WEBSOCKET` |")
    print(f"API security inventory passed: {count} route operations classified from source.")
