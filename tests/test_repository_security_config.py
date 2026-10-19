"""Cheap, network-free config guards for ongoing refactors."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_pwa_does_not_cache_private_api_responses():
    vite=(ROOT/'dashboard'/'vite.config.ts').read_text()
    assert 'runtimeCaching: []' in vite
    assert 'api-cache' not in vite

def test_dev_proxy_does_not_default_to_live_production():
    vite=(ROOT/'dashboard'/'vite.config.ts').read_text()
    assert "http://127.0.0.1:8000" in vite
    assert 'signal-engine-v5.vishalkool.top' not in vite

def test_trading_emails_are_absent_from_security_delivery():
    source=(ROOT/'saas'/'security_email.py').read_text()
    for forbidden in ('TRADE_OPENED', 'SIGNAL', 'PERFORMANCE_REPORT', 'MARKETING_EMAIL'):
        assert forbidden not in source
