"""Regression checks for routes that launch work or change server state."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _route_methods(source: str, owner: str = "router") -> dict[str, set[str]]:
    tree = ast.parse(source)
    routes: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != owner:
                continue
            if decorator.func.attr not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            routes.setdefault(decorator.args[0].value, set()).add(decorator.func.attr.upper())
    return routes


def test_expensive_or_stateful_routes_require_post():
    routes = _route_methods((ROOT / "api/routes.py").read_text())
    expected = {
        "/scan": "POST",
        "/backtest/{coin}": "POST",
        "/backtest/all/run": "POST",
    }
    for path, method in expected.items():
        assert routes.get(path) == {method}, f"{path} must be exposed only as {method}"


def test_session_logout_requires_post():
    routes = _route_methods((ROOT / "main.py").read_text(), owner="app")
    assert routes.get("/auth/logout") == {"POST"}


def test_frontend_uses_post_for_scan_and_backtest():
    source = (ROOT / "dashboard/src/lib/endpoints.ts").read_text()
    assert "scan:    () => api.post('/api/scan')" in source
    assert "backtest:        (coin: string) => api.post<BacktestResult>(`/api/backtest/${coin}`)" in source


def test_frontend_uses_post_for_session_logout():
    source = (ROOT / "dashboard/src/lib/endpoints.ts").read_text()
    assert "logout: () => api.post('/auth/logout')" in source
