"""Offline deployment-contract guards; these are NOT live API or browser tests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cloudflare_is_only_a_static_frontend():
    vite = (ROOT / 'dashboard/vite.config.ts').read_text()
    assert "outDir: 'dist'" in vite
    assert "runtimeCaching: []" in vite
    assert not (ROOT / '.github/workflows').exists()


def test_backend_retains_existing_start_command_and_data_volume():
    docker = (ROOT / 'Dockerfile').read_text()
    compose = (ROOT / 'docker-compose.yml').read_text()
    assert '"main:app"' in docker
    assert './database:/app/database' in compose
    assert 'redis_data:/data' in compose
    assert 'COPY . .' in docker


def test_pages_admin_requests_use_configured_aws_client():
    users = (ROOT / 'dashboard/src/pages/Users.tsx').read_text()
    assert "api.get<DemoStats>('/api/admin/demo/stats')" in users
    assert "fetch('/api/admin/demo/stats'" not in users
    api = (ROOT / 'dashboard/src/lib/api.ts').read_text()
    assert 'VITE_API_URL' in api
    assert 'withCredentials: true' in api


def test_oauth_destination_is_server_configured_and_legacy_fallback_preserved():
    main = (ROOT / 'main.py').read_text()
    assert '_os.environ.get("FRONTEND_URL") or cfg.DOMAIN' in main
    assert 'f"{dashboard_origin}/"' in main
    assert 'redirect_uri = f"{cfg.DOMAIN' in main
