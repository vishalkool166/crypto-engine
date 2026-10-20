"""Offline checks for the AWS-API / Cloudflare-UI boundary."""
from pathlib import Path

import pytest

from saas.frontend_url import frontend_location


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_origin_is_server_owned(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://app.vishalkool.top")
    assert frontend_location("/") == "https://app.vishalkool.top/"
    assert frontend_location("/login") == "https://app.vishalkool.top/login"
    assert frontend_location("/login?error=oauth_failed") == "https://app.vishalkool.top/login?error=oauth_failed"


@pytest.mark.parametrize("origin", [
    "//evil.test", "javascript:alert(1)", "https://app.example.com@evil.test",
    "https://app.example.com/path", "https://app.example.com/?next=evil",
    "https://app.example.com/#fragment", "https://app.example.com\\@evil.test",
    "https://app.example.com\r\nX-Injected: yes", "https://app.example.com:abc",
])
def test_rejects_malformed_frontend_origin(monkeypatch, origin):
    monkeypatch.setenv("FRONTEND_URL", origin)
    with pytest.raises(ValueError):
        frontend_location("/")


def test_redirect_allowlist(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "https://app.vishalkool.top")
    for path in ("//evil.test", "/admin", "https://evil.test", "/login?next=https://evil.test"):
        with pytest.raises(ValueError):
            frontend_location(path)


def test_static_frontend_is_no_longer_a_backend_dependency():
    source = (ROOT / "main.py").read_text()
    assert "Jinja2Templates" not in source
    assert "StaticFiles" not in source
    assert "templates.TemplateResponse" not in source
    assert "app.mount(" not in source
    assert "serve_spa(" not in source
    assert '@app.get("/auth/google")' in source
    assert '@app.get("/auth/callback/google")' in source
    assert '@app.websocket("/ws/dashboard")' in source
    assert '@app.post("/webhook/telegram")' in source
    assert '@app.get("/api/health", include_in_schema=False)' in source
    assert not (ROOT / "frontend").exists()
    assert not (ROOT / "dashboard/public/_redirects").exists()
