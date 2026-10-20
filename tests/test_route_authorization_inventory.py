"""Source-level route authorization matrix; live browser auth remains a staging gate."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE_FILES = (
    "main.py",
    "api/routes.py",
    "api/trading.py",
    "api/engine_health.py",
    "api/indian.py",
    "saas/admin.py",
    "saas/email_routes.py",
)

# Anonymous routes are intentional and require an explicit reason here. This
# prevents a new endpoint from silently entering the app without a policy.
PUBLIC_ROUTES = {
    ("main.py", "api_health"): "public liveness",
    ("main.py", "api_readiness"): "sanitized public dependency readiness",
    ("main.py", "auth_google"): "OAuth initiation",
    ("main.py", "auth_callback_google"): "OAuth callback",
    ("main.py", "auth_login"): "credential login",
    ("main.py", "request_totp_via_telegram"): "password-gated login factor delivery",
    ("main.py", "auth_reset_password"): "TOTP or recovery-code proof",
    ("main.py", "get_pricing"): "public product catalogue",
    ("main.py", "login_page"): "legacy redirect",
    ("main.py", "legacy_dashboard_home"): "legacy redirect",
    ("main.py", "auth_logout"): "session revocation; safe POST",
    ("main.py", "telegram_webhook"): "shared-secret webhook handler",
    ("api/routes.py", "coins_active"): "non-sensitive public symbol list",
    ("saas/email_routes.py", "status"): "feature availability only",
    ("saas/email_routes.py", "register"): "feature-gated registration with persistent throttle",
    ("saas/email_routes.py", "verify"): "single-use email challenge",
    ("saas/email_routes.py", "login"): "credential login with persistent throttle",
    ("saas/email_routes.py", "request_reset"): "generic, throttled recovery response",
    ("saas/email_routes.py", "reset"): "single-use reset challenge",
}

# These helpers have file-specific meanings; the test verifies the helper
# implementations below so a generic `_auth` call cannot mask a policy change.
AUTH_HELPER_POLICY = {
    "api/routes.py": "authenticated",
    "api/indian.py": "authenticated",
    "api/trading.py": "admin",
    "api/engine_health.py": "admin",
    "saas/admin.py": "admin",
}


def _route_nodes(relative: str):
    tree = ast.parse((ROOT / relative).read_text())
    found = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id not in {"app", "router"}:
                continue
            if decorator.func.attr not in {"get", "post", "put", "patch", "delete", "websocket"}:
                continue
            path = ast.literal_eval(decorator.args[0]) if decorator.args else "?"
            found.append((node, decorator.func.attr.upper(), path))
    return found


def _calls(node) -> set[str]:
    names = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Name):
            names.add(item.func.id)
        elif isinstance(item.func, ast.Attribute):
            names.add(item.func.attr)
    return names


def test_every_http_and_websocket_route_has_a_classified_guard():
    seen = set()
    for relative in ROUTE_FILES:
        for node, method, path in _route_nodes(relative):
            key = (relative, node.name)
            seen.add(key)
            calls = _calls(node)
            if key in PUBLIC_ROUTES:
                if key == ("main.py", "telegram_webhook"):
                    assert "handle_webhook" in calls
                if key == ("main.py", "auth_callback_google"):
                    assert "authorize_access_token" in calls
                    source = ast.unparse(node)
                    assert "email_verified" in source and "provider_id" in source
                    assert "is not True" in source
                if key == ("main.py", "auth_google"):
                    assert "authorize_redirect" in calls
                if key == ("main.py", "auth_logout"):
                    assert method == "POST"
                continue
            if "require_setup_access" in calls:
                continue
            if "require_admin_access" in calls:
                continue
            if "get_current_user" in calls or "is_authenticated" in calls:
                continue
            if "_get_ws_user" in calls:  # dashboard websocket authenticates via session middleware
                assert "origin" in ast.unparse(node).lower()
                continue
            if "_auth" in calls:
                assert relative in AUTH_HELPER_POLICY, f"{key} uses an unclassified _auth helper"
                continue
            assert False, f"Unclassified route {method} {path} in {key}; add an explicit policy"

    assert seen == set(PUBLIC_ROUTES) | {
        (relative, node.name)
        for relative in ROUTE_FILES
        for node, _method, _path in _route_nodes(relative)
        if (relative, node.name) not in PUBLIC_ROUTES
    }


def test_auth_helpers_keep_their_declared_semantics():
    for relative, policy in AUTH_HELPER_POLICY.items():
        tree = ast.parse((ROOT / relative).read_text())
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_auth")
        calls = _calls(helper)
        if policy == "admin":
            assert "require_admin_access" in calls or "is_admin" in calls, relative
        else:
            assert "is_authenticated" in calls, relative


def test_admin_api_group_is_not_accidentally_public():
    for relative in ROUTE_FILES:
        for node, _method, path in _route_nodes(relative):
            if path.startswith("/admin/"):
                calls = _calls(node)
                assert "_auth" in calls or "require_admin_access" in calls, (relative, path)


def test_sensitive_api_key_creation_is_validated_and_rate_limited():
    tree = ast.parse((ROOT / "main.py").read_text())
    route = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == "create_api_key")
    decorators = [ast.unparse(item) for item in route.decorator_list]
    assert any("limit" in item and "5/hour" in item for item in decorators)
    assert any("post" in item and "/api/me/api-keys" in item for item in decorators)
    assert any(isinstance(arg.annotation, ast.Name) and arg.annotation.id == "APIKeyCreateRequest"
               for arg in route.args.args)
