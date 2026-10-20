"""Static, offline guards: no claiming fabricated performance, no Gmail/email relinking."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_login_does_not_present_fabricated_performance():
    content = (ROOT/'dashboard/src/pages/Login.tsx').read_text()
    assert 'MOCK_TICKER' not in content
    assert 'STATS.map' not in content
    assert 'System operational' not in content
    assert 'Continue with Google' in content
    assert 'emailAccountsAvailable &&' in content


def test_email_feature_is_disabled_by_default_and_ui_is_not_published_to_aws():
    backend = (ROOT/'saas/email_accounts.py').read_text()
    routes = (ROOT/'saas/email_routes.py').read_text()
    source = (ROOT/'dashboard/src/App.tsx').read_text()
    assert "os.environ.get('EMAIL_ACCOUNTS_ENABLED', '').lower() == 'true'" in backend
    assert "os.environ.get('SECURITY_EMAIL_ENABLED', '').lower() == 'true'" in backend
    assert "prefix='/auth/email'" in routes
    assert 'path="/verify-email"' in source and 'path="/reset-password"' in source
    assert not (ROOT/'frontend').exists()


def test_frontend_uses_server_entitlements_and_correct_free_fallback():
    from config import get_tier_features, TIER_FREE
    source = (ROOT/'dashboard/src/stores/authStore.ts').read_text()
    guard = (ROOT/'dashboard/src/components/layout/AuthGuard.tsx').read_text()
    assert f'signal_delay_minutes:   {get_tier_features(TIER_FREE)["signal_delay_minutes"]},' in source
    assert 'serverFeatures ??' in source
    assert "authApi.get('/api/me')" in guard
